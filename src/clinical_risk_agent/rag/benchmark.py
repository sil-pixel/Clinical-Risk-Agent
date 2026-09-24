"""Same-case document versus hierarchical retrieval measurements."""

from __future__ import annotations

import math
import statistics
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Protocol

from clinical_risk_agent.contracts import EvidenceResult, EvidenceStatus, RetrievalQuery


class Retriever(Protocol):
    def retrieve(self, query: RetrievalQuery, *, today: date) -> EvidenceResult: ...
    def rank_source_ids_for_evaluation(
        self, query: RetrievalQuery, *, today: date, limit: int = 20
    ) -> tuple[str, ...]: ...


@dataclass(frozen=True, slots=True)
class RelevanceCase:
    case_id: str
    query: str
    relevant_source_ids: frozenset[str]
    relevant_chunk_ids: frozenset[str] = frozenset()


@dataclass(frozen=True, slots=True)
class StrategyMetrics:
    strategy: str
    cases: int
    recall_at_5: float
    recall_at_10: float
    recall_at_20: float
    precision_at_5: float
    mrr_at_10: float
    ndcg_at_10: float
    no_evidence_precision: float | None
    no_evidence_recall: float | None
    median_latency_ms: float
    max_latency_ms: float


def _dcg(ids: Sequence[str], relevant: frozenset[str], cutoff: int) -> float:
    return sum(1 / math.log2(rank + 2) for rank, source_id in enumerate(ids[:cutoff])
               if source_id in relevant)


def evaluate_strategy(
    name: str,
    retriever: Retriever,
    cases: Sequence[RelevanceCase],
    *,
    today: date,
) -> StrategyMetrics:
    if not cases or len({case.case_id for case in cases}) != len(cases):
        raise ValueError("Benchmark needs unique, nonempty frozen cases")
    recall_5: list[float] = []
    recall_10: list[float] = []
    recall_20: list[float] = []
    precision_5: list[float] = []
    mrr_10: list[float] = []
    ndcg_10: list[float] = []
    latency_ms: list[float] = []
    no_evidence_true_positive = 0
    no_evidence_predicted = 0
    no_evidence_actual = 0
    for case in cases:
        started = time.perf_counter()
        result = retriever.retrieve(RetrievalQuery(case.query), today=today)
        latency_ms.append((time.perf_counter() - started) * 1000)
        ids = list(retriever.rank_source_ids_for_evaluation(
            RetrievalQuery(case.query), today=today, limit=20))
        relevant = case.relevant_source_ids
        for cutoff, target in ((5, recall_5), (10, recall_10), (20, recall_20)):
            target.append(len(set(ids[:cutoff]) & relevant) / len(relevant) if relevant else 1.0)
        precision_5.append(len(set(ids[:5]) & relevant) / 5)
        first = next((rank for rank, source_id in enumerate(ids[:10], start=1)
                      if source_id in relevant), None)
        mrr_10.append(1 / first if first else 0.0)
        ideal = sum(1 / math.log2(rank + 2) for rank in range(min(10, len(relevant))))
        ndcg_10.append(_dcg(ids, relevant, 10) / ideal if ideal else 1.0)
        actual_empty = not relevant
        predicted_empty = result.status is EvidenceStatus.NO_ELIGIBLE_EVIDENCE
        no_evidence_actual += actual_empty
        no_evidence_predicted += predicted_empty
        no_evidence_true_positive += actual_empty and predicted_empty
    return StrategyMetrics(
        strategy=name, cases=len(cases),
        recall_at_5=statistics.mean(recall_5),
        recall_at_10=statistics.mean(recall_10),
        recall_at_20=statistics.mean(recall_20),
        precision_at_5=statistics.mean(precision_5),
        mrr_at_10=statistics.mean(mrr_10),
        ndcg_at_10=statistics.mean(ndcg_10),
        no_evidence_precision=(no_evidence_true_positive / no_evidence_predicted
                               if no_evidence_predicted else None),
        no_evidence_recall=(no_evidence_true_positive / no_evidence_actual
                            if no_evidence_actual else None),
        median_latency_ms=statistics.median(latency_ms),
        max_latency_ms=max(latency_ms),
    )


def compare_strategies(
    retrievers: Mapping[str, Retriever],
    cases: Sequence[RelevanceCase],
    *,
    today: date,
) -> tuple[StrategyMetrics, StrategyMetrics]:
    if set(retrievers) != {"document", "hierarchical"}:
        raise ValueError("Both approved chunking strategies are required")
    return (
        evaluate_strategy("document", retrievers["document"], cases, today=today),
        evaluate_strategy("hierarchical", retrievers["hierarchical"], cases, today=today),
    )
