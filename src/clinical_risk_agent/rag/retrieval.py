"""Volatile hybrid retrieval over an eligible versioned scientific corpus."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Protocol

from clinical_risk_agent.contracts import (
    AttemptStatus,
    EvidenceDisplayRecord,
    EvidenceItem,
    EvidenceResult,
    EvidenceStatus,
    RetrievalMode,
    RetrievalQuery,
)

from .chunking import Passage
from .corpus import EVIDENCE_TIERS, ScientificSource, eligible_source
from .index import BM25Index, CorpusSnapshot, LexicalHit


@dataclass(frozen=True, slots=True)
class DenseHit:
    chunk_id: str
    cosine: float


class DenseSearcher(Protocol):
    def search(self, query: str, *, limit: int) -> Sequence[DenseHit]: ...


class SparseSearcher(Protocol):
    def sparse_search(self, query: str, *, limit: int) -> Sequence[LexicalHit]: ...


class CrossEncoder(Protocol):
    def score(self, query: str, passage: Passage) -> float: ...

    def score_many(self, query: str, passages: Sequence[Passage]) -> Sequence[float]: ...


class SupportChecker(Protocol):
    def supports(self, query: RetrievalQuery, source: ScientificSource,
                 passage: Passage) -> bool: ...


@dataclass(frozen=True, slots=True)
class _RankedCandidate:
    passage: Passage
    source: ScientificSource
    fused_score: float
    dense_cosine: float | None
    lexical_score: float | None
    rerank_score: float | None


class HybridRetriever:
    """Relevance-first dense+BM25 search with an independent BM25 outage path."""

    def __init__(
        self,
        snapshot: CorpusSnapshot,
        lexical_index: BM25Index,
        dense_searcher: DenseSearcher,
        *,
        primary_sparse_searcher: SparseSearcher | None = None,
        reranker: CrossEncoder | None = None,
        dense_min_cosine: float = 0.85,
        rerank_min_score: float | None = None,
        relevance_first: bool = True,
        support_checker: SupportChecker | None = None,
    ) -> None:
        if lexical_index.version != f"bm25-{snapshot.version}":
            raise ValueError("Lexical index and corpus versions differ")
        if not -1 <= dense_min_cosine <= 1:
            raise ValueError("Dense cosine threshold is invalid")
        self.snapshot = snapshot
        self.lexical_index = lexical_index
        self.dense_searcher = dense_searcher
        self.primary_sparse_searcher = primary_sparse_searcher
        self.reranker = reranker
        self.dense_min_cosine = dense_min_cosine
        self.rerank_min_score = rerank_min_score
        self.relevance_first = relevance_first
        self.support_checker = support_checker

    def retrieve(self, query: RetrievalQuery, *, today: date) -> EvidenceResult:
        active = self.snapshot.active_passages(today=today)
        passages = {item.chunk_id: item for item in active}
        sources = {item.source_id: item for item in self.snapshot.sources
                   if eligible_source(item, today=today)}
        if not passages:
            return self._result(
                query, EvidenceStatus.NO_ELIGIBLE_EVIDENCE, None,
                AttemptStatus.ZERO_MATCH, AttemptStatus.ZERO_MATCH, (),
            )
        dense_status = AttemptStatus.SUCCESS
        try:
            raw_dense = tuple(self.dense_searcher.search(query.text, limit=40))
            dense = tuple(
                item for item in raw_dense
                if item.chunk_id in passages and math.isfinite(item.cosine)
                and item.cosine > self.dense_min_cosine
            )[:40]
            if not dense:
                dense_status = AttemptStatus.ZERO_MATCH
        except Exception:
            # The backend owns safe error telemetry. Never log raw query or exception locals here.
            dense = ()
            dense_status = AttemptStatus.UNAVAILABLE

        if dense_status is not AttemptStatus.SUCCESS:
            return self._fallback(query, today, passages, sources, dense_status)

        try:
            if self.primary_sparse_searcher is None:
                lexical = self.lexical_index.search(
                    query.text, limit=40, allowed_chunk_ids=set(passages)
                )
            else:
                lexical = tuple(item for item in self.primary_sparse_searcher.sparse_search(
                    query.text, limit=40) if item.chunk_id in passages)
        except Exception:
            return self._fallback(query, today, passages, sources, AttemptStatus.UNAVAILABLE)
        candidates = self._fuse(dense, lexical, passages, sources)
        try:
            selected = self._select(self._supported(candidates, query), query, today)
        except Exception:
            return self._result(
                query, EvidenceStatus.RETRIEVAL_UNAVAILABLE, None,
                AttemptStatus.UNAVAILABLE, AttemptStatus.NOT_ATTEMPTED, (),
            )
        if selected:
            return self._result(
                query, self._evidence_status(selected, query), RetrievalMode.PRIMARY_HYBRID,
                AttemptStatus.SUCCESS, AttemptStatus.NOT_ATTEMPTED, selected,
            )
        return self._fallback(query, today, passages, sources, AttemptStatus.ZERO_MATCH)

    def _fallback(
        self,
        query: RetrievalQuery,
        today: date,
        passages: Mapping[str, Passage],
        sources: Mapping[str, ScientificSource],
        primary_status: AttemptStatus,
    ) -> EvidenceResult:
        try:
            lexical = self.lexical_index.search(
                query.text, limit=40, allowed_chunk_ids=set(passages)
            )
            candidates = tuple(
                _RankedCandidate(passages[hit.chunk_id], sources[passages[hit.chunk_id].source_id],
                                 hit.score, None, hit.score, None)
                for hit in lexical
            )
            selected = self._select(self._supported(candidates, query), query, today)
        except Exception:
            return self._result(
                query, EvidenceStatus.RETRIEVAL_UNAVAILABLE, None,
                primary_status, AttemptStatus.UNAVAILABLE, (),
            )
        if selected:
            return self._result(
                query, self._evidence_status(selected, query), RetrievalMode.KEYWORD_FALLBACK,
                primary_status, AttemptStatus.SUCCESS, selected,
            )
        # The independent fallback completed. Its zero supported matches are
        # a no-evidence result even if the primary backend was unavailable.
        return self._result(query, EvidenceStatus.NO_ELIGIBLE_EVIDENCE, None,
                            primary_status, AttemptStatus.ZERO_MATCH, ())

    def _supported(self, candidates: Sequence[_RankedCandidate],
                   query: RetrievalQuery) -> tuple[_RankedCandidate, ...]:
        if self.support_checker is None:
            return tuple(candidates)
        return tuple(item for item in candidates if self.support_checker.supports(
            query, item.source, item.passage))

    def _fuse(
        self,
        dense: Sequence[DenseHit],
        lexical: Sequence[LexicalHit],
        passages: Mapping[str, Passage],
        sources: Mapping[str, ScientificSource],
    ) -> tuple[_RankedCandidate, ...]:
        scores: dict[str, float] = {}
        for ranking in (dense, lexical):
            for rank, hit in enumerate(ranking, start=1):
                scores[hit.chunk_id] = scores.get(hit.chunk_id, 0.0) + 1 / (60 + rank)
        dense_by_id = {item.chunk_id: item.cosine for item in dense}
        lexical_by_id = {item.chunk_id: item.score for item in lexical}
        top_ids = sorted(scores, key=lambda item: (-scores[item], item))[:30]
        return tuple(
            _RankedCandidate(
                passages[chunk_id], sources[passages[chunk_id].source_id], scores[chunk_id],
                dense_by_id.get(chunk_id), lexical_by_id.get(chunk_id), None,
            ) for chunk_id in top_ids
        )

    def _select(
        self, candidates: Sequence[_RankedCandidate], query: RetrievalQuery, today: date,
        *, limit: int | None = None,
    ) -> tuple[_RankedCandidate, ...]:
        eligible = [item for item in candidates[:20]
                    if eligible_source(item.source, today=today)]
        if self.reranker is not None and hasattr(self.reranker, "score_many"):
            scores = self.reranker.score_many(query.text, [item.passage for item in eligible])
            if len(scores) != len(eligible):
                raise ValueError("Reranker returned the wrong score count")
        else:
            scores = [self.reranker.score(query.text, item.passage)
                      if self.reranker is not None else None for item in eligible]
        rescored: list[_RankedCandidate] = []
        for item, score in zip(eligible, scores, strict=True):
            if score is not None and not math.isfinite(score):
                continue
            if score is not None and self.rerank_min_score is not None and score < self.rerank_min_score:
                continue
            rescored.append(_RankedCandidate(
                item.passage, item.source, item.fused_score, item.dense_cosine,
                item.lexical_score, score,
            ))
        if self.relevance_first:
            rescored.sort(key=lambda item: (
                -(item.rerank_score if item.rerank_score is not None else item.fused_score),
                EVIDENCE_TIERS[item.source.study_design],
                -item.source.published_on.toordinal(),
                -item.source.quality_score,
                item.source.source_id,
            ))
        else:
            rescored.sort(key=lambda item: (
                EVIDENCE_TIERS[item.source.study_design],
                -item.source.published_on.toordinal(),
                -item.source.quality_score,
                -(item.rerank_score if item.rerank_score is not None else item.fused_score),
                item.source.source_id,
            ))
        selected: list[_RankedCandidate] = []
        seen_sources: set[str] = set()
        for item in rescored:
            if item.source.source_id in seen_sources:
                continue
            selected.append(item)
            seen_sources.add(item.source.source_id)
            if len(selected) == (limit or query.source_cap):
                break
        # Preserve an explicitly appraised opposing source when the source cap
        # would otherwise hide a known conflict. Never infer stance from text.
        stances = {item.source.stance for item in selected
                   if query.claim_id and item.source.stance_claim_id == query.claim_id}
        if limit is None and len(selected) >= 2 and len(stances & {"supports", "refutes"}) == 1:
            opposing = "refutes" if "supports" in stances else "supports"
            alternative = next((item for item in rescored
                                if item.source.stance == opposing
                                and item.source.stance_claim_id == query.claim_id
                                and item.source.source_id not in seen_sources), None)
            if alternative is not None:
                selected[-1] = alternative
        return tuple(selected)

    @staticmethod
    def _evidence_status(
        selected: Sequence[_RankedCandidate], query: RetrievalQuery
    ) -> EvidenceStatus:
        stances = {item.source.stance for item in selected
                   if query.claim_id and item.source.stance_claim_id == query.claim_id}
        return (EvidenceStatus.CONFLICTING_EVIDENCE
                if {"supports", "refutes"} <= stances else EvidenceStatus.SUFFICIENT)

    def rank_source_ids_for_evaluation(
        self, query: RetrievalQuery, *, today: date, limit: int = 20
    ) -> tuple[str, ...]:
        """Offline-only ranking before the generation source cap; never expose to UI."""
        if not 1 <= limit <= 20:
            raise ValueError("Evaluation rank limit must be in 1..20")
        passages = {item.chunk_id: item for item in self.snapshot.active_passages(today=today)}
        sources = {item.source_id: item for item in self.snapshot.sources
                   if eligible_source(item, today=today)}
        try:
            dense = tuple(
                item for item in self.dense_searcher.search(query.text, limit=40)
                if item.chunk_id in passages and math.isfinite(item.cosine)
                and item.cosine > self.dense_min_cosine
            )[:40]
        except Exception:
            dense = ()
        if self.primary_sparse_searcher is None:
            lexical = self.lexical_index.search(
                query.text, limit=40, allowed_chunk_ids=set(passages)
            )
        else:
            lexical = tuple(item for item in self.primary_sparse_searcher.sparse_search(
                query.text, limit=40) if item.chunk_id in passages)
        if dense:
            candidates = self._fuse(dense, lexical, passages, sources)
        else:
            candidates = tuple(
                _RankedCandidate(passages[hit.chunk_id], sources[passages[hit.chunk_id].source_id],
                                 hit.score, None, hit.score, None)
                for hit in lexical
            )
        return tuple(item.source.source_id for item in self._select(
            candidates, query, today, limit=limit))

    def _result(
        self,
        query: RetrievalQuery,
        status: EvidenceStatus,
        mode: RetrievalMode | None,
        primary: AttemptStatus,
        fallback: AttemptStatus,
        selected: Sequence[_RankedCandidate],
    ) -> EvidenceResult:
        items: list[EvidenceItem] = []
        displays: list[EvidenceDisplayRecord] = []
        for index, candidate in enumerate(selected, start=1):
            source, passage = candidate.source, candidate.passage
            citation_id = f"S{index}"
            tier = EVIDENCE_TIERS[source.study_design]
            items.append(EvidenceItem(
                citation_id=citation_id, source_id=source.source_id,
                chunk_id=passage.chunk_id, parent_id=passage.parent_id,
                exact_matched_text=passage.exact_text, title=source.title,
                authors=source.authors, publication=source.publication,
                published_on=source.published_on, doi=source.doi, pmid=source.pmid,
                section=passage.section, locator=passage.locator,
                source_type=source.source_type, evidence_tier=tier,
                peer_reviewed=source.peer_reviewed, pubmed_indexed=source.pubmed_indexed,
                issuing_authority=source.issuing_authority,
                quality_score=source.quality_score,
                quality_rubric_version=source.quality_rubric_version,
                retraction_state=source.retraction_state,
                retraction_checked_on=source.retraction_checked_on,
                retrieval_score=candidate.fused_score,
                rerank_score=candidate.rerank_score,
                lexical_score=candidate.lexical_score,
                dense_cosine=candidate.dense_cosine,
                stance=(source.stance if query.claim_id == source.stance_claim_id else None),
            ))
            displays.append(EvidenceDisplayRecord(
                citation_id=citation_id, source_id=source.source_id,
                exact_matched_text=passage.exact_text, title=source.title,
                authors=source.authors, publication=source.publication,
                published_on=source.published_on, doi=source.doi, pmid=source.pmid,
                evidence_tier=tier, quality_score=source.quality_score,
                quality_rubric_version=source.quality_rubric_version,
                retraction_state=source.retraction_state,
                retraction_checked_on=source.retraction_checked_on,
            ))
        return EvidenceResult(
            status=status, retrieval_mode=mode, primary_status=primary,
            fallback_status=fallback, items=tuple(items), displays=tuple(displays),
            corpus_version=self.snapshot.version,
            index_version=self.lexical_index.version,
            source_cap=query.source_cap,
        )
