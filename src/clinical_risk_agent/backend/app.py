"""FastAPI boundary for the bounded research RAG prototype."""

from __future__ import annotations

import asyncio
import hashlib
import json
import threading
import time
from collections.abc import Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Literal, Protocol

from fastapi import Depends, FastAPI, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.responses import StreamingResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ConfigDict, Field

from clinical_risk_agent.ai import (
    AssessmentStatus,
    AssessmentSubmission,
    MLAssessmentAdapter,
    PreflightRequest,
    ProtectedConversationOrchestrator,
    ProtectedAssessmentGraph,
    PrototypeIntentPort,
    PrototypeLanguagePort,
    PrototypeSafetyPort,
    RequestKind,
    RoutingGraph,
    create_generator,
)
from clinical_risk_agent.inference import DCMFNetPredictor, questionnaire_requirements
from clinical_risk_agent.rag.answering import CURATED_QUESTIONS
from clinical_risk_agent.rag.runtime import ResearchRuntime

from .sessions import SessionStore
from .settings import BackendSettings
from .monitoring import Monitor

API_VERSION = "v1"
USAGE_LIMIT_MESSAGE = (
    "This research demo has reached its current usage limit. Assessments and evidence-based "
    "answers are temporarily unavailable. Please try again after the displayed reset time. "
    "No calculation has been performed."
)


class ResearchService(Protocol):
    def ready(self) -> tuple[bool, str | None]: ...
    def answer(self, question_id: str) -> dict[str, Any]: ...
    def answer_text(self, question: str) -> dict[str, Any]: ...
    def search_general(self, question: str) -> dict[str, Any]: ...
    def close(self) -> None: ...


class ConversationService(Protocol):
    def handle(self, text: str, *, deployment_mode: str,
               session_valid: bool) -> dict[str, Any]: ...
    def explain_assessment(self, result: dict[str, Any]) -> dict[str, Any]: ...
    def close(self) -> None: ...


class AssessmentService(Protocol):
    def requirements(self) -> dict[str, Any]: ...
    def assess(self, version: str, answers: dict[str, str],
               *, deployment_mode: str, timeout_seconds: float) -> dict[str, Any]: ...


class LocalAssessmentService:
    """Lazily loads both pinned DCMFNet artifacts and the protected graph."""

    def __init__(self, root: Path) -> None:
        self._root = root
        self._graph: ProtectedAssessmentGraph | None = None
        self._lock = threading.Lock()

    def _load(self) -> ProtectedAssessmentGraph:
        with self._lock:
            if self._graph is None:
                artifact_dir = self._root / "model_artifacts"
                positive = DCMFNetPredictor(
                    artifact_dir / "dcmfnet_pos.pt",
                    artifact_dir / "dcmfnet_pos.metadata.json",
                )
                negative = DCMFNetPredictor(
                    artifact_dir / "dcmfnet_neg.pt",
                    artifact_dir / "dcmfnet_neg.metadata.json",
                )
                routing = RoutingGraph(
                    PrototypeSafetyPort(), PrototypeLanguagePort(), PrototypeIntentPort(),
                )
                self._graph = ProtectedAssessmentGraph(
                    routing, MLAssessmentAdapter(positive, negative),
                )
            return self._graph

    def warmup(self) -> None:
        self._load()

    @staticmethod
    def requirements() -> dict[str, Any]:
        contract = questionnaire_requirements()
        return {
            "questionnaire_version": contract.version,
            "questions": [
                {"question_id": item.question_id, "option_ids": list(item.option_ids)}
                for item in contract.questions
            ],
        }

    def assess(self, version: str, answers: dict[str, str],
               *, deployment_mode: str, timeout_seconds: float) -> dict[str, Any]:
        submission = AssessmentSubmission(
            PreflightRequest(
                RequestKind.STRUCTURED_ASSESSMENT, deployment_mode, True,
                assessment_view_authorized=True,
            ),
            version,
            answers,
            time.monotonic() + min(timeout_seconds, 59.0),
        )
        outcome = self._load().run(submission)
        body: dict[str, Any] = {
            "response_kind": outcome.status.value.upper(),
            "status": outcome.status.value,
        }
        if outcome.validation is not None:
            body["missing_question_ids"] = list(outcome.validation.missing_question_ids)
            body["invalid_question_ids"] = list(outcome.validation.invalid_question_ids)
            body["unknown_question_ids"] = list(outcome.validation.unknown_question_ids)
        if outcome.status is AssessmentStatus.READY and outcome.display is not None:
            body.update({
                "response_kind": "ASSESSMENT_RESULT",
                "result": {
                    "positive_symptom_research_probability": outcome.display.positive_percent,
                    "negative_symptom_research_probability": outcome.display.negative_percent,
                    "generic_profile_version": outcome.display.generic_profile_version,
                    "synthetic_training_data": outcome.display.synthetic_training_data,
                },
                "prediction_note": (
                    "This is a prediction, not a causal explanation. The model evaluates all "
                    "105 inputs together; no single answer can be identified as the cause of "
                    "the result. Validated feature importance is not available for this result."
                ),
                "limitation": (
                    "Portfolio research demonstration only; not validated for individual care, "
                    "diagnosis, screening, or treatment decisions."
                ),
            })
        elif outcome.safe_message:
            body["message"] = outcome.safe_message
        return body


