"""Synthetic records only: these are not real scientific citations."""

from __future__ import annotations

import sys
import unittest
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parents[2] / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from clinical_risk_agent.contracts import (  # noqa: E402
    AttemptStatus,
    EvidenceStatus,
    RetrievalMode,
    RetrievalQuery,
)
from clinical_risk_agent.rag import ScientificSource, SourceSection, chunk_source  # noqa: E402
from clinical_risk_agent.rag.corpus import source_rejection_reasons  # noqa: E402
from clinical_risk_agent.rag.index import BM25Index, CorpusSnapshot  # noqa: E402
from clinical_risk_agent.rag.retrieval import (  # noqa: E402
    DenseHit,
    HybridRetriever,
    _RankedCandidate,
)
from clinical_risk_agent.rag.benchmark import (  # noqa: E402
    RelevanceCase,
    compare_strategies,
)

TODAY = date(2026, 9, 24)


def synthetic_source(number: int, abstract: str, **overrides: object) -> ScientificSource:
    values = dict(
        source_id=f"synthetic-source-{number}",
        title=f"Synthetic study {number}",
        authors=("Fixture Author",),
        publication="Synthetic Journal Fixture",
        published_on=date(2024, 4, 1),
        doi=f"10.5555/synthetic.fixture.{number}",
        pmid=None,
        source_type="journal_article",
        study_design="observational_study",
        peer_reviewed=True,
        pubmed_indexed=False,
        authority_approved=False,
        quality_passed=True,
        quality_rubric_version="fixture-rubric-v1",
        retraction_state="current",
        retraction_checked_on=TODAY,
        abstract=abstract,
        quality_score=0.8,
    )
    values.update(overrides)
    return ScientificSource(**values)


class FakeDense:
    def __init__(self, hits: tuple[DenseHit, ...] = (), fails: bool = False) -> None:
        self.hits = hits
        self.fails = fails

    def search(self, query: str, *, limit: int) -> tuple[DenseHit, ...]:
        if self.fails:
            raise RuntimeError("fixture dense outage")
        return self.hits[:limit]


class FakeReranker:
    def score(self, query: str, passage: object) -> float:
        return 1.0 if "bullying" in passage.exact_text.lower() else 0.1


