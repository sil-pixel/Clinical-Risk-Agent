import unittest

from clinical_risk_agent.ai import (
    Intent,
    PreflightRequest,
    PromptGuardIntentPort,
    PrototypeIntentPort,
    PrototypeLanguagePort,
    PrototypeSafetyPort,
    ProtectedConversationOrchestrator,
    Route,
    RoutingGraph,
)
from clinical_risk_agent.ai.generation import AssistantDraft, LLMProvider
from clinical_risk_agent.ai.routing import IntentDecision, RequestKind


class CountingScorer:
    """Score text containing 'ATTACK' as an attack; count calls."""

    def __init__(self):
        """Start with no calls."""
        self.calls = 0

    def score(self, text):
        """Return a high score for marked text."""
        self.calls += 1
        return 0.9 if "ATTACK" in text else 0.1


class FixedPort:
    """Return one preset decision for any text and count calls."""

    def __init__(self, intent, confidence, rationale="semantic"):
        """Store the decision to return."""
        self.calls = 0
        self.decision = IntentDecision(intent, confidence, False, "fixture", "sha", "cal",
                                       "router", rationale)

    def classify(self, text):
        """Return the preset decision."""
        self.calls += 1
        return self.decision


def guarded(base, scorer):
    """Wrap a port with a fixture Prompt Guard."""
    return PromptGuardIntentPort(base, lambda: scorer, threshold=0.5, model_id="guard",
                                 model_sha256="sha")


class PromptGuardScopeTests(unittest.TestCase):
    """Check Prompt Guard runs only where a message can reach the LLM."""

    def test_fixed_reply_routes_skip_the_guard(self):
        """Verify assessment, unsupported and weak clarifications are not screened."""
        for intent, confidence in ((Intent.RISK_ASSESSMENT, 1.0),
                                   (Intent.UNSUPPORTED_OR_UNSAFE, 0.95),
                                   (Intent.SCIENTIFIC_QUESTION, 0.3)):
            with self.subTest(intent=intent, confidence=confidence):
                scorer = CountingScorer()
                guarded(FixedPort(intent, confidence), scorer).classify("ATTACK text")
                self.assertEqual(scorer.calls, 0)

    def test_unfamiliar_text_is_screened(self):
        """Verify text unlike any reference example is still checked for injection."""
        scorer = CountingScorer()
        decision = guarded(FixedPort(Intent.GENERAL_CONVERSATION, 0.95, "semantic_unfamiliar"),
                           scorer).classify("ATTACK text")
        self.assertEqual(scorer.calls, 1)
        self.assertEqual(decision.rationale_code, "prompt_injection")

    def test_llm_bound_and_confirmable_routes_are_screened(self):
        """Verify routed LLM intents and confirmable suggestions are screened and blocked."""
        for confidence in (0.95, 0.6):  # routed, or a suggestion the user could confirm
            with self.subTest(confidence=confidence):
                scorer = CountingScorer()
                decision = guarded(FixedPort(Intent.GENERAL_CONVERSATION, confidence),
                                   scorer).classify("ATTACK text")
                self.assertEqual(scorer.calls, 1)
                self.assertEqual(decision.rationale_code, "prompt_injection")


class RecordingGenerator:
    """Return a fixed conversation draft and count calls."""
    provider = LLMProvider.GEMINI
    model = "fixture-model"

    def __init__(self, text="Hello there."):
        """Store the draft text."""
        self.text = text
        self.calls = 0

    def generate(self, request):
        """Count the call and return the draft."""
        self.calls += 1
        return AssistantDraft(response_kind="conversation", text=self.text)


class ResponseCacheTests(unittest.TestCase):
    """Check fixed replies are cached by message and nothing personal or generated is."""

    def conversation(self, port, generator=None):
        """Build an orchestrator around a given intent port."""
        graph = RoutingGraph(PrototypeSafetyPort(), PrototypeLanguagePort(), port)
        return ProtectedConversationOrchestrator(graph, None, generator)

    def ask(self, conversation, text, **kwargs):
        """Send one message through the orchestrator."""
        return conversation.handle(text, deployment_mode="prototype_demo", session_valid=True,
                                   **kwargs)

    def test_fixed_reply_is_served_from_cache(self):
        """Verify a repeated fixed reply skips routing and is marked cached."""
        port = FixedPort(Intent.RISK_ASSESSMENT, 1.0)
        conversation = self.conversation(port)
        first = self.ask(conversation, "please assess me")
        second = self.ask(conversation, "please assess me")
        self.assertEqual(first["response_kind"], "ASSESSMENT_REDIRECTION")
        self.assertNotIn("cached", first)
        self.assertTrue(second["cached"])
        self.assertEqual(port.calls, 1)
        self.ask(conversation, "please assess me", confirmed_intent="scientific_question")
        self.assertEqual(port.calls, 2)  # a different confirmation is a different key

    def test_generated_and_personal_replies_are_not_cached(self):
        """Verify LLM replies and anything using the session result always recompute."""
        generator = RecordingGenerator()
        conversation = self.conversation(FixedPort(Intent.GENERAL_CONVERSATION, 0.95),
                                         generator)
        self.ask(conversation, "hi there friend")
        self.assertNotIn("cached", self.ask(conversation, "hi there friend"))
        self.assertEqual(generator.calls, 2)
        port = FixedPort(Intent.RISK_ASSESSMENT, 1.0)
        conversation = self.conversation(port)
        for _ in range(2):
            self.ask(conversation, "please assess me", prior_result={"x": 1})
        self.assertEqual(port.calls, 2)

    def test_safety_response_checks_only_the_safety_rules(self):
        """Verify the fast safety check returns a reply for crises and None otherwise."""
        port = FixedPort(Intent.RISK_ASSESSMENT, 1.0)
        conversation = self.conversation(port)
        crisis = conversation.safety_response("I want to kill myself",
                                              deployment_mode="prototype_demo")
        self.assertEqual(crisis["response_kind"], "CRITICAL_SAFETY_REDIRECTION")
        self.assertIsNone(conversation.safety_response("does cannabis cause psychosis",
                                                       deployment_mode="prototype_demo"))
        self.assertEqual(port.calls, 0)


class CuratedCacheTests(unittest.TestCase):
    """Check verified curated wording is reused instead of re-formatting it."""

    def test_curated_answer_formatted_once(self):
        """Verify the second identical curated answer makes no generation call."""
        generator = RecordingGenerator("Approved finding [S1].")
        generator.generate = lambda request, g=generator: (
            setattr(g, "calls", g.calls + 1) or AssistantDraft(
                response_kind="grounded_answer", text="Approved finding [S1].",
                citation_ids=["S1"]))
        graph = RoutingGraph(PrototypeSafetyPort(), PrototypeLanguagePort(),
                             PrototypeIntentPort())
        conversation = ProtectedConversationOrchestrator(graph, None, generator)
        result = {"answer": "Approved finding [S1].",
                  "citations": [{"citation_id": "S1", "exact_matched_text": "Evidence."}]}
        self.assertEqual(conversation._generate_validated(result), "Approved finding [S1].")
        self.assertEqual(conversation._generate_validated(result), "Approved finding [S1].")
        self.assertEqual(generator.calls, 1)
