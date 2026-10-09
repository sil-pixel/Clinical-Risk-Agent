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
from collections.abc import Callable
from typing import Protocol, TypedDict

from langgraph.graph import END, START, StateGraph


# Free-text intents below this calibrated confidence are routed to clarification.
ROUTING_CONFIDENCE_THRESHOLD = 0.85


class RequestKind(str, Enum):
    """Distinguish free-text requests from structured assessment submissions."""
    FREE_TEXT = "free_text"
    STRUCTURED_ASSESSMENT = "structured_assessment"


class SafetyCategory(str, Enum):
    """Enumerate safety decisions that allow processing or require redirection."""
    EMERGENCY_REDIRECTION = "EMERGENCY_REDIRECTION"
    CRITICAL_SAFETY_REDIRECTION = "CRITICAL_SAFETY_REDIRECTION"
    ACUTE_DISTRESS_REDIRECTION = "ACUTE_DISTRESS_REDIRECTION"
    STATE_INELIGIBLE_MINOR = "STATE_INELIGIBLE_MINOR"
    THIRD_PARTY_REFUSAL = "THIRD_PARTY_REFUSAL"
    DIAGNOSTIC_REFUSAL = "DIAGNOSTIC_REFUSAL"
    PRESCRIPTIVE_REFUSAL = "PRESCRIPTIVE_REFUSAL"
    ALLOW_NORMAL_PROCESSING = "ALLOW_NORMAL_PROCESSING"


class LanguageStatus(str, Enum):
    """Enumerate English support and uncertain or unsupported language outcomes."""
    SUPPORTED_ENGLISH = "SUPPORTED_ENGLISH"
    UNSUPPORTED_LANGUAGE = "UNSUPPORTED_LANGUAGE"
    UNCERTAIN_LANGUAGE = "UNCERTAIN_LANGUAGE"


class Intent(str, Enum):
    """Enumerate the user intents understood by the protected router."""
    RISK_ASSESSMENT = "risk_assessment"
    EXPLAIN_MY_RISK = "explain_my_risk"
    SCIENTIFIC_QUESTION = "scientific_question"
    MENTAL_HEALTH_EDUCATION = "mental_health_education"
    GENERAL_CONVERSATION = "general_conversation"
    UNSUPPORTED_OR_UNSAFE = "unsupported_or_unsafe"


# A clarification may name the router's best guess when it is at least this confident and
# the text resembles the reference utterances. A user can confirm only such a suggestion,
# and never an unsupported or unsafe intent.
SUGGESTION_MIN_CONFIDENCE = 0.5
CONFIRMABLE_INTENTS = frozenset({
    Intent.RISK_ASSESSMENT, Intent.EXPLAIN_MY_RISK, Intent.SCIENTIFIC_QUESTION,
    Intent.MENTAL_HEALTH_EDUCATION, Intent.GENERAL_CONVERSATION,
})


class Route(str, Enum):
    """Enumerate permitted next stages of the protected request workflow."""
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
    # Client claim that the user accepted a clarification suggestion; verified by the graph.
    confirmed_intent: Intent | None = None

    def __post_init__(self) -> None:
        """Validate preflight request shape and backend-supplied authorization flags."""
        if (type(self.session_valid) is not bool
                or type(self.assessment_view_authorized) is not bool
                or not isinstance(self.deployment_mode, str)):
            raise ValueError("Invalid preflight authorization shape")
        if self.kind is RequestKind.FREE_TEXT:
            if (not isinstance(self.text, str) or not self.text.strip()
                    or self.assessment_view_authorized):
                raise ValueError("Invalid free-text request shape")
            if (self.confirmed_intent is not None
                    and self.confirmed_intent not in CONFIRMABLE_INTENTS):
                raise ValueError("Intent cannot be confirmed")
        elif self.kind is RequestKind.STRUCTURED_ASSESSMENT:
            if self.text is not None or self.confirmed_intent is not None:
                raise ValueError("Structured assessment cannot contain free text")
        else:
            raise ValueError("Unknown request kind")


@dataclass(frozen=True, slots=True)
class SafetyDecision:
    """Carry a safety category with policy provenance and a stable rationale code."""
    category: SafetyCategory
    policy_version: str
    rationale_code: str


@dataclass(frozen=True, slots=True)
class LanguageDecision:
    """Carry a language classification with detector provenance and rationale."""
    status: LanguageStatus
    detector_version: str
    rationale_code: str


@dataclass(frozen=True, slots=True)
class IntentDecision:
    """Carry an intent prediction with confidence and model-calibration provenance."""
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
    # Router's best guess, offered to the user when the route is CLARIFY_INTENT.
    suggested_intent: Intent | None = None
    allow_rag: bool = False
    allow_llm: bool = False


class SafetyPort(Protocol):
    """Define safety classification for protected preflight requests."""
    def evaluate(self, request: PreflightRequest) -> SafetyDecision:
        """Evaluate the safety category of a protected preflight request."""
        ...


