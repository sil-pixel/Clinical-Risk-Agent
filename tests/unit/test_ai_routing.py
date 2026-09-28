"""Synthetic route fixtures; no user payload or model service is involved."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from clinical_risk_agent.ai import (
    Intent,
    IntentDecision,
    LanguageDecision,
    LanguageStatus,
    PreflightRequest,
    RequestKind,
    Route,
    RoutingGraph,
    SafetyCategory,
    SafetyDecision,
)


class Port:
    """Provide port fixtures and assertions."""
    def __init__(self, result):
        """Initialize the synthetic test fixture and its observable state."""
        self.result = result
        self.calls = 0

    def evaluate(self, request):
        """Provide evaluate behavior for synthetic test fixtures."""
        self.calls += 1
        return self.result

    def classify(self, text):
        """Provide classify behavior for synthetic test fixtures."""
        self.calls += 1
        return self.result


def intent(value=Intent.SCIENTIFIC_QUESTION, confidence=0.98, clarify=False):
    """Provide intent behavior for synthetic test fixtures."""
    return IntentDecision(value, confidence, clarify, "synthetic-router", "fixture-sha",
                          "fixture-calibration", "router-v1", "fixture")


class RoutingTests(unittest.TestCase):
    """Provide routing tests fixtures and assertions."""
    def setUp(self):
        """Prepare isolated fixtures before each test."""
        self.safety = Port(SafetyDecision(SafetyCategory.ALLOW_NORMAL_PROCESSING,
                                          "policy-v1", "fixture"))
        self.language = Port(LanguageDecision(LanguageStatus.SUPPORTED_ENGLISH,
                                              "detector-v1", "fixture"))
        self.intent = Port(intent())
        self.graph = RoutingGraph(self.safety, self.language, self.intent)

    def message(self, **changes):
        """Provide message behavior for synthetic test fixtures."""
        args = dict(kind=RequestKind.FREE_TEXT, deployment_mode="prototype_demo",
                    session_valid=True, text="What is the research association?")
        args.update(changes)
        return PreflightRequest(**args)

    def test_scientific_route_is_not_tool_authorization(self):
        """Verify scientific route is not tool authorization."""
        request = self.message()
        self.assertNotIn("research association", repr(request))
        result = self.graph.advance(request)
        self.assertEqual(result.route, Route.SCIENTIFIC_RETRIEVAL)
        self.assertFalse(result.allow_rag or result.allow_llm or result.allow_inference)
        self.assertEqual((self.safety.calls, self.language.calls, self.intent.calls), (1, 1, 1))

    def test_invalid_session_never_reaches_safety_or_models(self):
        """Verify invalid session never reaches safety or models."""
        result = self.graph.advance(self.message(session_valid=False))
        self.assertEqual(result.route, Route.REJECT_SESSION)
        self.assertEqual((self.safety.calls, self.language.calls, self.intent.calls), (0, 0, 0))

    def test_hospital_mode_fails_closed(self):
        """Verify hospital mode fails closed."""
        result = self.graph.advance(self.message(deployment_mode="hospital_silent_research"))
        self.assertEqual(result.route, Route.REJECT_MODE)
        self.assertEqual(self.safety.calls, 0)

    def test_safety_terminal_denies_later_ports(self):
        """Verify safety terminal denies later ports."""
        self.safety.result = SafetyDecision(SafetyCategory.PRESCRIPTIVE_REFUSAL,
                                            "policy-v1", "fixture")
        result = self.graph.advance(self.message())
        self.assertEqual(result.route, Route.SAFETY_TERMINAL)
        self.assertEqual(result.safety_category, SafetyCategory.PRESCRIPTIVE_REFUSAL)
        self.assertEqual((self.language.calls, self.intent.calls), (0, 0))

    def test_uncertain_language_denies_intent(self):
        """Verify uncertain language denies intent."""
        self.language.result = LanguageDecision(LanguageStatus.UNCERTAIN_LANGUAGE,
                                                "detector-v1", "fixture")
        result = self.graph.advance(self.message())
        self.assertEqual(result.route, Route.LANGUAGE_TERMINAL)
        self.assertEqual(self.intent.calls, 0)

    def test_risk_chat_only_redirects(self):
        """Verify risk chat only redirects."""
        self.intent.result = intent(Intent.RISK_ASSESSMENT)
        result = self.graph.advance(self.message())
        self.assertEqual(result.route, Route.ASSESSMENT_REDIRECTION)
        self.assertFalse(result.allow_inference)

    def test_low_confidence_clarifies_before_tools(self):
        """Verify low confidence clarifies before tools."""
        self.intent.result = intent(confidence=0.84)
        result = self.graph.advance(self.message())
        self.assertEqual(result.route, Route.CLARIFY_INTENT)
        self.assertFalse(result.allow_rag)

    def test_explicit_abstention_clarifies(self):
        """Verify explicit abstention clarifies."""
        self.intent.result = intent(clarify=True)
        self.assertEqual(self.graph.advance(self.message()).route, Route.CLARIFY_INTENT)

    def test_structured_assessment_bypasses_language_and_intent_but_not_safety(self):
        """Verify structured assessment bypasses language and intent but not safety."""
        request = PreflightRequest(RequestKind.STRUCTURED_ASSESSMENT, "prototype_demo", True,
                                   assessment_view_authorized=True)
        result = self.graph.advance(request)
        self.assertEqual(result.route, Route.VALIDATE_ASSESSMENT)
        self.assertFalse(result.allow_inference)
        self.assertEqual((self.safety.calls, self.language.calls, self.intent.calls), (1, 0, 0))

    def test_structured_assessment_requires_view_authorization(self):
        """Verify structured assessment requires view authorization."""
        request = PreflightRequest(RequestKind.STRUCTURED_ASSESSMENT, "prototype_demo", True)
        self.assertEqual(self.graph.advance(request).route, Route.UNSUPPORTED)

    def test_mixed_request_shape_is_rejected(self):
        """Verify mixed request shape is rejected."""
        with self.assertRaises(ValueError):
            self.message(assessment_view_authorized=True)
        with self.assertRaises(ValueError):
            PreflightRequest(RequestKind.STRUCTURED_ASSESSMENT, "prototype_demo", True,
                             text="hello")
        with self.assertRaises(ValueError):
            self.message(session_valid="false")
        with self.assertRaises(ValueError):
            PreflightRequest(RequestKind.STRUCTURED_ASSESSMENT, "prototype_demo", True,
                             assessment_view_authorized="false")

    def test_uncalibrated_router_result_is_rejected(self):
        """Verify uncalibrated router result is rejected."""
        self.intent.result = intent(confidence=float("nan"))
        with self.assertRaises(ValueError):
            self.graph.advance(self.message())

    def test_external_tracing_is_rejected(self):
        """Verify external tracing is rejected."""
        for key in ("LANGSMITH_TRACING", "LANGCHAIN_TRACING_V2"):
            with self.subTest(key=key), patch.dict("os.environ", {key: "true"}):
                with self.assertRaises(RuntimeError):
                    self.graph.advance(self.message())
        self.assertEqual(self.safety.calls, 0)


if __name__ == "__main__":
    unittest.main()
