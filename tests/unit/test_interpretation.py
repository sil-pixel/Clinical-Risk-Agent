import unittest

from clinical_risk_agent.ai import (
    PrototypeIntentPort,
    PrototypeLanguagePort,
    PrototypeSafetyPort,
    ProtectedConversationOrchestrator,
    RoutingGraph,
)
from clinical_risk_agent.ai.generation import AssistantDraft, LLMProvider
from clinical_risk_agent.interpretation import fallback_explanation, interpret, ordinal

QUANTILES = [i / 100 for i in range(101)]  # percentile p sits at value p/100
RESULT = {
    "positive_symptom_research_probability": "35.0%",
    "negative_symptom_research_probability": "20.0%",
    "positive_reference": interpret(0.92, QUANTILES),
    "negative_reference": interpret(0.10, QUANTILES),
}


class ScriptedGenerator:
    """Return queued drafts and record each request."""
    provider = LLMProvider.GEMINI
    model = "fixture-model"

    def __init__(self, *texts):
        """Queue conversation drafts with the given texts."""
        self.drafts = [AssistantDraft(response_kind="conversation", text=t) for t in texts]
        self.requests = []

    def generate(self, request):
        """Record the request and return the next queued draft."""
        self.requests.append(request)
        return self.drafts.pop(0)


def orchestrator(generator=None):
    """Build an orchestrator with rules routing and an optional generator."""
    graph = RoutingGraph(PrototypeSafetyPort(), PrototypeLanguagePort(), PrototypeIntentPort())
    return ProtectedConversationOrchestrator(graph, None, generator)


class InterpretationTests(unittest.TestCase):
    """Check percentile placement, levels and the deterministic fallback."""

    def test_levels_follow_reference_percentiles(self):
        """Verify level boundaries at the 25th, 75th and 90th percentiles."""
        cases = {0.10: ("low", 10), 0.25: ("typical", 25), 0.74: ("typical", 74),
                 0.75: ("above typical", 75), 0.90: ("high", 90), 1.5: ("high", 99),
                 -1.0: ("low", 0)}
        for value, (level, percentile) in cases.items():
            with self.subTest(value=value):
                self.assertEqual(interpret(value, QUANTILES)["level"], level)
                self.assertEqual(interpret(value, QUANTILES)["percentile"], percentile)
        self.assertEqual(interpret(-1.0, QUANTILES)["percentile_text"], "lowest percentile")
        self.assertEqual(interpret(1.5, QUANTILES)["percentile_text"], "highest percentile")
        with self.assertRaises(ValueError):
            interpret(0.5, [0.0, 1.0])

    def test_ordinals(self):
        """Verify English ordinal suffixes, including the teens."""
        self.assertEqual([ordinal(n) for n in (1, 2, 3, 11, 12, 13, 21, 92)],
                         ["1st", "2nd", "3rd", "11th", "12th", "13th", "21st", "92nd"])

    def test_fallback_states_values_levels_and_meaning(self):
        """Verify the fixed explanation includes both scores, levels and definitions."""
        text = fallback_explanation(RESULT)
        for term in ("35.0%", "high", "92nd percentile", "20.0%", "low", "10th percentile",
                     "psychotic and manic", "depressive", "not a diagnosis"):
            self.assertIn(term, text)


class ExplanationTests(unittest.TestCase):
    """Check the level-aware explanation and chat follow-ups."""

    GOOD = ("Your positive-symptom estimate is 35.0%, which is high: the 92nd percentile of the "
            "synthetic reference group. Your negative-symptom estimate is 20.0%, a low level at "
            "the 10th percentile. Ask me anything about these results.")

    def test_explanation_preserves_scores_and_percentiles(self):
        """Verify a compliant draft is used and the result context reaches the model."""
        generator = ScriptedGenerator(self.GOOD)
        explanation = orchestrator(generator).explain_assessment(RESULT)
        self.assertTrue(explanation["generated_by_llm"])
        self.assertEqual(explanation["message"], self.GOOD)
        self.assertIn("92nd percentile", generator.requests[0].evidence_context)

    def test_invented_number_or_missing_percentile_uses_fallback(self):
        """Verify drafts that add a percentage or drop a percentile are rejected."""
        for text in (self.GOOD + " About 40% of people like you develop symptoms.",
                     self.GOOD.replace("92nd percentile", "top group")):
            with self.subTest(text=text[-40:]):
                explanation = orchestrator(ScriptedGenerator(text)).explain_assessment(RESULT)
                self.assertFalse(explanation["generated_by_llm"])
                self.assertEqual(explanation["message"], fallback_explanation(RESULT))

    def test_chat_followup_uses_session_result(self):
        """Verify 'explain my result' in chat answers from the person's own scores."""
        reply = "Your 35.0% positive-symptom estimate is high for this model, at the 92nd percentile."
        generator = ScriptedGenerator(reply)
        result = orchestrator(generator).handle(
            "explain my result please", deployment_mode="prototype_demo", session_valid=True,
            prior_result=RESULT)
        self.assertEqual(result["response_kind"], "RESULT_EXPLANATION")
        self.assertEqual(result["message"], reply)
        self.assertIn("explain my result", generator.requests[0].user_text)

    def test_chat_without_result_keeps_no_result_reply(self):
        """Verify the route still says there is no result when none exists."""
        result = orchestrator(ScriptedGenerator()).handle(
            "explain my result", deployment_mode="prototype_demo", session_valid=True)
        self.assertEqual(result["response_kind"], "NO_PRIOR_ASSESSMENT_RESULT")