class LanguagePort(Protocol):
    """Define language classification for transient input text."""
    def classify(self, text: str) -> LanguageDecision:
        """Determine whether the transient input uses supported English."""
        ...


class IntentPort(Protocol):
    """Define intent classification for transient input text."""
    def classify(self, text: str) -> IntentDecision:
        """Determine intent and calibrated routing confidence for transient input."""
        ...


class _State(TypedDict, total=False):
    """Carry volatile preflight decisions between routing stages."""
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

    def __init__(self, safety: SafetyPort, language: LanguagePort, intent: IntentPort,
                 observer: Callable[[IntentDecision], None] | None = None) -> None:
        """Compile the protected safety, language and intent preflight graph."""
        if safety is None or language is None or intent is None:
            raise ValueError("Safety, language and intent ports are required")
        self._observer = observer
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
        """Reject unauthorized sessions or unsupported deployment modes before classification."""
        request = state["request"]
        if request.deployment_mode != "prototype_demo":
            return {"route": Route.REJECT_MODE}
        if not request.session_valid:
            return {"route": Route.REJECT_SESSION}
        return {}

    @staticmethod
    def _after_validation(state: _State) -> str:
        """Choose whether a validated preflight proceeds to safety interception."""
        return "end" if "route" in state else "safety"

    def _intercept_safety(self, state: _State) -> _State:
        """Run the required safety classifier before language or intent processing."""
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
        """Choose the next stage according to the safety decision and request kind."""
        if "route" in state:
            return "end"
        if state["request"].kind is RequestKind.STRUCTURED_ASSESSMENT:
            return "route"
        return "language"

    def _detect_language(self, state: _State) -> _State:
        """Run language classification on the transient free-text request."""
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
        """Continue only for supported English and otherwise select a terminal route."""
        return "end" if "route" in state else "intent"

    def _classify_intent(self, state: _State) -> _State:
        """Classify user intent and validate the returned confidence and provenance."""
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
        confirmed = state["request"].confirmed_intent
        # Stateless check: honor a confirmation only if the router itself would suggest it.
        if confirmed is not None and suggestion(decision) is confirmed:
            decision = IntentDecision(
                confirmed, 1.0, False, decision.model_id, decision.model_sha256,
                decision.calibration_version, decision.router_version,
                "user_confirmed_suggestion",
            )
        if self._observer is not None:
            try:
                self._observer(decision)
            except Exception:
                pass  # Monitoring must never change routing.
        return {"intent": decision}

    @staticmethod
    def _select_route(state: _State) -> _State:
        """Map the validated intent to its allowed downstream workflow stage."""
        request = state["request"]
        if request.kind is RequestKind.STRUCTURED_ASSESSMENT:
            return {"route": (Route.VALIDATE_ASSESSMENT if request.assessment_view_authorized
                              else Route.UNSUPPORTED)}
        decision = state["intent"]
        if decision.requires_clarification or decision.calibrated_confidence < ROUTING_CONFIDENCE_THRESHOLD:
            return {"route": Route.CLARIFY_INTENT}
        return {"route": {
            Intent.RISK_ASSESSMENT: Route.ASSESSMENT_REDIRECTION,
            Intent.EXPLAIN_MY_RISK: Route.LOAD_PRIOR_RESULT,
            Intent.SCIENTIFIC_QUESTION: Route.SCIENTIFIC_RETRIEVAL,
            Intent.MENTAL_HEALTH_EDUCATION: Route.SCIENTIFIC_RETRIEVAL,
            Intent.GENERAL_CONVERSATION: Route.GENERAL_GENERATION,
            Intent.UNSUPPORTED_OR_UNSAFE: Route.UNSUPPORTED,
        }[decision.intent]}

    def safety_decision(self, request: PreflightRequest) -> SafetyDecision:
        """Run only the validated safety port, for paths that must not wait on capacity."""
        if external_tracing_enabled():
            raise RuntimeError("External tracing is forbidden for runtime requests")
        return self._intercept_safety({"request": request})["safety"]

    def advance(self, request: PreflightRequest) -> RouteDecision:
        # No runtime user content may be sent to an external trace service.
        """Execute protected preflight and return the next-stage routing decision."""
        if external_tracing_enabled():
            raise RuntimeError("External tracing is forbidden for runtime requests")
        state = self._graph.invoke({"request": request})
        suggested = (suggestion(state["intent"])
                     if state["route"] is Route.CLARIFY_INTENT and "intent" in state else None)
        return RouteDecision(
            route=state["route"],
            safety_category=state["safety"].category if "safety" in state else None,
            language_status=state["language"].status if "language" in state else None,
            intent=state["intent"].intent if "intent" in state else None,
            suggested_intent=suggested,
        )


def suggestion(decision: IntentDecision) -> Intent | None:
    """Return the intent worth offering for confirmation, or None for a generic menu."""
    unfamiliar = decision.rationale_code == "semantic_unfamiliar"
    if (decision.intent in CONFIRMABLE_INTENTS and not unfamiliar
            and decision.calibrated_confidence >= SUGGESTION_MIN_CONFIDENCE):
        return decision.intent
    return None
