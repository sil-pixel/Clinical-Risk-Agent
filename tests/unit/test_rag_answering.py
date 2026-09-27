"""Bounded research answers use synthetic retrieval records only."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

SOURCE_ROOT = Path(__file__).resolve().parents[2] / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from clinical_risk_agent.contracts import EvidenceStatus, RetrievalMode  # noqa: E402
from clinical_risk_agent.rag.answering import (  # noqa: E402
    BoundedResearchAnswerer,
    CURATED_QUESTIONS,
)


def supported_result(pmid: str = "21382538", *, citation_id: str = "S1",
                     excerpt: str = "Synthetic exact passage") -> SimpleNamespace:
    item = SimpleNamespace(
        pmid=pmid, citation_id=citation_id, source_id=f"pmid:{pmid}",
        chunk_id="synthetic-chunk", exact_matched_text=excerpt,
    )
    display = SimpleNamespace(
        citation_id=citation_id, source_id=item.source_id,
        exact_matched_text=excerpt, title="Synthetic paper",
    )
    return SimpleNamespace(
        status=EvidenceStatus.SUFFICIENT, items=(item,), displays=(display,),
        retrieval_mode=RetrievalMode.PRIMARY_HYBRID, corpus_version="fixture-v1",
    )


class AnsweringTests(unittest.TestCase):
    def setUp(self) -> None:
        self.calls: list[tuple] = []
        self.result = supported_result()

        def retrieve(question: str, claim_id: str) -> SimpleNamespace:
            self.calls.append(("supported", question, claim_id))
            return self.result

        def explore(question: str, limit: int) -> dict:
            self.calls.append(("explore", question, limit))
            return {"match_status": "matches_found", "matches": [
                {"pmid": "fixture", "citation_id": "S1"},
            ]}

        self.answerer = BoundedResearchAnswerer(
            claim_ids={item.claim_id for item in CURATED_QUESTIONS},
            retrieve_supported=retrieve, exploratory_search=explore,
            bounded_use=lambda pmid: f"Fixture bounded use for {pmid}",
        )

    def test_exact_question_returns_cited_bounded_answer(self) -> None:
        question = CURATED_QUESTIONS[0].question.upper().rstrip("?") + "!"
        result = self.answerer.answer(question)
        self.assertEqual(result["status"], "curated_support_available")
        self.assertEqual(result["claim_id"], CURATED_QUESTIONS[0].claim_id)
        self.assertEqual(result["citations"][0]["pmid"], "21382538")
        self.assertEqual(result["citations"][0]["exact_matched_text"],
                         "Synthetic exact passage")
        self.assertIn("meta-analysis", result["answer"])
        self.assertEqual([call[0] for call in self.calls], ["supported"])

    def test_near_misses_abstain_without_trusted_claim_routing(self) -> None:
        for question in (
            "Is childhood ADHD associated with later diagnosed alcohol use disorder?",
            "Did the MTA childhood ADHD cohort find more diagnosed substance use disorder by age 25?",
            "Is cyberbullying victimization associated with later diagnosed substance use disorder?",
            "Is bullying victimization associated with smoking or drinking at age 13?",
        ):
            with self.subTest(question=question):
                result = self.answerer.answer(question)
                self.assertEqual(result["status"], "no_adequate_evidence")
                self.assertEqual(result["citations"], [])
                self.assertEqual(result["related_unverified_passages"], [{
                    "pmid": "fixture", "support_status": "not_verified_for_this_question",
                }])
        self.assertTrue(all(call[0] == "explore" for call in self.calls))

    def test_wrong_source_or_citation_abstains(self) -> None:
        for result in (supported_result(pmid="99999999"),
                       supported_result(citation_id="S2"),
                       supported_result(excerpt="changed")):
            with self.subTest(result=result):
                self.result = result
                if result.items[0].exact_matched_text == "changed":
                    result.displays[0].exact_matched_text = "different"
                answer = self.answerer.answer(CURATED_QUESTIONS[0].question)
                self.assertEqual(answer["status"], "no_adequate_evidence")
                self.assertEqual(answer["citations"], [])

    def test_support_failure_and_exploration_outage_fail_closed(self) -> None:
        self.result = SimpleNamespace(status=EvidenceStatus.RETRIEVAL_UNAVAILABLE)
        result = self.answerer.answer(CURATED_QUESTIONS[0].question)
        self.assertEqual(result["status"], "retrieval_unavailable")
        self.assertEqual(result["citations"], [])

        answerer = BoundedResearchAnswerer(
            claim_ids={item.claim_id for item in CURATED_QUESTIONS},
            retrieve_supported=lambda *_: supported_result(),
            exploratory_search=lambda *_: (_ for _ in ()).throw(RuntimeError("outage")),
            bounded_use=lambda _: "fixture",
        )
        self.assertEqual(answerer.answer("Other research question")["status"],
                         "retrieval_unavailable")

    def test_invalid_question_and_missing_catalog_fail_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "3 to 500"):
            self.answerer.answer("  ")
        with self.assertRaisesRegex(ValueError, "catalog"):
            BoundedResearchAnswerer(
                claim_ids=set(), retrieve_supported=lambda *_: supported_result(),
                exploratory_search=lambda *_: {}, bounded_use=lambda _: "fixture",
            )


if __name__ == "__main__":
    unittest.main()
