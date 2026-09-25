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
    def __init__(self, result):
        self.result = result
        self.calls = 0

    def evaluate(self, request):
        self.calls += 1
        return self.result

    def classify(self, text):
        self.calls += 1
        return self.result


def intent(value=Intent.SCIENTIFIC_QUESTION, confidence=0.98, clarify=False):
    return IntentDecision(value, confidence, clarify, "synthetic-router", "fixture-sha",
                          "fixture-calibration", "router-v1", "fixture")


class RoutingTests(unittest.TestCase):
    def setUp(self):
        self.safety = Port(SafetyDecision(SafetyCategory.ALLOW_NORMAL_PROCESSING,
                                          "policy-v1", "fixture"))
        self.language = Port(LanguageDecision(LanguageStatus.SUPPORTED_ENGLISH,
                                              "detector-v1", "fixture"))
        self.intent = Port(intent())
        self.graph = RoutingGraph(self.safety, self.language, self.intent)

    def message(self, **changes):
        args = dict(kind=RequestKind.FREE_TEXT, deployment_mode="prototype_demo",
                    session_valid=True, text="What is the research association?")
        args.update(changes)
        return PreflightRequest(**args)

    def test_scientific_route_is_not_tool_authorization(self):
        result = self.graph.advance(self.message())
        self.assertEqual(result.route, Route.SCIENTIFIC_RETRIEVAL)
        self.assertFalse(result.allow_rag or result.allow_llm or result.allow_inference)
        self.assertEqual((self.safety.calls, self.language.calls, self.intent.calls), (1, 1, 1))

    def test_invalid_session_never_reaches_safety_or_models(self):
        result = self.graph.advance(self.message(session_valid=False))
        self.assertEqual(result.route, Route.REJECT_SESSION)
        self.assertEqual((self.safety.calls, self.language.calls, self.intent.calls), (0, 0, 0))

    def test_hospital_mode_fails_closed(self):
        result = self.graph.advance(self.message(deployment_mode="hospital_silent_research"))
        self.assertEqual(result.route, Route.REJECT_MODE)
        self.assertEqual(self.safety.calls, 0)

    def test_safety_terminal_denies_later_ports(self):
        self.safety.result = SafetyDecision(SafetyCategory.PRESCRIPTIVE_REFUSAL,
                                            "policy-v1", "fixture")
        result = self.graph.advance(self.message())
        self.assertEqual(result.route, Route.SAFETY_TERMINAL)
        self.assertEqual(result.safety_category, SafetyCategory.PRESCRIPTIVE_REFUSAL)
        self.assertEqual((self.language.calls, self.intent.calls), (0, 0))

    def test_uncertain_language_denies_intent(self):
        self.language.result = LanguageDecision(LanguageStatus.UNCERTAIN_LANGUAGE,
                                                "detector-v1", "fixture")
        result = self.graph.advance(self.message())
        self.assertEqual(result.route, Route.LANGUAGE_TERMINAL)
        self.assertEqual(self.intent.calls, 0)

    def test_risk_chat_only_redirects(self):
        self.intent.result = intent(Intent.RISK_ASSESSMENT)
        result = self.graph.advance(self.message())
        self.assertEqual(result.route, Route.ASSESSMENT_REDIRECTION)
        self.assertFalse(result.allow_inference)

    def test_low_confidence_clarifies_before_tools(self):
        self.intent.result = intent(confidence=0.84)
        result = self.graph.advance(self.message())
        self.assertEqual(result.route, Route.CLARIFY_INTENT)
        self.assertFalse(result.allow_rag)

    def test_explicit_abstention_clarifies(self):
        self.intent.result = intent(clarify=True)
        self.assertEqual(self.graph.advance(self.message()).route, Route.CLARIFY_INTENT)

    def test_structured_assessment_bypasses_language_and_intent_but_not_safety(self):
        request = PreflightRequest(RequestKind.STRUCTURED_ASSESSMENT, "prototype_demo", True,
                                   assessment_view_authorized=True)
        result = self.graph.advance(request)
        self.assertEqual(result.route, Route.VALIDATE_ASSESSMENT)
        self.assertFalse(result.allow_inference)
        self.assertEqual((self.safety.calls, self.language.calls, self.intent.calls), (1, 0, 0))

    def test_structured_assessment_requires_view_authorization(self):
        request = PreflightRequest(RequestKind.STRUCTURED_ASSESSMENT, "prototype_demo", True)
        self.assertEqual(self.graph.advance(request).route, Route.UNSUPPORTED)

    def test_mixed_request_shape_is_rejected(self):
        with self.assertRaises(ValueError):
            self.message(assessment_view_authorized=True)
        with self.assertRaises(ValueError):
            PreflightRequest(RequestKind.STRUCTURED_ASSESSMENT, "prototype_demo", True,
                             text="hello")

    def test_uncalibrated_router_result_is_rejected(self):
        self.intent.result = intent(confidence=float("nan"))
        with self.assertRaises(ValueError):
            self.graph.advance(self.message())

    def test_external_tracing_is_rejected(self):
        for key in ("LANGSMITH_TRACING", "LANGCHAIN_TRACING_V2"):
            with self.subTest(key=key), patch.dict("os.environ", {key: "true"}):
                with self.assertRaises(RuntimeError):
                    self.graph.advance(self.message())
        self.assertEqual(self.safety.calls, 0)


if __name__ == "__main__":
    unittest.main()
