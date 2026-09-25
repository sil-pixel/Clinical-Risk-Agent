"""Protected, no-checkpointer assessment subgraph over the ML-owned adapter."""

from __future__ import annotations

import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from math import isfinite
from types import MappingProxyType
from typing import Protocol, TypedDict

from langgraph.graph import END, START, StateGraph

from clinical_risk_agent.contracts import (
    InferenceResult,
    ModelTarget,
    QuestionnaireAssessmentResult,
    QuestionnaireStatus,
    QuestionnaireValidationResult,
    SymptomSeverityPrediction,
)
from clinical_risk_agent.contracts.model_inference import OUTPUT_NAME
from clinical_risk_agent.contracts.questionnaire import GENERIC_PROFILE_VERSION
from clinical_risk_agent.inference.errors import InferenceError, InferenceErrorCode
from clinical_risk_agent.inference.questionnaire import (
    predict_questionnaire,
    validate_questionnaire,
)
from clinical_risk_agent.inference.runtime import DCMFNetPredictor

from .routing import (
    PreflightRequest,
    RequestKind,
    Route,
    RoutingGraph,
    SafetyCategory,
    external_tracing_enabled,
)


INTERNAL_VARIANCE_MESSAGE = (
    "Error: Unable to compute estimate due to an internal system variance. "
    "Please try again later."
)


class AssessmentStatus(str, Enum):
    READY = "assessment_ready"
    UNAUTHORIZED = "assessment_unauthorized"
    SAFETY_TERMINAL = "safety_terminal"
    PRECONDITION_UNAVAILABLE = "assessment_precondition_unavailable"
    DEADLINE_EXPIRED = "assessment_deadline_expired"
    QUESTIONNAIRE_INCOMPLETE = "questionnaire_incomplete"
    QUESTIONNAIRE_INVALID = "questionnaire_invalid"
    QUESTIONNAIRE_CONTRACT_UNAVAILABLE = "questionnaire_contract_unavailable"
    INFERENCE_UNAVAILABLE = "inference_unavailable"
    INTERNAL_SYSTEM_VARIANCE = "internal_system_variance"


@dataclass(frozen=True, slots=True)
class AssessmentSubmission:
    """Backend-only request. Authorization booleans must never come from a client body."""

    preflight: PreflightRequest
    questionnaire_version: str
    answers: Mapping[str, str] = field(repr=False)
    deadline_monotonic: float

    def __post_init__(self) -> None:
        if self.preflight.kind is not RequestKind.STRUCTURED_ASSESSMENT:
            raise ValueError("Assessment requires a structured request")
        if not isinstance(self.answers, Mapping):
            raise TypeError("Questionnaire answers must be a mapping")
        if (not isinstance(self.deadline_monotonic, (int, float))
                or isinstance(self.deadline_monotonic, bool)
                or not isfinite(self.deadline_monotonic)
                or self.deadline_monotonic - time.monotonic() > 60.0):
            raise ValueError("Assessment deadline is invalid")
        object.__setattr__(self, "answers", MappingProxyType(dict(self.answers)))


@dataclass(frozen=True, slots=True, repr=False)
class ValidatedAssessmentDisplay:
    positive_percent: str
    negative_percent: str
    generic_profile_version: str
    synthetic_training_data: bool = True


@dataclass(frozen=True, slots=True)
class ProtectedAssessmentOutcome:
    """Internal only: never serialize the raw assessment result into public content."""

    status: AssessmentStatus
    validation: QuestionnaireValidationResult | None = field(default=None, repr=False)
    result: QuestionnaireAssessmentResult | None = field(default=None, repr=False)
    display: ValidatedAssessmentDisplay | None = field(default=None, repr=False)
    safe_message: str | None = None


class AssessmentMLPort(Protocol):
    def validate(self, answers: Mapping[str, str], *, version: str) -> QuestionnaireValidationResult: ...

    def predict(
        self, answers: Mapping[str, str], *, version: str
    ) -> QuestionnaireAssessmentResult: ...


