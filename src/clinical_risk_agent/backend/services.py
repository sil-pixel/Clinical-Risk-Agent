"""Service protocols consumed by the HTTP layer and their local model-backed adapters.

The API depends only on the protocols; `create_app` receives concrete services, so tests
inject fakes through the same parameters (dependency inversion).
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any, Protocol

from clinical_risk_agent.ai import (
    AssessmentStatus,
    AssessmentSubmission,
    MLAssessmentAdapter,
    PreflightRequest,
    ProtectedAssessmentGraph,
    PrototypeIntentPort,
    PrototypeLanguagePort,
    PrototypeSafetyPort,
    RequestKind,
    RoutingGraph,
)
from clinical_risk_agent.inference import (
    DCMFNetPredictor,
    questionnaire_feature_codes,
    questionnaire_requirements,
)
from clinical_risk_agent.interpretation import interpret, load_score_reference
from clinical_risk_agent.rag.runtime import ResearchRuntime


class ResearchService(Protocol):
    """Define the research retrieval operations required by the public API."""
    def ready(self) -> tuple[bool, str | None]:
        """Check research readiness and report the loaded corpus version."""
        ...
    def answer(self, question_id: str) -> dict[str, Any]:
        """Answer a supported research question using approved claim evidence."""
        ...
    def answer_text(self, question: str) -> dict[str, Any]:
        """Answer a free-text research question through the bounded evidence workflow."""
        ...
    def search_general(self, question: str) -> dict[str, Any]:
        """Retrieve broader corpus passages for a general research question."""
        ...
    def close(self) -> None:
        """Release the owned runtime or provider resources."""
        ...


class ConversationService(Protocol):
    """Define protected chat generation and assessment-explanation operations."""
    def handle(self, text: str, *, deployment_mode: str, session_valid: bool,
               confirmed_intent: str | None = None,
               prior_result: dict[str, Any] | None = None) -> dict[str, Any]:
        """Run protected routing and return the appropriate public conversational outcome."""
        ...

    def safety_response(self, text: str, *, deployment_mode: str) -> dict[str, Any] | None:
        """Return the fixed safety reply if the safety rules intercept text, else None."""
        ...
    def explain_assessment(self, result: dict[str, Any]) -> dict[str, Any]:
        """Generate a plain-language explanation of validated research-model display values."""
        ...
    def close(self) -> None:
        """Release the owned runtime or provider resources."""
        ...


class AssessmentService(Protocol):
    """Define questionnaire discovery and protected model assessment operations."""
    def requirements(self) -> dict[str, Any]:
        """Return the public questionnaire version, questions and allowed options."""
        ...
    def assess(self, version: str, answers: dict[str, str],
               *, deployment_mode: str, timeout_seconds: float) -> dict[str, Any]:
        """Run protected questionnaire validation and return separate research-model estimates."""
        ...


class LocalAssessmentService:
    """Lazily loads both pinned DCMFNet artifacts and the protected graph."""

    def __init__(self, root: Path) -> None:
        """Prepare lazy, thread-safe loading of the protected assessment runtime."""
        self._root = root
        self._graph: ProtectedAssessmentGraph | None = None
        self._score_reference: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def _load(self) -> ProtectedAssessmentGraph:
        """Lazily initialize and cache the local service runtime under a lock."""
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
                # Use reference quantiles only if built from these exact checkpoints.
                reference = load_score_reference(self._root) or {}
                for name, predictor in (("positive", positive), ("negative", negative)):
                    target = reference.get("targets", {}).get(name, {})
                    if target.get("checkpoint_sha256") == predictor.inspection.checkpoint_sha256:
                        self._score_reference[name] = target["quantiles"]
            return self._graph

    def warmup(self) -> None:
        """Load model resources before the first assessment request."""
        self._load()

    @staticmethod
    def drift_features(version: str, answers: dict[str, str]) -> dict[str, int]:
        """Return answered feature codes for aggregate input-drift monitoring."""
        return questionnaire_feature_codes(answers, version=version)

    @staticmethod
    def requirements() -> dict[str, Any]:
        """Return the public questionnaire version, questions and allowed options."""
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
        """Run protected questionnaire validation and return separate research-model estimates."""
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
                    **{f"{name}_reference": interpret(prediction.predictions[0]
                                                      .normalized_symptom_severity, quantiles)
                       for name, prediction in (("positive", outcome.result.positive),
                                                ("negative", outcome.result.negative))
                       if (quantiles := self._score_reference.get(name))},
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
        """Prepare lazy, thread-safe loading of the local scientific retrieval runtime."""
        self._root = root
        self._runtime: ResearchRuntime | None = None
        self._lock = threading.Lock()

    def _load(self) -> ResearchRuntime:
        """Lazily initialize and cache the local service runtime under a lock."""
        with self._lock:
            if self._runtime is None:
                self._runtime = ResearchRuntime(self._root)
            return self._runtime

    def ready(self) -> tuple[bool, str | None]:
        """Check research readiness and report the loaded corpus version."""
        try:
            return True, self._load().corpus_version
        except Exception:
            return False, None

    def answer(self, question_id: str) -> dict[str, Any]:
        """Answer a supported research question using approved claim evidence."""
        return self._load().answerer.answer_public_id(question_id)

    def answer_text(self, question: str) -> dict[str, Any]:
        """Answer a free-text research question through the bounded evidence workflow."""
        return self._load().answerer.answer(question)

    def search_general(self, question: str) -> dict[str, Any]:
        """Retrieve broader corpus passages for a general research question."""
        return self._load().search_general(question)

    def close(self) -> None:
        """Release the owned runtime or provider resources."""
        if self._runtime is not None:
            self._runtime.close()
