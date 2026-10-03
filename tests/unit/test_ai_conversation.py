"""Protected conversational orchestration tests use synthetic non-user fixtures."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

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
    """Provide fake research fixtures and assertions."""
    def __init__(self, result=None, general_result=None) -> None:
        """Initialize the synthetic test fixture and its observable state."""
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
        self.general_result = general_result or {
            "status": "general_evidence_available",
            "answer": None,
            "limitation": "Research only; corpus limited.",
            "corpus_version": "fixture-corpus",
            "citations": [{
                "citation_id": "S1", "pmid": "456", "title": "Fixture title",
                "exact_matched_text": "Fixture evidence about schizophrenia.",
                "bounded_use": "General research context.",
            }],
        }

    def answer_text(self, question):
        """Answer a free-text research question through the bounded evidence workflow."""
        self.calls.append(question)
        return self.result

    def search_general(self, question):
        """Retrieve broader corpus passages for a general research question."""
        self.calls.append(f"general:{question}")
        return self.general_result


class FakeGenerator:
    """Provide fake generator fixtures and assertions."""
    provider = LLMProvider.OPENAI
    model = "fixture-model"

    def __init__(self, drafts=None) -> None:
        """Initialize the synthetic test fixture and its observable state."""
        self.calls = []
        self.drafts = list(drafts or [AssistantDraft(
            response_kind="grounded_answer",
            text="Synthetic approved finding [S1].",
            citation_ids=["S1"],
        )])

    def generate(self, request):
        """Generate and validate an assistant draft using the configured provider."""
        self.calls.append(request)
        return self.drafts.pop(0)


def orchestrator(research=None, generator=None):
    """Provide orchestrator behavior for synthetic test fixtures."""
    return ProtectedConversationOrchestrator(
        RoutingGraph(PrototypeSafetyPort(), PrototypeLanguagePort(), PrototypeIntentPort()),
        research or FakeResearch(), generator if generator is not None else FakeGenerator(),
    )


class ConversationTests(unittest.TestCase):
    """Provide conversation tests fixtures and assertions."""
    def test_separate_judge_does_not_use_chat_generator(self):
        """Route quality requests to the distinct judge and close each owned adapter once."""
        chat = MagicMock()
        judge = MagicMock(model="independent-judge", provider=LLMProvider.GEMINI)
        judge.generate.return_value = AssistantDraft(response_kind="conversation", citation_ids=[],
            text='{"correctness": 0.8, "groundedness": null, "quality_label": "acceptable"}')
        service = ProtectedConversationOrchestrator(None, FakeResearch(), chat, judge=judge)
        result = service.evaluate_response("Question", {"message": "Answer", "citations": []})
        self.assertEqual(result["judge_model"], "independent-judge")
        self.assertEqual(result["quality_label"], "acceptable")
        chat.generate.assert_not_called()
        judge.generate.assert_called_once()
        service.close()
        chat.close.assert_called_once()
        judge.close.assert_called_once()

    def test_live_judge_context_and_no_passage_groundedness(self):
        """Verify live judge context and no passage groundedness."""
        generator = FakeGenerator([AssistantDraft(
            response_kind="conversation", citation_ids=[],
            text='{"correctness": 0.8, "groundedness": 1, "quality_label": "good"}',
        )])
        service = orchestrator(generator=generator)
        scores = service.evaluate_response("Fixture question", {
            "message": "Fixture answer", "citations": [],
        })
        self.assertEqual(scores["correctness"], .8)
        self.assertIsNone(scores["groundedness"])
        self.assertNotIn("Fixture answer", str(scores))
        self.assertIn("NO verified reference", generator.calls[0].system_instruction)

    def test_live_judge_rejects_malformed_scores(self):
        """Verify live judge rejects malformed scores."""
        for text in ('{"correctness": true, "groundedness": 0.5}',
                     '{"correctness": 1.1, "groundedness": null}',
                     '{"correctness": 0.5}', '[]'):
            with self.subTest(text=text):
                generator = FakeGenerator([AssistantDraft(
                    response_kind="conversation", citation_ids=[], text=text,
                )])
                with self.assertRaises(ValueError):
                    orchestrator(generator=generator).evaluate_response("Fixture", {
                        "message": "Fixture answer", "citations": [],
                    })

    def test_curated_question_reaches_rag_then_validated_generator(self) -> None:
        """Verify curated question reaches rag then validated generator."""
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
        """Verify invalid generated claim retries once then fails closed."""
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
        """Verify invalid first draft can recover once."""
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
        """Verify no evidence never reaches generator."""
        no_evidence = {
            "status": "no_adequate_evidence", "answer": "No adequate evidence.",
            "limitation": "Research only.", "citations": [],
        }
        research = FakeResearch(no_evidence, no_evidence)
        generator = FakeGenerator()
        result = orchestrator(research, generator).handle(
            "What does research say about genetics and substance use?",
            deployment_mode="prototype_demo", session_valid=True,
        )
        self.assertEqual(result["response_kind"], "NO_ELIGIBLE_EVIDENCE")
        self.assertEqual(len(generator.calls), 0)

    def test_schizophrenia_education_uses_general_corpus_retrieval(self) -> None:
        """Verify schizophrenia education uses general corpus retrieval."""
        research = FakeResearch({
            "status": "no_adequate_evidence", "answer": "No adequate evidence.",
            "limitation": "Research only.", "citations": [],
        })
        answer = "Schizophrenia is discussed in the retrieved research context [S1]."
        generator = FakeGenerator([AssistantDraft(
            response_kind="grounded_answer", text=answer, citation_ids=["S1"],
        )])
        result = orchestrator(research, generator).handle(
            "Tell me about schizophrenia",
            deployment_mode="prototype_demo", session_valid=True,
        )
        self.assertEqual(result["response_kind"], "GROUNDED_ANSWER")
        self.assertEqual(result["message"], answer)
        self.assertEqual(len(result["citations"]), 1)
        self.assertEqual(len(research.calls), 2)

    def test_general_evidence_normalizes_missing_inline_citation_without_retry(self) -> None:
        """Verify general evidence normalizes missing inline citation without retry."""
        no_curated = {
            "status": "no_adequate_evidence", "answer": "No adequate evidence.",
            "limitation": "Research only.", "citations": [],
        }
        research = FakeResearch(no_curated)
        generator = FakeGenerator([AssistantDraft(
            response_kind="conversation",
            text="Schizophrenia is discussed in the retrieved research context.",
            citation_ids=["[S1]"],
        )])
        result = orchestrator(research, generator).handle(
            "Tell me about schizophrenia",
            deployment_mode="prototype_demo", session_valid=True,
        )
        self.assertEqual(result["response_kind"], "GROUNDED_ANSWER")
        self.assertTrue(result["message"].endswith("[S1]"))
        self.assertEqual(len(generator.calls), 1)

    def test_regular_conversation_uses_llm_without_retrieval(self) -> None:
        """Verify regular conversation uses llm without retrieval."""
        research = FakeResearch()
        generator = FakeGenerator([AssistantDraft(
            response_kind="conversation", text="That sounds like a good place to start.",
            citation_ids=[],
        )])
        result = orchestrator(research, generator).handle(
            "Help me organize my study plan",
            deployment_mode="prototype_demo", session_valid=True,
        )
        self.assertEqual(result["response_kind"], "CONVERSATION")
        self.assertEqual(research.calls, [])
        self.assertEqual(len(generator.calls), 1)

    def test_corpus_abstention_falls_back_to_labeled_general_education(self) -> None:
        """Verify corpus abstention falls back to labeled general education."""
        research = FakeResearch({
            "status": "no_adequate_evidence", "answer": "No adequate evidence.",
            "citations": [],
        })
        generator = FakeGenerator([
            AssistantDraft(response_kind="refusal", text="The passages do not cover this."),
            AssistantDraft(response_kind="conversation", text="A general educational overview."),
        ])
        result = orchestrator(research, generator).handle(
            "Tell me about schizophrenia", deployment_mode="prototype_demo", session_valid=True,
        )
        self.assertEqual(result["response_kind"], "GENERAL_EDUCATION")
        self.assertEqual(result["citations"], [])
        self.assertEqual(result["message"], "A general educational overview.")

    def test_specific_research_abstention_does_not_use_general_knowledge(self) -> None:
        """Verify specific research abstention does not use general knowledge."""
        research = FakeResearch({
            "status": "no_adequate_evidence", "answer": "No adequate evidence.",
            "citations": [],
        })
        generator = FakeGenerator([
            AssistantDraft(response_kind="refusal", text="The passages do not cover this."),
        ])
        result = orchestrator(research, generator).handle(
            "Is schizophrenia associated with cannabis use?",
            deployment_mode="prototype_demo", session_valid=True,
        )
        self.assertEqual(result["response_kind"], "NO_ELIGIBLE_EVIDENCE")
        self.assertEqual(len(generator.calls), 1)

    def test_assessment_explanation_preserves_exact_values(self) -> None:
        """Verify assessment explanation preserves exact values."""
        text = (
            "The separate outputs are 12.3% and 45.6%. Psychotic and manic patterns inform the "
            "positive category, while depressive patterns inform the negative category. They are "
            "not a diagnosis and not a causal explanation. The synthetic data model uses "
            "generic_genetic_profile_v1; genetic values were not measured from you."
        )
        generator = FakeGenerator([AssistantDraft(
            response_kind="conversation", text=text, citation_ids=[],
        )])
        result = orchestrator(generator=generator).explain_assessment({
            "positive_symptom_research_probability": "12.3%",
            "negative_symptom_research_probability": "45.6%",
            "generic_profile_version": "generic_genetic_profile_v1",
        })
        self.assertEqual(result["message"], text)
        self.assertTrue(result["generated_by_llm"])

    def test_safety_language_and_assessment_routes_deny_tools(self) -> None:
        """Verify safety language and assessment routes deny tools."""
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
