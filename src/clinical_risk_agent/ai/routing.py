"""Typed, non-persistent LangGraph preflight and route selection.

This graph deliberately authorizes no tool. The downstream assessment, evidence,
and generation subgraphs are separate release-gated work. External safety,
language, and intent ports must be supplied; there is no permissive default.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from math import isfinite
from typing import Protocol, TypedDict

from langgraph.graph import END, START, StateGraph


class RequestKind(str, Enum):
    FREE_TEXT = "free_text"
    STRUCTURED_ASSESSMENT = "structured_assessment"


class SafetyCategory(str, Enum):
    EMERGENCY_REDIRECTION = "EMERGENCY_REDIRECTION"
    CRITICAL_SAFETY_REDIRECTION = "CRITICAL_SAFETY_REDIRECTION"
    ACUTE_DISTRESS_REDIRECTION = "ACUTE_DISTRESS_REDIRECTION"
    STATE_INELIGIBLE_MINOR = "STATE_INELIGIBLE_MINOR"
    THIRD_PARTY_REFUSAL = "THIRD_PARTY_REFUSAL"
    DIAGNOSTIC_REFUSAL = "DIAGNOSTIC_REFUSAL"
    PRESCRIPTIVE_REFUSAL = "PRESCRIPTIVE_REFUSAL"
    ALLOW_NORMAL_PROCESSING = "ALLOW_NORMAL_PROCESSING"


class LanguageStatus(str, Enum):
    SUPPORTED_ENGLISH = "SUPPORTED_ENGLISH"
    UNSUPPORTED_LANGUAGE = "UNSUPPORTED_LANGUAGE"
    UNCERTAIN_LANGUAGE = "UNCERTAIN_LANGUAGE"


class Intent(str, Enum):
    RISK_ASSESSMENT = "risk_assessment"
    EXPLAIN_MY_RISK = "explain_my_risk"
    SCIENTIFIC_QUESTION = "scientific_question"
    MENTAL_HEALTH_EDUCATION = "mental_health_education"
    GENERAL_CONVERSATION = "general_conversation"
    UNSUPPORTED_OR_UNSAFE = "unsupported_or_unsafe"


class Route(str, Enum):
    REJECT_SESSION = "reject_session"
    REJECT_MODE = "reject_mode"
    SAFETY_TERMINAL = "safety_terminal"
    LANGUAGE_TERMINAL = "language_terminal"
    CLARIFY_INTENT = "clarify_intent"
    ASSESSMENT_REDIRECTION = "assessment_redirection"
    VALIDATE_ASSESSMENT = "validate_assessment"
    LOAD_PRIOR_RESULT = "load_prior_result"
    SCIENTIFIC_RETRIEVAL = "scientific_retrieval"
    GENERAL_GENERATION = "general_generation"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True, slots=True)
class PreflightRequest:
    """Volatile input. Only the backend may assert session/view authorization."""

    kind: RequestKind
    deployment_mode: str
    session_valid: bool
    text: str | None = field(default=None, repr=False)
    assessment_view_authorized: bool = False

    def __post_init__(self) -> None:
        if (type(self.session_valid) is not bool
                or type(self.assessment_view_authorized) is not bool
                or not isinstance(self.deployment_mode, str)):
            raise ValueError("Invalid preflight authorization shape")
        if self.kind is RequestKind.FREE_TEXT:
            if (not isinstance(self.text, str) or not self.text.strip()
                    or self.assessment_view_authorized):
                raise ValueError("Invalid free-text request shape")
        elif self.kind is RequestKind.STRUCTURED_ASSESSMENT:
            if self.text is not None:
                raise ValueError("Structured assessment cannot contain free text")
        else:
            raise ValueError("Unknown request kind")


@dataclass(frozen=True, slots=True)
class SafetyDecision:
    category: SafetyCategory
    policy_version: str
    rationale_code: str


@dataclass(frozen=True, slots=True)
class LanguageDecision:
    status: LanguageStatus
    detector_version: str
    rationale_code: str


@dataclass(frozen=True, slots=True)
class IntentDecision:
    intent: Intent
    calibrated_confidence: float
    requires_clarification: bool
    model_id: str
    model_sha256: str
    calibration_version: str
    router_version: str
    rationale_code: str


@dataclass(frozen=True, slots=True)
class RouteDecision:
    """Next workflow stage, not an authorization to invoke any tool."""

    route: Route
    safety_category: SafetyCategory | None
    language_status: LanguageStatus | None
    intent: Intent | None
    allow_inference: bool = False
    allow_rag: bool = False
    allow_llm: bool = False


class SafetyPort(Protocol):
    def evaluate(self, request: PreflightRequest) -> SafetyDecision: ...


class LanguagePort(Protocol):
    def classify(self, text: str) -> LanguageDecision: ...


class IntentPort(Protocol):
    def classify(self, text: str) -> IntentDecision: ...


class _State(TypedDict, total=False):
    request: PreflightRequest
    safety: SafetyDecision
    language: LanguageDecision
    intent: IntentDecision
    route: Route


def external_tracing_enabled() -> bool:
    """Reject settings that could export volatile graph state."""
    return any(os.getenv(key, "").lower() in {"true", "1", "yes"}
               for key in ("LANGSMITH_TRACING", "LANGCHAIN_TRACING_V2"))


class RoutingGraph:
    """One-turn, no-checkpointer preflight; state never leaves volatile memory."""

    def __init__(self, safety: SafetyPort, language: LanguagePort, intent: IntentPort) -> None:
        if safety is None or language is None or intent is None:
            raise ValueError("Safety, language and intent ports are required")
        self._safety = safety
        self._language = language
        self._intent = intent
        graph = StateGraph(_State)
        graph.add_node("validate_transport_and_session", self._validate)
        graph.add_node("intercept_safety", self._intercept_safety)
        graph.add_node("detect_language", self._detect_language)
        graph.add_node("classify_intent", self._classify_intent)
        graph.add_node("select_route", self._select_route)
        graph.add_edge(START, "validate_transport_and_session")
        graph.add_conditional_edges(
            "validate_transport_and_session", self._after_validation,
            {"safety": "intercept_safety", "end": END},
        )
        graph.add_conditional_edges(
            "intercept_safety", self._after_safety,
            {"language": "detect_language", "route": "select_route", "end": END},
        )
        graph.add_conditional_edges(
            "detect_language", self._after_language,
            {"intent": "classify_intent", "end": END},
        )
        graph.add_edge("classify_intent", "select_route")
        graph.add_edge("select_route", END)
        self._graph = graph.compile()

    @staticmethod
    def _validate(state: _State) -> _State:
        request = state["request"]
        if request.deployment_mode != "prototype_demo":
            return {"route": Route.REJECT_MODE}
        if not request.session_valid:
            return {"route": Route.REJECT_SESSION}
        return {}

    @staticmethod
    def _after_validation(state: _State) -> str:
        return "end" if "route" in state else "safety"

    def _intercept_safety(self, state: _State) -> _State:
        decision = self._safety.evaluate(state["request"])
        if (not isinstance(decision, SafetyDecision)
                or not isinstance(decision.category, SafetyCategory)
                or not decision.policy_version or not decision.rationale_code):
            raise TypeError("Safety port returned an invalid decision")
        if decision.category is not SafetyCategory.ALLOW_NORMAL_PROCESSING:
            return {"safety": decision, "route": Route.SAFETY_TERMINAL}
        return {"safety": decision}

    @staticmethod
    def _after_safety(state: _State) -> str:
        if "route" in state:
            return "end"
        if state["request"].kind is RequestKind.STRUCTURED_ASSESSMENT:
            return "route"
        return "language"

    def _detect_language(self, state: _State) -> _State:
        decision = self._language.classify(state["request"].text or "")
        if (not isinstance(decision, LanguageDecision)
                or not isinstance(decision.status, LanguageStatus)
                or not decision.detector_version or not decision.rationale_code):
            raise TypeError("Language port returned an invalid decision")
        if decision.status is not LanguageStatus.SUPPORTED_ENGLISH:
            return {"language": decision, "route": Route.LANGUAGE_TERMINAL}
        return {"language": decision}

    @staticmethod
    def _after_language(state: _State) -> str:
        return "end" if "route" in state else "intent"

    def _classify_intent(self, state: _State) -> _State:
        decision = self._intent.classify(state["request"].text or "")
        if not isinstance(decision, IntentDecision):
            raise TypeError("Intent port returned an invalid decision")
        if (not isinstance(decision.intent, Intent)
                or type(decision.requires_clarification) is not bool
                or not decision.model_id or not decision.model_sha256
                or not decision.calibration_version or not decision.router_version
                or not isinstance(decision.calibrated_confidence, (int, float))
                or isinstance(decision.calibrated_confidence, bool)
                or not isfinite(decision.calibrated_confidence)
                or not 0.0 <= decision.calibrated_confidence <= 1.0):
            raise ValueError("Intent decision lacks calibrated provenance")
        return {"intent": decision}

    @staticmethod
    def _select_route(state: _State) -> _State:
        request = state["request"]
        if request.kind is RequestKind.STRUCTURED_ASSESSMENT:
            return {"route": (Route.VALIDATE_ASSESSMENT if request.assessment_view_authorized
                              else Route.UNSUPPORTED)}
        decision = state["intent"]
        if decision.requires_clarification or decision.calibrated_confidence < 0.85:
            return {"route": Route.CLARIFY_INTENT}
        return {"route": {
            Intent.RISK_ASSESSMENT: Route.ASSESSMENT_REDIRECTION,
            Intent.EXPLAIN_MY_RISK: Route.LOAD_PRIOR_RESULT,
            Intent.SCIENTIFIC_QUESTION: Route.SCIENTIFIC_RETRIEVAL,
            Intent.MENTAL_HEALTH_EDUCATION: Route.SCIENTIFIC_RETRIEVAL,
            Intent.GENERAL_CONVERSATION: Route.GENERAL_GENERATION,
            Intent.UNSUPPORTED_OR_UNSAFE: Route.UNSUPPORTED,
        }[decision.intent]}

    def advance(self, request: PreflightRequest) -> RouteDecision:
        # No runtime user content may be sent to an external trace service.
        if external_tracing_enabled():
            raise RuntimeError("External tracing is forbidden for runtime requests")
        state = self._graph.invoke({"request": request})
        return RouteDecision(
            route=state["route"],
            safety_category=state["safety"].category if "safety" in state else None,
            language_status=state["language"].status if "language" in state else None,
            intent=state["intent"].intent if "intent" in state else None,
        )