class MLAssessmentAdapter:
    """Thin bridge to ML-owned validation and paired inference; no feature mapping here."""

    def __init__(self, positive: DCMFNetPredictor, negative: DCMFNetPredictor) -> None:
        if (positive.target is not ModelTarget.POSITIVE_SYMPTOM_SEVERITY
                or negative.target is not ModelTarget.NEGATIVE_SYMPTOM_SEVERITY):
            raise ValueError("Assessment predictor targets are incompatible")
        self._positive = positive
        self._negative = negative

    def validate(self, answers: Mapping[str, str], *, version: str) -> QuestionnaireValidationResult:
        return validate_questionnaire(answers, version=version)

    def predict(
        self, answers: Mapping[str, str], *, version: str
    ) -> QuestionnaireAssessmentResult:
        return predict_questionnaire(
            answers, self._positive, self._negative, version=version,
        )


class _State(TypedDict, total=False):
    submission: AssessmentSubmission
    status: AssessmentStatus
    validation: QuestionnaireValidationResult
    result: QuestionnaireAssessmentResult | None
    display: ValidatedAssessmentDisplay


class ProtectedAssessmentGraph:
    """Runs authorized validation and inference once, without persistence or retries."""

    def __init__(self, routing: RoutingGraph, ml: AssessmentMLPort) -> None:
        if routing is None or ml is None:
            raise ValueError("Routing and ML ports are required")
        self._routing = routing
        self._ml = ml
        graph = StateGraph(_State)
        graph.add_node("authorize_assessment", self._authorize)
        graph.add_node("validate_questionnaire", self._validate)
        graph.add_node("invoke_dcmfnet", self._invoke)
        graph.add_node("validate_and_present_results", self._present)
        graph.add_edge(START, "authorize_assessment")
        graph.add_conditional_edges("authorize_assessment", self._next, {
            "continue": "validate_questionnaire", "end": END,
        })
        graph.add_conditional_edges("validate_questionnaire", self._next, {
            "continue": "invoke_dcmfnet", "end": END,
        })
        graph.add_conditional_edges("invoke_dcmfnet", self._next, {
            "continue": "validate_and_present_results", "end": END,
        })
        graph.add_edge("validate_and_present_results", END)
        self._graph = graph.compile()

    @staticmethod
    def _expired(submission: AssessmentSubmission) -> bool:
        return time.monotonic() >= submission.deadline_monotonic

    @staticmethod
    def _next(state: _State) -> str:
        return "end" if "status" in state else "continue"

    def _authorize(self, state: _State) -> _State:
        submission = state["submission"]
        if self._expired(submission):
            return {"status": AssessmentStatus.DEADLINE_EXPIRED}
        try:
            route = self._routing.advance(submission.preflight)
        except Exception:
            return {"status": AssessmentStatus.PRECONDITION_UNAVAILABLE}
        if route.route is Route.SAFETY_TERMINAL:
            return {"status": AssessmentStatus.SAFETY_TERMINAL}
        if (route.route is not Route.VALIDATE_ASSESSMENT
                or route.safety_category is not SafetyCategory.ALLOW_NORMAL_PROCESSING):
            return {"status": AssessmentStatus.UNAUTHORIZED}
        return {}

    def _validate(self, state: _State) -> _State:
        submission = state["submission"]
        if self._expired(submission):
            return {"status": AssessmentStatus.DEADLINE_EXPIRED}
        try:
            validation = self._ml.validate(
                submission.answers, version=submission.questionnaire_version,
            )
        except ValueError:
            return {"status": AssessmentStatus.QUESTIONNAIRE_CONTRACT_UNAVAILABLE}
        except TypeError:
            return {"status": AssessmentStatus.QUESTIONNAIRE_INVALID}
        except RuntimeError:
            return {"status": AssessmentStatus.QUESTIONNAIRE_CONTRACT_UNAVAILABLE}
        except Exception:
            return {"status": AssessmentStatus.QUESTIONNAIRE_CONTRACT_UNAVAILABLE}
        if not isinstance(validation, QuestionnaireValidationResult):
            return {"status": AssessmentStatus.QUESTIONNAIRE_CONTRACT_UNAVAILABLE}
        if validation.version != submission.questionnaire_version:
            return {"status": AssessmentStatus.QUESTIONNAIRE_CONTRACT_UNAVAILABLE}
        if validation.status is QuestionnaireStatus.INCOMPLETE:
            return {"validation": validation, "status": AssessmentStatus.QUESTIONNAIRE_INCOMPLETE}
        if validation.status is not QuestionnaireStatus.COMPLETE or not validation.authorizes_inference:
            return {"validation": validation, "status": AssessmentStatus.QUESTIONNAIRE_INVALID}
        return {"validation": validation}

    def _invoke(self, state: _State) -> _State:
        submission = state["submission"]
        if self._expired(submission):
            return {"status": AssessmentStatus.DEADLINE_EXPIRED}
        try:
            result = self._ml.predict(
                submission.answers, version=submission.questionnaire_version,
            )
        except InferenceError as error:
            status = (AssessmentStatus.INTERNAL_SYSTEM_VARIANCE
                      if error.code is InferenceErrorCode.NON_FINITE_OUTPUT
                      else AssessmentStatus.INFERENCE_UNAVAILABLE)
            return {"status": status}
        except ValueError as error:
            # The current ML adapter uses this exact message for out-of-range output.
            status = (AssessmentStatus.INTERNAL_SYSTEM_VARIANCE
                      if str(error) == "Assessment produced an invalid probability"
                      else AssessmentStatus.INFERENCE_UNAVAILABLE)
            return {"status": status}
        except Exception:
            return {"status": AssessmentStatus.INFERENCE_UNAVAILABLE}
        if not isinstance(result, QuestionnaireAssessmentResult):
            return {"status": AssessmentStatus.INFERENCE_UNAVAILABLE}
        return {"result": result}

    def _present(self, state: _State) -> _State:
        submission = state["submission"]
        if self._expired(submission):
            return {"result": None, "status": AssessmentStatus.DEADLINE_EXPIRED}
        result = state["result"]
        if result is None or (result.questionnaire_version != submission.questionnaire_version
                             or result.generic_profile_version != GENERIC_PROFILE_VERSION):
            return {"result": None, "status": AssessmentStatus.INFERENCE_UNAVAILABLE}
        if (not isinstance(result.positive, InferenceResult)
                or not isinstance(result.negative, InferenceResult)
                or result.positive.target is not ModelTarget.POSITIVE_SYMPTOM_SEVERITY
                or result.negative.target is not ModelTarget.NEGATIVE_SYMPTOM_SEVERITY
                or result.positive.output_name != OUTPUT_NAME
                or result.negative.output_name != OUTPUT_NAME
                or type(result.positive.artifact_version) is not int
                or type(result.negative.artifact_version) is not int
                or result.positive.artifact_version < 1
                or result.negative.artifact_version < 1
                or not isinstance(result.positive.artifact_sha256, str)
                or not isinstance(result.negative.artifact_sha256, str)
                or not result.positive.artifact_sha256 or not result.negative.artifact_sha256
                or not isinstance(result.positive.predictions, tuple)
                or not isinstance(result.negative.predictions, tuple)
                or len(result.positive.predictions) != 1
                or len(result.negative.predictions) != 1
                or not isinstance(result.positive.predictions[0], SymptomSeverityPrediction)
                or not isinstance(result.negative.predictions[0], SymptomSeverityPrediction)):
            return {"result": None, "status": AssessmentStatus.INFERENCE_UNAVAILABLE}
        positive = result.positive.predictions[0].normalized_symptom_severity
        negative = result.negative.predictions[0].normalized_symptom_severity
        if not all(isinstance(value, (int, float)) and not isinstance(value, bool)
                   and isfinite(value) and 0.0 <= value <= 1.0
                   for value in (positive, negative)):
            return {"result": None, "status": AssessmentStatus.INTERNAL_SYSTEM_VARIANCE}
        display = ValidatedAssessmentDisplay(
            positive_percent=f"{positive * 100:.1f}%",
            negative_percent=f"{negative * 100:.1f}%",
            generic_profile_version=result.generic_profile_version,
        )
        return {"display": display, "status": AssessmentStatus.READY}

    def run(self, submission: AssessmentSubmission) -> ProtectedAssessmentOutcome:
        if external_tracing_enabled():
            return ProtectedAssessmentOutcome(AssessmentStatus.PRECONDITION_UNAVAILABLE)
        state = self._graph.invoke({"submission": submission})
        status = state["status"]
        return ProtectedAssessmentOutcome(
            status=status,
            validation=state.get("validation"),
            result=state.get("result") if status is AssessmentStatus.READY else None,
            display=state.get("display") if status is AssessmentStatus.READY else None,
            safe_message=(INTERNAL_VARIANCE_MESSAGE
                          if status is AssessmentStatus.INTERNAL_SYSTEM_VARIANCE else None),
        )