class LocalResearchService:
    """Loads the two pinned encoders and read-only Qdrant store once per process."""

    def __init__(self, root: Path) -> None:
        self._root = root
        self._runtime: ResearchRuntime | None = None
        self._lock = threading.Lock()

    def _load(self) -> ResearchRuntime:
        with self._lock:
            if self._runtime is None:
                self._runtime = ResearchRuntime(self._root)
            return self._runtime

    def ready(self) -> tuple[bool, str | None]:
        try:
            return True, self._load().corpus_version
        except Exception:
            return False, None

    def answer(self, question_id: str) -> dict[str, Any]:
        return self._load().answerer.answer_public_id(question_id)

    def answer_text(self, question: str) -> dict[str, Any]:
        return self._load().answerer.answer(question)

    def search_general(self, question: str) -> dict[str, Any]:
        return self._load().search_general(question)

    def close(self) -> None:
        if self._runtime is not None:
            self._runtime.close()


class ResearchAnswerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    question_id: str = Field(pattern=r"^rq_0[1-5]$")


class MessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    kind: Literal["free_text"]
    text: str = Field(min_length=1, max_length=500)


class AssessmentAttestations(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    age_18_or_over: Literal[True]
    self_assessment: Literal[True]
    research_only_consent: Literal[True]


class AssessmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    questionnaire_version: str = Field(min_length=1, max_length=80)
    answers: dict[str, str] = Field(max_length=85)
    attestations: AssessmentAttestations


class CapacityGate:
    def __init__(self, limit: int) -> None:
        self._limit = limit
        self._active = 0
        self._lock = threading.Lock()

    def acquire(self) -> bool:
        with self._lock:
            if self._active >= self._limit:
                return False
            self._active += 1
            return True

    def release(self) -> None:
        with self._lock:
            self._active -= 1


def _error(code: str, message: str, component: str, status: int,
           *, retryable: bool = False) -> JSONResponse:
    return JSONResponse(status_code=status, headers={"Cache-Control": "no-store"}, content={
        "api_version": API_VERSION,
        "error": {"code": code, "message": message, "component": component,
                  "retryable": retryable},
    })


def create_app(settings: BackendSettings, *, service: ResearchService | None = None,
               conversation: ConversationService | None = None,
               assessment: AssessmentService | None = None,
               clock: Callable[[], float] | None = None) -> FastAPI:
    """Compose the API. Authorization is derived only from transport state."""
    research = service or LocalResearchService(settings.root)
    if conversation is None:
        generator = None
        if settings.llm_provider and settings.llm_model and settings.llm_api_key:
            generator = create_generator(
                settings.llm_provider, settings.llm_api_key, settings.llm_model,
            )
        conversation = ProtectedConversationOrchestrator(
            RoutingGraph(
                PrototypeSafetyPort(), PrototypeLanguagePort(), PrototypeIntentPort(),
            ),
            research,
            generator,
        )
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
    monitor = Monitor(settings.root)
    assessment_results: dict[str, tuple[float, dict[str, Any]]] = {}
    explanation_tasks: set[asyncio.Task] = set()
    quality_tasks: set[asyncio.Task] = set()
    quality_capacity = CapacityGate(1)
    explanation_capacity = asyncio.Semaphore(settings.max_model_concurrency)

    def evaluate_live(text: str, result: dict[str, Any]):
        if result.get("response_kind") not in {"GROUNDED_ANSWER", "GENERAL_EDUCATION", "CONVERSATION"}:
            return
        evaluator = getattr(conversation, "evaluate_response", None)
        if evaluator is None or not result.get("model") or not quality_capacity.acquire():
            monitor.quality_finished("skipped", result["response_kind"])
            return
        monitor.quality_started()

        async def evaluate():
            started = time.monotonic()
            try:
                verdict = await asyncio.to_thread(evaluator, text, result)
                monitor.quality_finished("scored", result["response_kind"], verdict)
                monitor.record("live_quality_judge", "scored", time.monotonic() - started)
            except Exception:
                monitor.quality_finished("error", result["response_kind"])
                monitor.record("live_quality_judge", "error", time.monotonic() - started)
            finally:
                quality_capacity.release()

        task = asyncio.create_task(evaluate())
        quality_tasks.add(task)
        task.add_done_callback(quality_tasks.discard)

    def assessment_key(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    def prune_assessments() -> None:
        cutoff = time.monotonic() - settings.session_ttl_seconds
        for key, (created, _) in tuple(assessment_results.items()):
            if created < cutoff:
                del assessment_results[key]

    async def explain_result(result: dict[str, Any]):
        started = time.monotonic()
        async def generate():
            async with explanation_capacity:
                return await asyncio.to_thread(conversation.explain_assessment, dict(result["result"]))
        try:
            explanation = await asyncio.wait_for(
                generate(),
                timeout=settings.request_timeout_seconds,
            )
            result.update({
                "explanation": explanation["message"],
                "explanation_provider": explanation.get("provider"),
                "explanation_model": explanation.get("model"),
                "explanation_generated_by_llm": explanation.get("generated_by_llm", False),
                "explanation_status": "ready" if explanation.get("generated_by_llm") else "unavailable",
            })
            monitor.record("assessment_explanation", result["explanation_status"],
                           time.monotonic() - started)
        except Exception:
            result["explanation_status"] = "unavailable"
            result["explanation"] = "Your scores are ready, but the explanation is temporarily unavailable."
            monitor.record("assessment_explanation", "error", time.monotonic() - started)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        try:
            warmup = getattr(assessment, "warmup", None)
            if warmup is not None:
                started = time.monotonic()
                await asyncio.to_thread(warmup)
                monitor.record("model_startup", "ready", time.monotonic() - started)
            yield
        finally:
            for task in explanation_tasks | quality_tasks:
                task.cancel()
            if explanation_tasks or quality_tasks:
                await asyncio.gather(*explanation_tasks, *quality_tasks, return_exceptions=True)
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
        if not http_capacity.acquire():
            return _error("HTTP_CAPACITY_EXHAUSTED", "The research demo is at capacity.",
                          "capacity", 503, retryable=True)
        try:
            return await _bounded_transport(request, call_next)
        finally:
            http_capacity.release()

    async def _bounded_transport(request: Request, call_next):
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
        if not authorization or not authorization.startswith("Bearer "):
            raise PermissionError("missing_session")
        return authorization[7:]

    @app.exception_handler(PermissionError)
    async def permission_error(_request: Request, error: PermissionError):
        code = str(error)
        if code in {"hourly_quota_exhausted", "daily_quota_exhausted",
                    "assessment_quota_exhausted"}:
            return _error("SESSION_QUOTA_EXHAUSTED", USAGE_LIMIT_MESSAGE, "quota", 429)
        return _error("SESSION_INVALID", "Session is missing, invalid, or expired.",
                      "session", 401)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, _error_value: RequestValidationError):
        return _error("INVALID_REQUEST", "Request validation failed.", "transport", 422)

    @app.get("/health/live")
    async def live():
        return {"status": "live", "api_version": API_VERSION}

    @app.get("/health/ready")
    async def ready():
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
        sessions.delete(token)
        assessment_results.pop(assessment_key(token), None)
        return {"api_version": API_VERSION, "status": "session_cleared"}

    @app.get("/v1/research/questions")
    async def list_questions(token: str = Depends(bearer)):
        # Static-content reads do not count as explicit user activity.
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
        started = time.monotonic()
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
                    ),
                    timeout=settings.request_timeout_seconds,
                )
                monitor.record("chat", result["response_kind"], time.monotonic() - started)
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
        evaluate_live(payload.text, result)
        return JSONResponse(status_code=status_code, content=body)

    @app.post("/v1/messages:stream")
    async def stream_message(payload: MessageRequest, token: str = Depends(bearer)):
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
                started = time.monotonic()
                try:
                    yield _sse("status", {"phase": "protected_preflight"}, 1)
                    yield _sse("status", {"phase": "retrieval_and_generation"}, 2)
                    try:
                        result = await asyncio.wait_for(
                            asyncio.to_thread(
                                conversation.handle, payload.text,
                                deployment_mode=settings.deployment_mode, session_valid=True,
                            ),
                            timeout=settings.request_timeout_seconds,
                        )
                        monitor.record("chat", result["response_kind"], time.monotonic() - started)
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
                    evaluate_live(payload.text, result)
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
        state = sessions.authorize(token, renew=False, now=now() if now else None)
        return {
            "api_version": API_VERSION, "deployment_mode": settings.deployment_mode,
            "state_version": state.state_version,
            "inactivity_expires_in_seconds": settings.session_ttl_seconds,
            **assessment.requirements(),
        }

    @app.post("/v1/assessments")
    async def submit_assessment(payload: AssessmentRequest, token: str = Depends(bearer)):
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
                    prune_assessments()
                    assessment_results[assessment_key(token)] = (time.monotonic(), result)
                    explainer = getattr(conversation, "explain_assessment", None)
                    if explainer is not None:
                        result["explanation_status"] = "pending"
                        task = asyncio.create_task(explain_result(result))
                        explanation_tasks.add(task)
                        task.add_done_callback(explanation_tasks.discard)
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
        sessions.authorize(token, renew=False, now=now() if now else None)
        prune_assessments()
        cached = assessment_results.get(assessment_key(token))
        if cached is None:
            return _error("ASSESSMENT_NOT_FOUND", "No assessment is available in this session.",
                          "assessment", 404)
        return {"api_version": API_VERSION, **cached[1]}

    @app.get("/v1/evaluations/dashboard")
    async def evaluation_dashboard(request: Request):
        if (not request.client or request.client.host not in {"127.0.0.1", "::1", "testclient"}
                or request.headers.get("x-forwarded-for")):
            return _error("LOCAL_ACCESS_REQUIRED", "The evaluation dashboard is local-only.",
                          "authorization", 403)
        return await asyncio.to_thread(monitor.snapshot)

    @app.post("/v1/assessments/explanation")
    async def retry_explanation(token: str = Depends(bearer)):
        sessions.authorize(token, renew=False, now=now() if now else None)
        prune_assessments()
        cached = assessment_results.get(assessment_key(token))
        if cached is None:
            return _error("ASSESSMENT_NOT_FOUND", "No assessment is available in this session.",
                          "assessment", 404)
        result = cached[1]
        if result.get("explanation_status") != "pending":
            sessions.consume_model_operation(token, now=now() if now else None)
            result["explanation_status"] = "pending"
            result.pop("explanation", None)
            task = asyncio.create_task(explain_result(result))
            explanation_tasks.add(task)
            task.add_done_callback(explanation_tasks.discard)
        return {"api_version": API_VERSION, **result}

    return app


def app_factory() -> FastAPI:
    """Uvicorn factory; secrets and origins come from environment variables."""
    return create_app(BackendSettings.from_env())


def _sse(event: str, data: dict[str, Any], sequence: int) -> str:
    payload = json.dumps(data, separators=(",", ":"), ensure_ascii=True)
    return f"id: {sequence}\nevent: {event}\ndata: {payload}\n\n"
    RequestKind,
