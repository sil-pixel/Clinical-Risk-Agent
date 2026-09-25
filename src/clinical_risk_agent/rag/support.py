"""Conservative, corpus-bound claim support assertions for research retrieval."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from clinical_risk_agent.contracts import RetrievalQuery

from .chunking import Passage
from .corpus import ScientificSource
from .index import CorpusSnapshot


@dataclass(frozen=True, slots=True)
class SupportAssertion:
    claim_id: str
    source_id: str
    chunk_id: str
    anchor: str


class CuratedClaimSupport:
    """Allow only an explicit claim/source/passage/anchor match.

    Assertion IDs represent bounded association claims, not generic topic tags.
    Unknown claims and unannotated passages fail closed. The catalog is tied to
    a snapshot version so it cannot silently authorize a rebuilt corpus.
    """

    def __init__(self, snapshot: CorpusSnapshot, assertions: Sequence[SupportAssertion],
                 *, expected_version: str) -> None:
        if snapshot.version != expected_version:
            raise ValueError("Support assertions target a different corpus version")
        passages = {item.chunk_id: item for item in snapshot.passages}
        sources = {item.source_id for item in snapshot.sources}
        keys: set[tuple[str, str, str]] = set()
        for item in assertions:
            key = (item.claim_id, item.source_id, item.chunk_id)
            if not item.claim_id.strip() or not item.anchor.strip() or key in keys:
                raise ValueError("Invalid or duplicate support assertion")
            if item.source_id not in sources or item.chunk_id not in passages:
                raise ValueError("Support assertion refers to absent corpus material")
            passage = passages[item.chunk_id]
            if passage.source_id != item.source_id or item.anchor not in passage.exact_text:
                raise ValueError("Support anchor is not in the exact cited passage")
            keys.add(key)
        self._assertions = frozenset(keys)

    def supports(self, query: RetrievalQuery, source: ScientificSource,
                 passage: Passage) -> bool:
        return (query.claim_id, source.source_id, passage.chunk_id) in self._assertions
