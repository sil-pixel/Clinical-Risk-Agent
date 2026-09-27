"""FastAPI boundary for the bounded research RAG prototype."""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Literal, Protocol

from fastapi import Depends, FastAPI, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ConfigDict, Field

from clinical_risk_agent.ai import (
    ProtectedConversationOrchestrator,
    PrototypeIntentPort,
    PrototypeLanguagePort,
    PrototypeSafetyPort,
    RoutingGraph,
    create_generator,
)
from clinical_risk_agent.rag.answering import CURATED_QUESTIONS
from clinical_risk_agent.rag.runtime import ResearchRuntime

from .sessions import SessionStore
from .settings import BackendSettings

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
    def close(self) -> None: ...


class ConversationService(Protocol):
    def handle(self, text: str, *, deployment_mode: str,
               session_valid: bool) -> dict[str, Any]: ...
    def close(self) -> None: ...


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
    sessions = SessionStore(
        settings.session_signing_key, ttl_seconds=settings.session_ttl_seconds,
        max_sessions=settings.max_active_sessions,
        hourly_limit=settings.model_turns_per_hour,
        daily_limit=settings.model_turns_per_day,
        global_daily_limit=settings.global_model_operations_per_day,
        create_limit=settings.session_creations_per_network_hour,
    )
    model_capacity = CapacityGate(settings.max_model_concurrency)
    http_capacity = CapacityGate(settings.max_http_concurrency)
    now = clock

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        try:
            yield
        finally:
            research.close()
            close_conversation = getattr(conversation, "close", None)
            if close_conversation is not None:
                close_conversation()

    app = FastAPI(
        title="Clinical Risk Research API", version="0.1.0", lifespan=lifespan,
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
        if code in {"hourly_quota_exhausted", "daily_quota_exhausted"}:
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
            except TimeoutError:
                return _error("REQUEST_DEADLINE_EXPIRED", "The request timed out safely.",
                              "workflow", 504, retryable=True)
            except Exception:
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
        return JSONResponse(status_code=status_code, content=body)

    return app


def app_factory() -> FastAPI:
    """Uvicorn factory; secrets and origins come from environment variables."""
    return create_app(BackendSettings.from_env())
