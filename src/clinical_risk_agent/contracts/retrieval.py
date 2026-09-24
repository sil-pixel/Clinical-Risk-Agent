"""Immutable scientific evidence boundary shared by retrieval and workflow code."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum


class EvidenceStatus(str, Enum):
    SUFFICIENT = "sufficient_evidence"
    NO_ELIGIBLE_EVIDENCE = "no_eligible_evidence"
    CONFLICTING_EVIDENCE = "conflicting_evidence"
    RETRIEVAL_UNAVAILABLE = "retrieval_unavailable"


class RetrievalMode(str, Enum):
    PRIMARY_HYBRID = "primary_hybrid"
    KEYWORD_FALLBACK = "keyword_fallback"


class AttemptStatus(str, Enum):
    SUCCESS = "success"
    ZERO_MATCH = "zero_match"
    UNAVAILABLE = "unavailable"
    NOT_ATTEMPTED = "not_attempted"


@dataclass(frozen=True, slots=True)
class RetrievalQuery:
    """Volatile query text; never serialize or log a runtime instance."""

    text: str
    source_cap: int = 5
    claim_id: str | None = None

    def __post_init__(self) -> None:
        if (not self.text.strip() or not 3 <= self.source_cap <= 5
                or (self.claim_id is not None and not self.claim_id.strip())):
            raise ValueError("Retrieval query or source cap is invalid")


@dataclass(frozen=True, slots=True)
class EvidenceItem:
    citation_id: str
    source_id: str
    chunk_id: str
    parent_id: str
    exact_matched_text: str
    title: str
    authors: tuple[str, ...]
    publication: str
    published_on: date
    doi: str | None
    pmid: str | None
    section: str
    locator: str
    source_type: str
    evidence_tier: int
    peer_reviewed: bool
    pubmed_indexed: bool
    issuing_authority: str | None
    quality_score: float
    quality_rubric_version: str
    retraction_state: str
    retraction_checked_on: date
    retrieval_score: float
    rerank_score: float | None
    lexical_score: float | None
    dense_cosine: float | None
    stance: str | None = None


@dataclass(frozen=True, slots=True)
class EvidenceDisplayRecord:
    citation_id: str
    source_id: str
    exact_matched_text: str
    title: str
    authors: tuple[str, ...]
    publication: str
    published_on: date
    doi: str | None
    pmid: str | None
    evidence_tier: int
    quality_score: float
    quality_rubric_version: str
    retraction_state: str
    retraction_checked_on: date


@dataclass(frozen=True, slots=True)
class EvidenceResult:
    status: EvidenceStatus
    retrieval_mode: RetrievalMode | None
    primary_status: AttemptStatus
    fallback_status: AttemptStatus
    items: tuple[EvidenceItem, ...]
    displays: tuple[EvidenceDisplayRecord, ...]
    corpus_version: str
    index_version: str
    source_cap: int
    limitation: str | None = None

    def __post_init__(self) -> None:
        ids = {item.citation_id for item in self.items}
        if len(ids) != len(self.items) or ids != {item.citation_id for item in self.displays}:
            raise ValueError("Evidence and display citation IDs must match uniquely")
        if len({item.source_id for item in self.items}) > self.source_cap:
            raise ValueError("Evidence exceeds the distinct-source cap")
