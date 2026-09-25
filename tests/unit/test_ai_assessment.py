"""Synthetic protected-assessment paths and one pinned-artifact integration check."""

from __future__ import annotations

import time
import unittest
from pathlib import Path
from unittest.mock import patch

from clinical_risk_agent.ai import (
    AssessmentStatus,
    AssessmentSubmission,
    Intent,
    IntentDecision,
    LanguageDecision,
    LanguageStatus,
    MLAssessmentAdapter,
    PreflightRequest,
    ProtectedAssessmentGraph,
    RequestKind,
    RoutingGraph,
    SafetyCategory,
    SafetyDecision,
)
from clinical_risk_agent.ai.assessment import INTERNAL_VARIANCE_MESSAGE
from clinical_risk_agent.contracts import (
    InferenceResult,
    ModelTarget,
    QuestionnaireAssessmentResult,
    SymptomSeverityPrediction,
)
from clinical_risk_agent.contracts.model_inference import OUTPUT_NAME
from clinical_risk_agent.inference import DCMFNetPredictor
from clinical_risk_agent.inference.questionnaire import (
    questionnaire_requirements,
    validate_questionnaire,
)

ROOT = Path(__file__).resolve().parents[2]


def answers() -> dict[str, str]:
    return {item.question_id: item.option_ids[0] for item in questionnaire_requirements().questions}


def synthetic_result(positive: float = 0.25, negative: float = 0.75) -> QuestionnaireAssessmentResult:
    def one(target: ModelTarget, value: float) -> InferenceResult:
        return InferenceResult(target, (SymptomSeverityPrediction(value),), 1,
                               "synthetic-artifact-sha", OUTPUT_NAME, ("synthetic fixture",))

    return QuestionnaireAssessmentResult(
        questionnaire_requirements().version, "generic_genetic_profile_v1",
        one(ModelTarget.POSITIVE_SYMPTOM_SEVERITY, positive),
        one(ModelTarget.NEGATIVE_SYMPTOM_SEVERITY, negative),
    )


class FixedSafety:
    def __init__(self):
        self.category = SafetyCategory.ALLOW_NORMAL_PROCESSING
        self.calls = 0

    def evaluate(self, request):
        self.calls += 1
        return SafetyDecision(self.category, "synthetic-policy", "fixture")


class NeverLanguage:
    def classify(self, text):
        raise AssertionError("Structured assessment must bypass language detection")


class NeverIntent:
    def classify(self, text):
        raise AssertionError("Structured assessment must bypass intent classification")


class FakeML:
    def __init__(self, result=None):
        self.result = result or synthetic_result()
        self.validations = 0
        self.predictions = 0
        self.error = None

    def validate(self, answer_map, *, version):
        self.validations += 1
        return validate_questionnaire(answer_map, version=version)

    def predict(self, answer_map, *, version):
        self.predictions += 1
        if self.error:
            raise self.error
        return self.result


