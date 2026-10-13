"""FastAPI boundary for the bounded research RAG prototype."""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Callable
from contextlib import asynccontextmanager
from typing import Any, Literal

from fastapi import Depends, FastAPI, Header, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from clinical_risk_agent.rag.answering import CURATED_QUESTIONS

from .assessment_store import AssessmentResultStore
from .background import BackgroundJobs
from .capacity import CapacityGate
from .composition import build_conversation
from .monitoring import Monitor
from .services import (
    AssessmentService,
    ConversationService,
    LocalAssessmentService,
    LocalResearchService,
    ResearchService,
)
from .sessions import SessionStore
from .settings import BackendSettings

API_VERSION = "v1"
USAGE_LIMIT_MESSAGE = (
    "This research demo has reached its current usage limit. Assessments and evidence-based "
    "answers are temporarily unavailable. Please try again after the displayed reset time. "
    "No calculation has been performed."
)


class ResearchAnswerRequest(BaseModel):
    """Validate a request selecting one curated research question."""
    model_config = ConfigDict(extra="forbid", strict=True)
    question_id: str = Field(pattern=r"^rq_0[1-5]$")


class MessageRequest(BaseModel):
    """Validate a bounded free-text chat request."""
    model_config = ConfigDict(extra="forbid", strict=True)
    kind: Literal["free_text"]
    text: str = Field(min_length=1, max_length=500)
    # Set when the user taps "Yes" on a clarification; the router re-verifies it.
    confirmed_intent: Literal[
        "risk_assessment", "explain_my_risk", "scientific_question",
        "mental_health_education", "general_conversation",
    ] | None = None


class AssessmentAttestations(BaseModel):
    """Require adult, self-assessment and research-consent confirmations."""
    model_config = ConfigDict(extra="forbid", strict=True)
    age_18_or_over: Literal[True]
    self_assessment: Literal[True]
    research_only_consent: Literal[True]


class AssessmentRequest(BaseModel):
    """Validate questionnaire answers and required assessment attestations."""
    model_config = ConfigDict(extra="forbid", strict=True)
    questionnaire_version: str = Field(min_length=1, max_length=80)
    answers: dict[str, str] = Field(max_length=85)
    attestations: AssessmentAttestations


def _error(code: str, message: str, component: str, status: int,
           *, retryable: bool = False) -> JSONResponse:
    """Build a non-cacheable API error with a stable code and safe message."""
    return JSONResponse(status_code=status, headers={"Cache-Control": "no-store"}, content={
        "api_version": API_VERSION,
        "error": {"code": code, "message": message, "component": component,
                  "retryable": retryable},
    })


def confirmation(payload: MessageRequest) -> dict[str, str]:
    """Forward a clarification confirmation only when the client supplied one."""
    return {"confirmed_intent": payload.confirmed_intent} if payload.confirmed_intent else {}


