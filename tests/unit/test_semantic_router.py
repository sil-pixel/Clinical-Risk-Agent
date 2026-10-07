import json
from pathlib import Path
import unittest

import numpy as np

from clinical_risk_agent.ai import (
    HybridIntentPort,
    Intent,
    PreflightRequest,
    PrototypeIntentPort,
    PrototypeLanguagePort,
    PrototypeSafetyPort,
    Route,
    RoutingGraph,
    SemanticIntentRouter,
)
from clinical_risk_agent.ai import ProtectedConversationOrchestrator
from clinical_risk_agent.ai.routing import IntentDecision, RequestKind
from clinical_risk_agent.backend.monitoring import Monitor
from clinical_risk_agent.ai.semantic_router import (
    CALIBRATION_PATH,
    UTTERANCES_PATH,
    load_semantic_router,
    sha256_text,
)

ROOT = Path(__file__).resolve().parents[2]
VOCABULARY = ("risk", "my", "result", "cannabis", "psychosis", "hello", "dose")


class BagOfWordsEncoder:
    """Deterministic unit-length bag-of-words vectors standing in for a sentence model."""

    def __init__(self):
        """Count embed calls so lazy loading can be observed."""
        self.calls = 0

    def embed(self, texts):
        """Return normalized vocabulary counts, with a bias slot for unknown words."""
        self.calls += 1
        rows = []
        for text in texts:
            words = text.lower().split()
            row = np.array([words.count(term) for term in VOCABULARY] + [0.01], dtype=float)
            rows.append(row / np.linalg.norm(row))
        return np.array(rows)


UTTERANCES = {
    "risk_assessment": ["calculate my risk", "my risk"],
    "scientific_question": ["cannabis psychosis", "cannabis and psychosis evidence"],
    "unsupported_or_unsafe": ["dose for me", "my dose"],
}