class RAGCoreTests(unittest.TestCase):
    def test_relevance_first_is_default_and_legacy_order_can_be_reproduced(self) -> None:
        sources = (
            synthetic_source(1, "Older direct evidence.", published_on=date(2021, 1, 1)),
            synthetic_source(2, "Newer weak evidence.", published_on=date(2025, 1, 1)),
        )
        snapshot = CorpusSnapshot.build(sources, strategy="hierarchical", today=TODAY)
        lexical = BM25Index(snapshot)
        by_source = {item.source_id: item for item in snapshot.sources}
        candidates = tuple(_RankedCandidate(
            passage, by_source[passage.source_id],
            0.9 if passage.source_id == "synthetic-source-1" else 0.1,
            None, None, None,
        ) for passage in snapshot.passages)
        query = RetrievalQuery("direct evidence")
        old = HybridRetriever(snapshot, lexical, FakeDense(), relevance_first=False)._select(
            candidates, query, TODAY)
        new = HybridRetriever(snapshot, lexical, FakeDense())._select(
            candidates, query, TODAY)
        self.assertEqual(old[0].source.source_id, "synthetic-source-2")
        self.assertEqual(new[0].source.source_id, "synthetic-source-1")

    def test_eligibility_rejects_stale_retraction_and_unlicensed_full_text(self) -> None:
        source = synthetic_source(1, "Bullying evidence fixture.")
        self.assertEqual(source_rejection_reasons(source, today=TODAY), ())
        stale = replace(source, retraction_checked_on=TODAY - timedelta(days=15))
        self.assertIn("retraction_check_stale", source_rejection_reasons(stale, today=TODAY))
        unlicensed = replace(
            source, full_text_sections=(SourceSection("results", "Synthetic results.", "sec-1"),)
        )
        self.assertIn("full_text_license_unverified",
                      source_rejection_reasons(unlicensed, today=TODAY))
        self.assertIn("isolation_metadata_invalid", source_rejection_reasons(
            replace(source, contains_patient_data=True), today=TODAY))
        self.assertIn("retracted_or_unverified", source_rejection_reasons(
            replace(source, retraction_state="retracted"), today=TODAY))

    def test_document_and_hierarchical_chunks_keep_source_and_section_identity(self) -> None:
        abstract = " ".join(f"Sentence {i} describes bullying evidence." for i in range(100))
        source = synthetic_source(1, abstract)
        whole = chunk_source(source, strategy="document")
        children = chunk_source(source, strategy="hierarchical")
        self.assertEqual(len(whole), 1)
        self.assertGreater(len(children), 1)
        self.assertEqual({item.parent_id for item in children}, {whole[0].parent_id})
        self.assertTrue(all(item.source_id == source.source_id for item in children))
        self.assertTrue(all(item.section == "abstract" for item in children))
        self.assertNotEqual(children[0].chunk_id, whole[0].chunk_id)

    def test_hybrid_and_fallback_return_only_current_citable_sources(self) -> None:
        sources = (
            synthetic_source(1, "Bullying and mental health association in a synthetic fixture."),
            synthetic_source(2, "Unrelated synthetic chemistry record."),
            synthetic_source(3, "Bullying fixture with stale retraction check.",
                             retraction_checked_on=TODAY - timedelta(days=15)),
        )
        snapshot = CorpusSnapshot.build(sources, strategy="hierarchical", today=TODAY)
        self.assertEqual(len(snapshot.sources), 2)
        lexical = BM25Index(snapshot)
        hit = DenseHit(snapshot.passages[0].chunk_id, 0.91)
        query = RetrievalQuery("bullying mental health")
        primary = HybridRetriever(snapshot, lexical, FakeDense((hit,)),
                                  reranker=FakeReranker()).retrieve(query, today=TODAY)
        self.assertEqual(primary.status, EvidenceStatus.SUFFICIENT)
        self.assertEqual(primary.retrieval_mode, RetrievalMode.PRIMARY_HYBRID)
        self.assertEqual(len(primary.items), 1)
        self.assertEqual(primary.items[0].source_id, "synthetic-source-1")
        self.assertEqual(primary.items[0].exact_matched_text,
                         primary.displays[0].exact_matched_text)
        self.assertEqual(primary.items[0].citation_id, primary.displays[0].citation_id)
        fallback = HybridRetriever(snapshot, lexical, FakeDense(fails=True)).retrieve(
            query, today=TODAY)
        self.assertEqual(fallback.retrieval_mode, RetrievalMode.KEYWORD_FALLBACK)
        self.assertEqual(fallback.primary_status, AttemptStatus.UNAVAILABLE)
        self.assertEqual(fallback.items[0].source_id, "synthetic-source-1")

    def test_no_evidence_and_dual_outage_are_distinct(self) -> None:
        snapshot = CorpusSnapshot.build(
            (synthetic_source(1, "Synthetic bullying evidence."),),
            strategy="document", today=TODAY,
        )
        index = BM25Index(snapshot)
        query = RetrievalQuery("unmatchedterm")
        no_evidence = HybridRetriever(snapshot, index, FakeDense()).retrieve(query, today=TODAY)
        self.assertEqual(no_evidence.status, EvidenceStatus.NO_ELIGIBLE_EVIDENCE)
        outage = HybridRetriever(snapshot, index, FakeDense(fails=True)).retrieve(
            query, today=TODAY)
        self.assertEqual(outage.status, EvidenceStatus.RETRIEVAL_UNAVAILABLE)

    def test_explicit_opposing_stance_survives_source_cap(self) -> None:
        sources = tuple(
            synthetic_source(number, "Synthetic bullying evidence.",
                             stance="refutes" if number == 4 else "supports",
                             stance_claim_id="fixture-claim")
            for number in range(1, 5)
        )
        snapshot = CorpusSnapshot.build(sources, strategy="document", today=TODAY)
        dense = FakeDense(tuple(DenseHit(passage.chunk_id, 0.95)
                                for passage in snapshot.passages))
        result = HybridRetriever(snapshot, BM25Index(snapshot), dense).retrieve(
            RetrievalQuery("bullying evidence", source_cap=3,
                           claim_id="fixture-claim"), today=TODAY
        )
        self.assertEqual(result.status, EvidenceStatus.CONFLICTING_EVIDENCE)
        self.assertEqual({item.stance for item in result.items}, {"supports", "refutes"})
        self.assertEqual(len(result.items), 3)
        unscoped = HybridRetriever(snapshot, BM25Index(snapshot), dense).retrieve(
            RetrievalQuery("bullying evidence", source_cap=3), today=TODAY
        )
        self.assertEqual(unscoped.status, EvidenceStatus.SUFFICIENT)
        self.assertEqual({item.stance for item in unscoped.items}, {None})

    def test_document_and_hierarchical_benchmark_use_same_cases(self) -> None:
        sources = (
            synthetic_source(1, "Synthetic bullying research passage."),
            synthetic_source(2, "Synthetic attention research passage."),
        )
        retrievers = {}
        for strategy in ("document", "hierarchical"):
            snapshot = CorpusSnapshot.build(sources, strategy=strategy, today=TODAY)
            retrievers[strategy] = HybridRetriever(
                snapshot, BM25Index(snapshot), FakeDense(
                    (DenseHit(snapshot.passages[0].chunk_id, 0.95),)
                ),
            )
        cases = (
            RelevanceCase("synthetic-case-1", "bullying research",
                          frozenset({"synthetic-source-1"})),
            RelevanceCase("synthetic-case-2", "unmatchedterm", frozenset()),
        )
        metrics = compare_strategies(retrievers, cases, today=TODAY)
        self.assertEqual({item.strategy for item in metrics}, {"document", "hierarchical"})
        self.assertTrue(all(item.cases == 2 for item in metrics))
        self.assertTrue(all(0 <= item.ndcg_at_10 <= 1 for item in metrics))


if __name__ == "__main__":
    unittest.main()