class AssessmentGraphTests(unittest.TestCase):
    def setUp(self):
        self.safety = FixedSafety()
        self.ml = FakeML()
        self.routing = RoutingGraph(self.safety, NeverLanguage(), NeverIntent())
        self.graph = ProtectedAssessmentGraph(self.routing, self.ml)

    def submission(self, answer_map=None, *, authorized=True, session=True,
                   mode="prototype_demo", version=None, deadline=None):
        preflight = PreflightRequest(
            RequestKind.STRUCTURED_ASSESSMENT, mode, session,
            assessment_view_authorized=authorized,
        )
        return AssessmentSubmission(
            preflight, version or questionnaire_requirements().version,
            answers() if answer_map is None else answer_map,
            time.monotonic() + 60 if deadline is None else deadline,
        )

    def test_complete_synthetic_assessment_preserves_separate_raw_values(self):
        outcome = self.graph.run(self.submission())
        self.assertEqual(outcome.status, AssessmentStatus.READY)
        self.assertIs(outcome.result, self.ml.result)
        self.assertEqual(outcome.result.positive.predictions[0].normalized_symptom_severity, 0.25)
        self.assertEqual(outcome.result.negative.predictions[0].normalized_symptom_severity, 0.75)
        self.assertEqual(outcome.display.positive_percent, "25.0%")
        self.assertEqual(outcome.display.negative_percent, "75.0%")
        self.assertTrue(outcome.display.synthetic_training_data)
        self.assertEqual((self.ml.validations, self.ml.predictions), (1, 1))
        self.assertNotIn("25.0%", repr(outcome))

    def test_missing_answers_do_not_call_inference(self):
        answer_map = answers()
        answer_map.pop("q001")
        outcome = self.graph.run(self.submission(answer_map))
        self.assertEqual(outcome.status, AssessmentStatus.QUESTIONNAIRE_INCOMPLETE)
        self.assertEqual(outcome.validation.missing_question_ids, ("q001",))
        self.assertEqual(self.ml.predictions, 0)

    def test_unscored_and_unknown_answers_do_not_call_inference(self):
        for invalid_map in ({**answers(), "q001": "memory_unknown"},
                            {**answers(), "q999": "o01"}):
            with self.subTest(invalid_map=invalid_map.get("q999", "memory_unknown")):
                self.assertEqual(self.graph.run(self.submission(invalid_map)).status,
                                 AssessmentStatus.QUESTIONNAIRE_INVALID)
        self.assertEqual(self.ml.predictions, 0)

    def test_wrong_version_fails_before_inference(self):
        outcome = self.graph.run(self.submission(version="unsupported-v0"))
        self.assertEqual(outcome.status, AssessmentStatus.QUESTIONNAIRE_CONTRACT_UNAVAILABLE)
        self.assertEqual(self.ml.predictions, 0)

    def test_session_and_view_authorization_precede_ml(self):
        for kwargs in ({"session": False}, {"authorized": False},
                       {"mode": "hospital_silent_research"}):
            with self.subTest(kwargs=kwargs):
                self.assertEqual(self.graph.run(self.submission(**kwargs)).status,
                                 AssessmentStatus.UNAUTHORIZED)
        self.assertEqual((self.ml.validations, self.ml.predictions), (0, 0))

    def test_safety_terminal_precedes_ml(self):
        self.safety.category = SafetyCategory.CRITICAL_SAFETY_REDIRECTION
        outcome = self.graph.run(self.submission())
        self.assertEqual(outcome.status, AssessmentStatus.SAFETY_TERMINAL)
        self.assertEqual((self.ml.validations, self.ml.predictions), (0, 0))

    def test_expired_deadline_precedes_even_safety(self):
        outcome = self.graph.run(self.submission(deadline=time.monotonic() - 1))
        self.assertEqual(outcome.status, AssessmentStatus.DEADLINE_EXPIRED)
        self.assertEqual(self.safety.calls, 0)
        self.assertEqual(self.ml.validations, 0)

    def test_external_tracing_fails_before_graph_receives_answers(self):
        with patch.dict("os.environ", {"LANGSMITH_TRACING": "true"}):
            outcome = self.graph.run(self.submission())
        self.assertEqual(outcome.status, AssessmentStatus.PRECONDITION_UNAVAILABLE)
        self.assertEqual((self.safety.calls, self.ml.validations, self.ml.predictions),
                         (0, 0, 0))

    def test_out_of_range_and_nonfinite_outputs_fail_closed(self):
        for value in (-0.01, 1.01, float("nan"), float("inf")):
            with self.subTest(value=value):
                self.ml.result = synthetic_result(positive=value)
                outcome = self.graph.run(self.submission())
                self.assertEqual(outcome.status, AssessmentStatus.INTERNAL_SYSTEM_VARIANCE)
                self.assertIsNone(outcome.result)
                self.assertIsNone(outcome.display)
                self.assertEqual(outcome.safe_message, INTERNAL_VARIANCE_MESSAGE)

    def test_wrong_target_fails_closed_without_display(self):
        result = synthetic_result()
        self.ml.result = QuestionnaireAssessmentResult(
            result.questionnaire_version, result.generic_profile_version,
            result.negative, result.positive,
        )
        outcome = self.graph.run(self.submission())
        self.assertEqual(outcome.status, AssessmentStatus.INFERENCE_UNAVAILABLE)
        self.assertIsNone(outcome.result)

    def test_ml_adapter_invalid_probability_maps_to_variance(self):
        self.ml.error = ValueError("Assessment produced an invalid probability")
        outcome = self.graph.run(self.submission())
        self.assertEqual(outcome.status, AssessmentStatus.INTERNAL_SYSTEM_VARIANCE)
        self.assertEqual(outcome.safe_message, INTERNAL_VARIANCE_MESSAGE)

    def test_runtime_failure_returns_no_estimate(self):
        self.ml.error = RuntimeError("synthetic worker failure with secret")
        outcome = self.graph.run(self.submission())
        self.assertEqual(outcome.status, AssessmentStatus.INFERENCE_UNAVAILABLE)
        self.assertIsNone(outcome.result)
        self.assertIsNone(outcome.safe_message)

    def test_submission_copies_answers_and_suppresses_repr(self):
        answer_map = answers()
        submission = self.submission(answer_map)
        answer_map["q001"] = "memory_unknown"
        self.assertEqual(submission.answers["q001"], "o01")
        self.assertNotIn("q001", repr(submission))

    def test_free_text_cannot_be_submitted(self):
        with self.assertRaises(ValueError):
            AssessmentSubmission(
                PreflightRequest(RequestKind.FREE_TEXT, "prototype_demo", True, "risk?"),
                questionnaire_requirements().version, answers(), time.monotonic() + 60,
            )

    def test_real_ml_adapter_uses_both_pinned_artifacts(self):
        artifact_dir = ROOT / "model_artifacts"
        positive = DCMFNetPredictor(artifact_dir / "dcmfnet_pos.pt",
                                    artifact_dir / "dcmfnet_pos.metadata.json")
        negative = DCMFNetPredictor(artifact_dir / "dcmfnet_neg.pt",
                                    artifact_dir / "dcmfnet_neg.metadata.json")
        graph = ProtectedAssessmentGraph(self.routing, MLAssessmentAdapter(positive, negative))
        outcome = graph.run(self.submission())
        self.assertEqual(outcome.status, AssessmentStatus.READY)
        self.assertEqual(outcome.result.positive.target, ModelTarget.POSITIVE_SYMPTOM_SEVERITY)
        self.assertEqual(outcome.result.negative.target, ModelTarget.NEGATIVE_SYMPTOM_SEVERITY)
        self.assertNotEqual(outcome.display.positive_percent, outcome.display.negative_percent)


if __name__ == "__main__":
    unittest.main()