def create_app(settings: BackendSettings, *, service: ResearchService | None = None,
               conversation: ConversationService | None = None,
               assessment: AssessmentService | None = None,
               clock: Callable[[], float] | None = None) -> FastAPI:
    """Compose the API. Authorization is derived only from transport state."""
    research = service or LocalResearchService(settings.root)
    monitor = Monitor(settings.root)
    intent_port = None
    if conversation is None:
        conversation, intent_port = build_conversation(settings, research,
                                                       observer=monitor.record_intent)
    assessment = assessment or LocalAssessmentService(settings.root)
    sessions = SessionStore(
        settings.session_signing_key, ttl_seconds=settings.session_ttl_seconds,
        max_sessions=settings.max_active_sessions,
        hourly_limit=settings.model_turns_per_hour,
        daily_limit=settings.model_turns_per_day,
        global_daily_limit=settings.global_model_operations_per_day,
        create_limit=settings.session_creations_per_network_hour,
        assessment_daily_limit=settings.assessment_submissions_per_day,
    )
    model_capacity = CapacityGate(settings.max_model_concurrency)
    http_capacity = CapacityGate(settings.max_http_concurrency)
    now = clock
    assessment_results = AssessmentResultStore(settings.session_ttl_seconds)
    jobs = BackgroundJobs(conversation, monitor,
                          timeout_seconds=settings.request_timeout_seconds,
                          explanation_limit=settings.max_model_concurrency)

    def safety_fast_path(token: str, text: str):
        """Answer safety-rule messages without waiting on model capacity or usage quotas.

        A person in crisis must never be told the service is busy or out of quota. Only the
        deterministic safety rules run here; everything else takes the normal path.
        """
        check = getattr(conversation, "safety_response", None)
        if check is None:
            return None
        state = sessions.authorize(token, now=now() if now else None)
        started = time.monotonic()
        result = check(text, deployment_mode=settings.deployment_mode)
        if result is None:
            return None
        monitor.record("chat_safety_fast_path", result["response_kind"],
                       time.monotonic() - started)
        monitor.record_guardrails(result)
        return state, result

    def prior_result(token: str) -> dict[str, Any]:
        """Pass this session's validated assessment scores to the conversation, if any."""
        scores = assessment_results.ready_scores(token)
        return {"prior_result": scores} if scores is not None else {}

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        """Warm models at startup and release volatile state and resources at shutdown."""
        try:
            warmup = getattr(assessment, "warmup", None)
            if warmup is not None:
                started = time.monotonic()
                await asyncio.to_thread(warmup)
                monitor.record("model_startup", "ready", time.monotonic() - started)
            router_warmup = getattr(intent_port, "warmup", None)
            if router_warmup is not None:
                started = time.monotonic()
                await asyncio.to_thread(router_warmup)
                monitor.record("intent_router_startup", "ready", time.monotonic() - started)
            yield
        finally:
            await jobs.shutdown()
            assessment_results.clear()
            research.close()
            close_conversation = getattr(conversation, "close", None)
            if close_conversation is not None:
                close_conversation()

    app = FastAPI(
        title="Bodhica API", version="0.1.0", lifespan=lifespan,
        docs_url=None, redoc_url=None, openapi_url=None,
    )
    app.add_middleware(
        CORSMiddleware, allow_origins=list(settings.allowed_origins),
        allow_credentials=False, allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Authorization", "Content-Type"], max_age=300,
    )

    @app.middleware("http")
    async def transport_boundary(request: Request, call_next):
        """Apply the HTTP concurrency limit before processing a request."""
        if not http_capacity.acquire():
            return _error("HTTP_CAPACITY_EXHAUSTED", "The research demo is at capacity.",
                          "capacity", 503, retryable=True)
        try:
            return await _bounded_transport(request, call_next)
        finally:
            http_capacity.release()

    async def _bounded_transport(request: Request, call_next):
        """Enforce origin, request-size and deployment transport restrictions."""
        origin = request.headers.get("origin")
        if origin and origin not in settings.allowed_origins:
            return _error("ORIGIN_NOT_ALLOWED", "Request origin is not allowed.",
                          "transport", 403)
        content_type = request.headers.get("content-type", "")
        if content_type.lower().startswith("multipart/"):
            return _error("UNSUPPORTED_MEDIA_TYPE", "File uploads are not supported.",
                          "transport", 415)
        length = request.headers.get("content-length")
        if length:
            try:
                too_large = int(length) > settings.max_request_bytes
            except ValueError:
                too_large = True
            if too_large:
                return _error("REQUEST_TOO_LARGE", "Request body is too large.",
                              "transport", 413)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    def bearer(authorization: str | None = Header(default=None)) -> str:
        """Extract the bearer credential required for private session operations."""
        if not authorization or not authorization.startswith("Bearer "):
            raise PermissionError("missing_session")
        return authorization[7:]

    @app.exception_handler(PermissionError)
    async def permission_error(_request: Request, error: PermissionError):
        """Convert session authorization failures into stable public API errors."""
        code = str(error)
        if code in {"hourly_quota_exhausted", "daily_quota_exhausted",
                    "assessment_quota_exhausted"}:
            return _error("SESSION_QUOTA_EXHAUSTED", USAGE_LIMIT_MESSAGE, "quota", 429)
        return _error("SESSION_INVALID", "Session is missing, invalid, or expired.",
                      "session", 401)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, _error_value: RequestValidationError):
        """Return a safe error for malformed public request payloads."""
        return _error("INVALID_REQUEST", "Request validation failed.", "transport", 422)

    @app.get("/health/live")
    async def live():
        """Report that the backend process is running."""
        return {"status": "live", "api_version": API_VERSION}

    @app.get("/health/ready")
    async def ready():
        """Check research and assessment readiness for the public health endpoint."""
        is_ready, corpus_version = await asyncio.to_thread(research.ready)
        if not is_ready:
            return _error("DEPENDENCY_UNAVAILABLE", "Research retrieval is unavailable.",
                          "retrieval", 503, retryable=True)
        return {"status": "ready", "api_version": API_VERSION,
                "deployment_mode": settings.deployment_mode,
                "corpus_version": corpus_version,
                "conversation_generation_ready": bool(
                    settings.llm_provider and settings.llm_model and settings.llm_api_key
                )}

    @app.post("/v1/session", status_code=201)
    async def create_session(request: Request):
        """Issue a quota-limited private session credential."""
        host = request.client.host if request.client else "unknown"
        network_key = sessions.network_digest(host)
        try:
            token, ttl = sessions.create(network_key, now=now() if now else None)
        except PermissionError:
            return _error("SESSION_CREATION_RATE_LIMITED", "Try again later.",
                          "session", 429, retryable=True)
        except OverflowError:
            return _error("SESSION_CAPACITY_EXHAUSTED", "The research demo is at capacity.",
                          "capacity", 503, retryable=True)
        return {"api_version": API_VERSION, "deployment_mode": settings.deployment_mode,
                "session_token": token, "state_version": 1,
                "inactivity_expires_in_seconds": ttl}

    @app.delete("/v1/session")
    async def delete_session(token: str = Depends(bearer)):
        """Invalidate a private session and remove its cached assessment."""
        sessions.delete(token)
        assessment_results.remove(token)
        return {"api_version": API_VERSION, "status": "session_cleared"}

    @app.get("/v1/research/questions")
    async def list_questions(token: str = Depends(bearer)):
        # Static-content reads do not count as explicit user activity.
        """List the curated research questions available to an authorized session."""
        state = sessions.authorize(token, renew=False, now=now() if now else None)
        return {"api_version": API_VERSION, "deployment_mode": settings.deployment_mode,
                "state_version": state.state_version,
                "inactivity_expires_in_seconds": settings.session_ttl_seconds,
                "questions": [{"id": item.public_id, "question": item.question}
                              for item in CURATED_QUESTIONS],
                "limitation": "Research-only; not medical advice or an emergency service."}

    @app.post("/v1/research/answers")
    async def answer_research(payload: ResearchAnswerRequest,
                              token: str = Depends(bearer)):
        """Return a bounded research answer after session, quota and capacity checks."""
        if not model_capacity.acquire():
            return _error("MODEL_CAPACITY_EXHAUSTED", "The research service is busy. Try again.",
                          "capacity", 503, retryable=True)
        try:
            try:
                state = sessions.consume_model_operation(token, now=now() if now else None)
            except OverflowError:
                return _error("GLOBAL_USAGE_LIMIT", USAGE_LIMIT_MESSAGE, "quota", 429)
            try:
                result = await asyncio.wait_for(
                    asyncio.to_thread(research.answer, payload.question_id),
                    timeout=settings.request_timeout_seconds,
                )
            except TimeoutError:
                return _error("REQUEST_DEADLINE_EXPIRED", "The request timed out safely.",
                              "workflow", 504, retryable=True)
            except KeyError:
                return _error("QUESTION_NOT_SUPPORTED", "Select an available research question.",
                              "routing", 422)
            except Exception:
                return _error("RETRIEVAL_UNAVAILABLE", "Research retrieval is unavailable.",
                              "retrieval", 503, retryable=True)
        finally:
            model_capacity.release()
        status_code = (503 if result["status"] == "retrieval_unavailable" else 200)
        body = {"api_version": API_VERSION, "deployment_mode": settings.deployment_mode,
                "state_version": state.state_version,
                "inactivity_expires_in_seconds": settings.session_ttl_seconds,
                "response_kind": result["status"], **result}
        return JSONResponse(status_code=status_code, content=body)

    @app.post("/v1/messages")
    async def submit_message(payload: MessageRequest, token: str = Depends(bearer)):
        """Generate one protected conversational response within the request deadline."""
        started = time.monotonic()
        if fast := safety_fast_path(token, payload.text):
            state, result = fast
            return JSONResponse(status_code=200, content={
                "api_version": API_VERSION, "deployment_mode": settings.deployment_mode,
                "state_version": state.state_version,
                "inactivity_expires_in_seconds": settings.session_ttl_seconds, **result,
            })
        if not model_capacity.acquire():
            return _error("MODEL_CAPACITY_EXHAUSTED", "The research service is busy. Try again.",
                          "capacity", 503, retryable=True)
        try:
            try:
                state = sessions.consume_model_operation(token, now=now() if now else None)
            except OverflowError:
                return _error("GLOBAL_USAGE_LIMIT", USAGE_LIMIT_MESSAGE, "quota", 429)
            try:
                result = await asyncio.wait_for(
                    asyncio.to_thread(
                        conversation.handle, payload.text,
                        deployment_mode=settings.deployment_mode, session_valid=True,
                        **confirmation(payload), **prior_result(token),
                    ),
                    timeout=settings.request_timeout_seconds,
                )
                monitor.record("chat_cache_hit" if result.get("cached") else "chat",
                               result["response_kind"], time.monotonic() - started)
                monitor.record_guardrails(result)
            except TimeoutError:
                monitor.record("chat", "timeout", time.monotonic() - started)
                return _error("REQUEST_DEADLINE_EXPIRED", "The request timed out safely.",
                              "workflow", 504, retryable=True)
            except Exception:
                monitor.record("chat", "error", time.monotonic() - started)
                return _error("WORKFLOW_UNAVAILABLE", "The conversation workflow is unavailable.",
                              "workflow", 503, retryable=True)
        finally:
            model_capacity.release()
        status_code = 503 if result["response_kind"] in {
            "RETRIEVAL_UNAVAILABLE", "GENERATION_UNAVAILABLE",
        } else 200
        body = {
            "api_version": API_VERSION,
            "deployment_mode": settings.deployment_mode,
            "state_version": state.state_version,
            "inactivity_expires_in_seconds": settings.session_ttl_seconds,
            **result,
        }
        jobs.judge(payload.text, result)
        return JSONResponse(status_code=status_code, content=body)

    @app.post("/v1/messages:stream")
    async def stream_message(payload: MessageRequest, token: str = Depends(bearer)):
        """Stream typed validated chat events after protected session authorization."""
        if fast := safety_fast_path(token, payload.text):
            state, result = fast

            async def safety_events():
                """Emit the fixed safety reply as validated content without model work."""
                yield _sse("validated_content", {key: result.get(key) for key in (
                    "response_kind", "message", "limitation", "actions", "route")}, 1)
                yield _sse("done", {
                    "response_kind": result["response_kind"], "provider": None, "model": None,
                    "corpus_version": None, "state_version": state.state_version,
                    "inactivity_expires_in_seconds": settings.session_ttl_seconds,
                }, 2)

            return StreamingResponse(
                safety_events(), media_type="text/event-stream",
                headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
            )
        if not model_capacity.acquire():
            return _error("MODEL_CAPACITY_EXHAUSTED", "The research service is busy. Try again.",
                          "capacity", 503, retryable=True)
        try:
            try:
                state = sessions.consume_model_operation(token, now=now() if now else None)
            except Exception:
                model_capacity.release()
                raise

            async def events():
                """Emit status, validated content, citations or a safe error through SSE."""
                started = time.monotonic()
                try:
                    yield _sse("status", {"phase": "protected_preflight"}, 1)
                    yield _sse("status", {"phase": "retrieval_and_generation"}, 2)
                    try:
                        result = await asyncio.wait_for(
                            asyncio.to_thread(
                                conversation.handle, payload.text,
                                deployment_mode=settings.deployment_mode, session_valid=True,
                                **confirmation(payload), **prior_result(token),
                            ),
                            timeout=settings.request_timeout_seconds,
                        )
                        monitor.record("chat_cache_hit" if result.get("cached") else "chat",
                                       result["response_kind"], time.monotonic() - started)
                        monitor.record_guardrails(result)
                    except TimeoutError:
                        monitor.record("chat", "timeout", time.monotonic() - started)
                        yield _sse("error", {
                            "code": "REQUEST_DEADLINE_EXPIRED",
                            "message": "The request timed out safely.",
                            "component": "workflow", "retryable": True,
                        }, 3)
                        return
                    except Exception:
                        monitor.record("chat", "error", time.monotonic() - started)
                        yield _sse("error", {
                            "code": "WORKFLOW_UNAVAILABLE",
                            "message": "The conversation workflow is unavailable.",
                            "component": "workflow", "retryable": True,
                        }, 3)
                        return
                    if result["response_kind"] in {"RETRIEVAL_UNAVAILABLE", "GENERATION_UNAVAILABLE"}:
                        yield _sse("error", {
                            "code": result["response_kind"], "message": result["message"],
                            "component": "generation" if result["response_kind"] == "GENERATION_UNAVAILABLE" else "retrieval",
                            "retryable": True,
                        }, 3)
                        return
                    jobs.judge(payload.text, result)
                    yield _sse("validated_content", {
                        key: result.get(key) for key in (
                            "response_kind", "message", "limitation", "actions", "route",
                        )
                    }, 3)
                    sequence = 4
                    for citation in result.get("citations", []):
                        yield _sse("evidence", citation, sequence)
                        sequence += 1
                    yield _sse("done", {
                        "response_kind": result["response_kind"],
                        "provider": result.get("provider"), "model": result.get("model"),
                        "corpus_version": result.get("corpus_version"),
                        "state_version": state.state_version,
                        "inactivity_expires_in_seconds": settings.session_ttl_seconds,
                    }, sequence)
                finally:
                    model_capacity.release()

            return StreamingResponse(
                events(), media_type="text/event-stream",
                headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
            )
        except Exception:
            # Permission and quota exceptions are handled before streaming starts.
            raise

    @app.get("/v1/assessments/questionnaire")
    async def assessment_questionnaire(token: str = Depends(bearer)):
        """Return the questionnaire contract to an authorized private session."""
        state = sessions.authorize(token, renew=False, now=now() if now else None)
        return {
            "api_version": API_VERSION, "deployment_mode": settings.deployment_mode,
            "state_version": state.state_version,
            "inactivity_expires_in_seconds": settings.session_ttl_seconds,
            **assessment.requirements(),
        }

    @app.post("/v1/assessments")
    async def submit_assessment(payload: AssessmentRequest, token: str = Depends(bearer)):
        """Return validated model scores and start their background LLM explanation."""
        sessions.authorize(token, renew=False, now=now() if now else None)
        if payload.questionnaire_version != assessment.requirements()["questionnaire_version"]:
            return _error("QUESTIONNAIRE_VERSION_UNSUPPORTED",
                          "The questionnaire has changed. Refresh and complete the current version.",
                          "questionnaire", 409)
        started = time.monotonic()
        if not model_capacity.acquire():
            return _error("MODEL_CAPACITY_EXHAUSTED", "The model service is busy. Try again.",
                          "capacity", 503, retryable=True)
        try:
            try:
                state = sessions.consume_assessment_operation(
                    token, now=now() if now else None,
                )
            except OverflowError:
                return _error("GLOBAL_USAGE_LIMIT", USAGE_LIMIT_MESSAGE, "quota", 429)
            try:
                result = await asyncio.wait_for(
                    asyncio.to_thread(
                        assessment.assess, payload.questionnaire_version, payload.answers,
                        deployment_mode=settings.deployment_mode,
                        timeout_seconds=settings.request_timeout_seconds,
                    ),
                    timeout=settings.request_timeout_seconds,
                )
                if result.get("status") == "assessment_ready":
                    monitor.record("assessment_inference", "ready", time.monotonic() - started)
                    drift_features = getattr(assessment, "drift_features", None)
                    if drift_features is not None:
                        # Input monitoring must never fail an assessment that already succeeded.
                        try:
                            monitor.record_inputs(
                                drift_features(payload.questionnaire_version, payload.answers))
                        except Exception:
                            monitor.record("input_monitoring", "error", 0)
                    assessment_results.put(token, result)
                    explainer = getattr(conversation, "explain_assessment", None)
                    if explainer is not None:
                        jobs.explain(result)
                    else:
                        result["explanation_status"] = "unavailable"
            except TimeoutError:
                monitor.record("assessment_inference", "timeout", time.monotonic() - started)
                return _error("REQUEST_DEADLINE_EXPIRED", "The assessment timed out safely.",
                              "workflow", 504, retryable=True)
            except Exception:
                monitor.record("assessment_inference", "error", time.monotonic() - started)
                return _error("INFERENCE_UNAVAILABLE", "The assessment is unavailable.",
                              "inference", 503, retryable=True)
        finally:
            model_capacity.release()
        status = result["status"]
        status_code = 200
        if status in {"questionnaire_incomplete", "questionnaire_invalid"}:
            status_code = 422
        elif status not in {"assessment_ready"}:
            status_code = 503
        return JSONResponse(status_code=status_code, content={
            "api_version": API_VERSION, "deployment_mode": settings.deployment_mode,
            "state_version": state.state_version,
            "inactivity_expires_in_seconds": settings.session_ttl_seconds,
            **result,
        })

    @app.get("/v1/assessments/latest")
    async def latest_assessment(token: str = Depends(bearer)):
        """Return the latest assessment cached for the authorized session."""
        sessions.authorize(token, renew=False, now=now() if now else None)
        cached = assessment_results.get(token)
        if cached is None:
            return _error("ASSESSMENT_NOT_FOUND", "No assessment is available in this session.",
                          "assessment", 404)
        return {"api_version": API_VERSION, **cached}

    @app.get("/v1/evaluations/dashboard")
    async def evaluation_dashboard(request: Request):
        """Expose read-only aggregate evaluation telemetry to local clients."""
        if (not request.client or request.client.host not in {"127.0.0.1", "::1", "testclient"}
                or request.headers.get("x-forwarded-for")):
            return _error("LOCAL_ACCESS_REQUIRED", "The evaluation dashboard is local-only.",
                          "authorization", 403)
        return await asyncio.to_thread(monitor.snapshot)

    @app.post("/v1/assessments/explanation")
    async def retry_explanation(token: str = Depends(bearer)):
        """Retry only the LLM explanation for an authorized cached assessment result."""
        sessions.authorize(token, renew=False, now=now() if now else None)
        cached = assessment_results.get(token)
        if cached is None:
            return _error("ASSESSMENT_NOT_FOUND", "No assessment is available in this session.",
                          "assessment", 404)
        result = cached
        if result.get("explanation_status") != "pending":
            sessions.consume_model_operation(token, now=now() if now else None)
            jobs.explain(result)
        return {"api_version": API_VERSION, **result}

    return app


def app_factory() -> FastAPI:
    """Uvicorn factory; secrets and origins come from environment variables."""
    return create_app(BackendSettings.from_env())


def _sse(event: str, data: dict[str, Any], sequence: int) -> str:
    """Serialize a typed event with its sequence identifier for SSE transport."""
    payload = json.dumps(data, separators=(",", ":"), ensure_ascii=True)
    return f"id: {sequence}\nevent: {event}\ndata: {payload}\n\n"