class SemanticRouterTests(unittest.TestCase):
    """Check similarity scoring, clarification and hybrid rule precedence."""

    def router(self, **overrides):
        """Build a router over the fixture utterances with sharp default settings."""
        settings = {"temperature": 0.05, "min_similarity": 0.5, **overrides}
        return SemanticIntentRouter(BagOfWordsEncoder(), UTTERANCES, **settings)

    def test_nearest_examples_choose_intent_with_provenance(self):
        """Verify the closest reference intent wins with confident, pinned provenance."""
        decision = self.router().classify("is cannabis linked to psychosis")
        self.assertIs(decision.intent, Intent.SCIENTIFIC_QUESTION)
        self.assertGreater(decision.calibrated_confidence, 0.85)
        self.assertFalse(decision.requires_clarification)
        self.assertEqual(decision.rationale_code, "semantic")

    def test_unfamiliar_text_requires_clarification(self):
        """Verify text unlike every reference falls below the similarity floor."""
        decision = self.router().classify("purple bicycle")
        self.assertTrue(decision.requires_clarification)
        self.assertEqual(decision.rationale_code, "semantic_unfamiliar")

    def test_higher_temperature_lowers_confidence(self):
        """Verify temperature softens confidence so the routing threshold can act."""
        sharp = self.router().classify("my risk").calibrated_confidence
        soft = self.router(temperature=5.0).classify("my risk").calibrated_confidence
        self.assertLess(soft, sharp)
        self.assertLess(soft, 0.85)

    def test_invalid_configuration_rejected(self):
        """Verify empty intents and nonpositive temperatures are rejected."""
        with self.assertRaises(ValueError):
            SemanticIntentRouter(BagOfWordsEncoder(), {"risk_assessment": []},
                                 temperature=0.1, min_similarity=0.0)
        with self.assertRaises(ValueError):
            self.router(temperature=0)

    def test_hybrid_keeps_certain_rules_and_loads_lazily(self):
        """Verify certain rules bypass the encoder, which loads only when first needed."""
        built = []

        def factory():
            """Build the fixture router and record that loading happened."""
            built.append(True)
            return self.router()

        port = HybridIntentPort(factory)
        rule = port.classify("calculate my risk")
        self.assertEqual(rule.rationale_code, "assessment_request")
        self.assertEqual(built, [])
        semantic = port.classify("what does the evidence say on cannabis psychosis")
        self.assertIs(semantic.intent, Intent.SCIENTIFIC_QUESTION)
        self.assertEqual(built, [True])
        port.classify("my dose")
        self.assertEqual(built, [True])

    def graph(self, observer=None, **router_settings):
        """Build the full routing graph around the fixture semantic router."""
        port = HybridIntentPort(lambda: self.router(**router_settings))
        return RoutingGraph(PrototypeSafetyPort(), PrototypeLanguagePort(), port,
                            observer=observer)

    @staticmethod
    def request(text, confirmed=None):
        """Build a free-text preflight request with an optional confirmation."""
        return PreflightRequest(kind=RequestKind.FREE_TEXT, deployment_mode="prototype_demo",
                                session_valid=True, text=text, confirmed_intent=confirmed)

    def test_near_miss_offers_suggestion_and_confirmation_routes(self):
        """Verify a below-threshold guess is suggested, then honored once confirmed."""
        graph = self.graph(temperature=0.5)
        first = graph.advance(self.request("cannabis psychosis"))
        self.assertIs(first.route, Route.CLARIFY_INTENT)
        self.assertIs(first.suggested_intent, Intent.SCIENTIFIC_QUESTION)
        second = graph.advance(self.request("cannabis psychosis", Intent.SCIENTIFIC_QUESTION))
        self.assertIs(second.route, Route.SCIENTIFIC_RETRIEVAL)

    def test_confirmation_cannot_override_the_router(self):
        """Verify confirming an intent the router would not suggest changes nothing."""
        graph = self.graph(temperature=0.5)
        decision = graph.advance(self.request("cannabis psychosis", Intent.GENERAL_CONVERSATION))
        self.assertIs(decision.route, Route.CLARIFY_INTENT)
        unfamiliar = graph.advance(self.request("purple bicycle", Intent.GENERAL_CONVERSATION))
        self.assertIs(unfamiliar.route, Route.CLARIFY_INTENT)
        self.assertIsNone(unfamiliar.suggested_intent)

    def test_unsupported_intent_is_never_suggested_or_confirmable(self):
        """Verify unsafe guesses get the generic menu and cannot be confirmed."""
        decision = self.graph(temperature=0.5).advance(self.request("my dose"))
        self.assertIs(decision.route, Route.CLARIFY_INTENT)
        self.assertIsNone(decision.suggested_intent)
        with self.assertRaises(ValueError):
            self.request("my dose", Intent.UNSUPPORTED_OR_UNSAFE)

    def test_live_routing_counts_without_text(self):
        """Verify graph observations feed aggregate routing stats and never retain text."""
        monitor = Monitor(ROOT)
        self.assertEqual(monitor.live_routing(), {"n": 0})
        graph = self.graph(observer=monitor.record_intent, temperature=0.5)
        for text, confirmed in (("calculate my risk", None), ("cannabis psychosis", None),
                                ("cannabis psychosis", Intent.SCIENTIFIC_QUESTION),
                                ("purple bicycle", None)):
            graph.advance(self.request(text, confirmed))
        routing = monitor.live_routing()
        self.assertEqual(routing["n"], 4)
        self.assertAlmostEqual(routing["clarification_rate"], 0.5)
        self.assertAlmostEqual(routing["suggestion_share"], 0.5)
        self.assertEqual(routing["confirmed_suggestions"], 1)
        self.assertAlmostEqual(routing["rule_share"], 0.25)
        self.assertEqual(routing["routed_intents"],
                         {"risk_assessment": 1, "scientific_question": 1})
        self.assertNotIn("bicycle", str(monitor.snapshot()))

    def test_observer_failure_does_not_change_routing(self):
        """Verify a failing monitoring callback leaves the routing decision intact."""
        def broken(_decision):
            """Simulate a monitoring failure."""
            raise RuntimeError("monitor down")

        decision = self.graph(observer=broken).advance(self.request("calculate my risk"))
        self.assertIs(decision.route, Route.ASSESSMENT_REDIRECTION)

    def test_calibration_matches_current_utterances(self):
        """Verify the committed calibration was produced from the committed utterances."""
        calibration = json.loads((ROOT / CALIBRATION_PATH).read_text(encoding="utf-8"))
        utterances = (ROOT / UTTERANCES_PATH).read_text(encoding="utf-8")
        self.assertEqual(calibration["utterances_sha256"], sha256_text(utterances))
        self.assertEqual(calibration["settings"]["routing_threshold"], 0.85)


