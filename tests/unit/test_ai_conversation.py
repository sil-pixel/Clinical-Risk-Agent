"""Protected conversational orchestration tests use synthetic non-user fixtures."""

from __future__ import annotations

import unittest

from clinical_risk_agent.ai import (
    AssistantDraft,
    LLMProvider,
    ProtectedConversationOrchestrator,
    PrototypeIntentPort,
    PrototypeLanguagePort,
    PrototypeSafetyPort,
    RoutingGraph,
)
from clinical_risk_agent.rag.answering import CURATED_QUESTIONS


class FakeResearch:
    def __init__(self, result=None) -> None:
        self.calls = []
        self.result = result or {
            "status": "curated_support_available",
            "answer": "Synthetic approved finding [S1].",
            "limitation": "Research only.",
            "corpus_version": "fixture-corpus",
            "citations": [{
                "citation_id": "S1", "pmid": "123",
                "exact_matched_text": "Synthetic exact evidence passage.",
            }],
        }

    def answer_text(self, question):
        self.calls.append(question)
        return self.result


class FakeGenerator:
    provider = LLMProvider.OPENAI
    model = "fixture-model"

    def __init__(self, drafts=None) -> None:
        self.calls = []
        self.drafts = list(drafts or [AssistantDraft(
            response_kind="grounded_answer",
            text="Synthetic approved finding [S1].",
            citation_ids=["S1"],
        )])

    def generate(self, request):
        self.calls.append(request)
        return self.drafts.pop(0)


def orchestrator(research=None, generator=None):
    return ProtectedConversationOrchestrator(
        RoutingGraph(PrototypeSafetyPort(), PrototypeLanguagePort(), PrototypeIntentPort()),
        research or FakeResearch(), generator if generator is not None else FakeGenerator(),
    )


class ConversationTests(unittest.TestCase):
    def test_curated_question_reaches_rag_then_validated_generator(self) -> None:
        research = FakeResearch()
        generator = FakeGenerator()
        result = orchestrator(research, generator).handle(
            CURATED_QUESTIONS[0].question,
            deployment_mode="prototype_demo", session_valid=True,
        )
        self.assertEqual(result["response_kind"], "GROUNDED_ANSWER")
        self.assertEqual(result["message"], "Synthetic approved finding [S1].")
        self.assertEqual(result["provider"], "openai")
        self.assertEqual(result["model"], "fixture-model")
        self.assertEqual(len(research.calls), 1)
        self.assertEqual(len(generator.calls), 1)
        self.assertNotIn(CURATED_QUESTIONS[0].question, repr(generator.calls[0]))

    def test_invalid_generated_claim_retries_once_then_fails_closed(self) -> None:
        invalid = AssistantDraft(
            response_kind="grounded_answer", text="Invented claim [S1].", citation_ids=["S1"],
        )
        generator = FakeGenerator([invalid, invalid])
        result = orchestrator(generator=generator).handle(
            CURATED_QUESTIONS[0].question,
            deployment_mode="prototype_demo", session_valid=True,
        )
        self.assertEqual(result["response_kind"], "GENERATION_UNAVAILABLE")
        self.assertEqual(result["citations"], [])
        self.assertEqual(len(generator.calls), 2)

    def test_invalid_first_draft_can_recover_once(self) -> None:
        generator = FakeGenerator([
            AssistantDraft(
                response_kind="grounded_answer", text="Changed [S1].", citation_ids=["S1"],
            ),
            AssistantDraft(
                response_kind="grounded_answer",
                text="Synthetic approved finding [S1].", citation_ids=["S1"],
            ),
        ])
        result = orchestrator(generator=generator).handle(
            CURATED_QUESTIONS[0].question,
            deployment_mode="prototype_demo", session_valid=True,
        )
        self.assertEqual(result["response_kind"], "GROUNDED_ANSWER")
        self.assertEqual(len(generator.calls), 2)

    def test_no_evidence_never_reaches_generator(self) -> None:
        research = FakeResearch({
            "status": "no_adequate_evidence", "answer": "No adequate evidence.",
            "limitation": "Research only.", "citations": [],
        })
        generator = FakeGenerator()
        result = orchestrator(research, generator).handle(
            "What does research say about genetics and substance use?",
            deployment_mode="prototype_demo", session_valid=True,
        )
        self.assertEqual(result["response_kind"], "NO_ELIGIBLE_EVIDENCE")
        self.assertEqual(len(generator.calls), 0)

    def test_safety_language_and_assessment_routes_deny_tools(self) -> None:
        fixtures = (
            ("What medication should I start?", "PRESCRIPTIVE_REFUSAL"),
            ("I want to kill myself", "CRITICAL_SAFETY_REDIRECTION"),
            ("नमस्ते", "LANGUAGE_UNSUPPORTED"),
            ("Please calculate my risk", "ASSESSMENT_REDIRECTION"),
        )
        for text, expected in fixtures:
            with self.subTest(text=text):
                research = FakeResearch()
                generator = FakeGenerator()
                result = orchestrator(research, generator).handle(
                    text, deployment_mode="prototype_demo", session_valid=True,
                )
                self.assertEqual(result["response_kind"], expected)
                self.assertEqual(research.calls, [])
                self.assertEqual(generator.calls, [])


if __name__ == "__main__":
    unittest.main()