class FixedIntentPort:
    """Return one preset intent decision for every message."""

    def __init__(self, intent, confidence, rationale="semantic"):
        """Store the decision fields to return."""
        self.decision = IntentDecision(intent, confidence, rationale == "semantic_unfamiliar",
                                       "fixture", "fixture-sha", "fixture-calibration",
                                       "fixture-router", rationale)

    def classify(self, text):
        """Return the preset decision regardless of text."""
        return self.decision


class ClarificationReplyTests(unittest.TestCase):
    """Check the user-facing clarification text and actions."""

    @staticmethod
    def reply(intent, confidence, rationale="semantic", confirmed=None):
        """Run one message through a conversation whose router returns a fixed decision."""
        graph = RoutingGraph(PrototypeSafetyPort(), PrototypeLanguagePort(),
                             FixedIntentPort(intent, confidence, rationale))
        return ProtectedConversationOrchestrator(graph, research=None, generator=None).handle(
            "some message", deployment_mode="prototype_demo", session_valid=True,
            confirmed_intent=confirmed)

    def test_near_miss_asks_about_best_guess(self):
        """Verify the reply names the guess and offers Yes plus the generic options."""
        result = self.reply(Intent.SCIENTIFIC_QUESTION, 0.65)
        self.assertEqual(result["response_kind"], "INTENT_CLARIFICATION_REQUIRED")
        self.assertIn("what the research says", result["message"])
        self.assertEqual([action["id"] for action in result["actions"]], [
            "confirm_intent", "submit_risk_assessment_questionnaire",
            "ask_about_schizophrenia_and_clinical_associations"])
        self.assertEqual(result["actions"][0]["intent"], "scientific_question")

    def test_assessment_guess_confirms_by_opening_questionnaire(self):
        """Verify a risk-assessment guess offers the questionnaire as its Yes action."""
        result = self.reply(Intent.RISK_ASSESSMENT, 0.6)
        self.assertEqual(result["actions"][0]["id"], "submit_risk_assessment_questionnaire")
        self.assertEqual(result["actions"][0]["label"], "Yes, open the questionnaire")
        self.assertNotIn("confirm_intent", [action["id"] for action in result["actions"]])

    def test_low_confidence_unfamiliar_or_unsafe_get_generic_menu(self):
        """Verify no guess is named when it is weak, unfamiliar or unsupported."""
        for intent, confidence, rationale in (
            (Intent.SCIENTIFIC_QUESTION, 0.3, "semantic"),
            (Intent.SCIENTIFIC_QUESTION, 0.7, "semantic_unfamiliar"),
            (Intent.UNSUPPORTED_OR_UNSAFE, 0.7, "semantic"),
        ):
            with self.subTest(intent=intent, rationale=rationale):
                result = self.reply(intent, confidence, rationale)
                self.assertTrue(result["message"].startswith("I didn't quite catch that"))
                self.assertEqual(len(result["actions"]), 2)

    def test_confirmed_general_question_is_answered(self):
        """Verify a verified confirmation leaves clarification and reaches its route."""
        result = self.reply(Intent.GENERAL_CONVERSATION, 0.7,
                            confirmed="general_conversation")
        self.assertEqual(result["response_kind"], "CONVERSATION")


@unittest.skipUnless(
    (ROOT / "data/indexes/models/BGE-Small-EN-v1.5/model.safetensors").is_file(),
    "pinned router encoder is not provisioned",
)
class PinnedSemanticRouterTests(unittest.TestCase):
    """Smoke-test the provisioned encoder on paraphrases the old rules misrouted."""

    @classmethod
    def setUpClass(cls):
        """Load the pinned router once for all smoke cases."""
        cls.port = HybridIntentPort(lambda: load_semantic_router(ROOT))

    def test_paraphrases_route_to_expected_intents(self):
        """Verify representative paraphrases reach the right route with confidence."""
        cases = {
            "could you figure out how likely I am to become psychotic": Intent.RISK_ASSESSMENT,
            "does smoking weed lead to schizophrenia": Intent.SCIENTIFIC_QUESTION,
            "what dose of olanzapine should I take": Intent.UNSUPPORTED_OR_UNSAFE,
        }
        for text, intent in cases.items():
            with self.subTest(text=text):
                decision = self.port.classify(text)
                self.assertIs(decision.intent, intent)
                self.assertGreaterEqual(decision.calibrated_confidence, 0.85)
                self.assertFalse(decision.requires_clarification)
