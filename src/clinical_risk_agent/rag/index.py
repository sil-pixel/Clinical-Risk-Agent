"""Versioned public-corpus snapshot and independent deterministic BM25 index."""

from __future__ import annotations

import hashlib
import math
from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date

from .chunking import Passage, approximate_tokens, chunk_source
from .corpus import ScientificSource, eligible_source


@dataclass(frozen=True, slots=True)
class CorpusSnapshot:
    version: str
    strategy: str
    sources: tuple[ScientificSource, ...]
    passages: tuple[Passage, ...]

    @classmethod
    def build(
        cls,
        sources: Iterable[ScientificSource],
        *,
        strategy: str,
        today: date,
        count_tokens: Callable[[str], int] = approximate_tokens,
    ) -> "CorpusSnapshot":
        admitted = tuple(sorted(
            (source for source in sources if eligible_source(source, today=today)),
            key=lambda source: source.source_id,
        ))
        if len({source.source_id for source in admitted}) != len(admitted):
            raise ValueError("Duplicate source IDs cannot enter a corpus snapshot")
        dois = [source.doi.lower() for source in admitted if source.doi]
        pmids = [source.pmid for source in admitted if source.pmid]
        if len(set(dois)) != len(dois) or len(set(pmids)) != len(pmids):
            raise ValueError("Duplicate DOI/PMID identities cannot enter a corpus snapshot")
        passages = tuple(passage for source in admitted
                         for passage in chunk_source(source, strategy=strategy,
                                                     count_tokens=count_tokens))
        digest = hashlib.sha256()
        digest.update(strategy.encode())
        for source in admitted:
            digest.update(repr(source).encode("utf-8"))
        for passage in passages:
            digest.update(repr(passage).encode("utf-8"))
        return cls(
            version=f"corpus-{digest.hexdigest()[:16]}",
            strategy=strategy,
            sources=admitted,
            passages=passages,
        )

    def active_passages(self, *, today: date) -> tuple[Passage, ...]:
        active_ids = {source.source_id for source in self.sources
                      if eligible_source(source, today=today)}
        return tuple(item for item in self.passages if item.source_id in active_ids)


def tokenize(text: str) -> tuple[str, ...]:
    from .chunking import WORD_TOKEN

    return tuple(match.group().lower() for match in WORD_TOKEN.finditer(text))


@dataclass(frozen=True, slots=True)
class LexicalHit:
    chunk_id: str
    score: float


class BM25Index:
    """Separate from the vector engine; may be rebuilt from a public snapshot."""

    def __init__(self, snapshot: CorpusSnapshot, *, k1: float = 1.2, b: float = 0.75) -> None:
        self.version = f"bm25-{snapshot.version}"
        self._passages = snapshot.passages
        self._k1 = k1
        self._b = b
        self._terms = tuple(Counter(tokenize(f"{item.title} {item.exact_text}"))
                            for item in self._passages)
        self._lengths = tuple(sum(terms.values()) for terms in self._terms)
        self._average_length = sum(self._lengths) / max(len(self._lengths), 1)
        self._document_frequency: Counter[str] = Counter()
        for terms in self._terms:
            self._document_frequency.update(terms.keys())
        self._term_ids = {
            term: index for index, term in enumerate(sorted(self._document_frequency))
        }

    def sparse_document(self, chunk_id: str) -> tuple[list[int], list[float]]:
        position = next((index for index, item in enumerate(self._passages)
                         if item.chunk_id == chunk_id), None)
        if position is None:
            raise KeyError("Chunk is absent from the lexical index")
        counts = self._terms[position]
        length = self._lengths[position]
        vector = []
        for term, frequency in counts.items():
            document_frequency = self._document_frequency[term]
            idf = math.log(1 + (len(self._terms) - document_frequency + 0.5)
                           / (document_frequency + 0.5))
            denominator = frequency + self._k1 * (
                1 - self._b + self._b * length / max(self._average_length, 1)
            )
            vector.append((self._term_ids[term],
                           idf * frequency * (self._k1 + 1) / denominator))
        vector.sort()
        return [index for index, _ in vector], [value for _, value in vector]

    def sparse_query(self, query: str) -> tuple[list[int], list[float]]:
        indices = sorted(self._term_ids[term] for term in set(tokenize(query))
                         if term in self._term_ids)
        return indices, [1.0] * len(indices)

    def search(
        self, query: str, *, limit: int = 40, allowed_chunk_ids: set[str] | None = None
    ) -> tuple[LexicalHit, ...]:
        if limit < 1:
            raise ValueError("Search limit must be positive")
        query_terms = set(tokenize(query))
        document_count = len(self._terms)
        hits: list[LexicalHit] = []
        for item, counts, length in zip(
            self._passages, self._terms, self._lengths, strict=True
        ):
            if allowed_chunk_ids is not None and item.chunk_id not in allowed_chunk_ids:
                continue
            score = 0.0
            for term in query_terms:
                frequency = counts.get(term, 0)
                if not frequency:
                    continue
                document_frequency = self._document_frequency[term]
                idf = math.log(1 + (document_count - document_frequency + 0.5)
                               / (document_frequency + 0.5))
                denominator = frequency + self._k1 * (
                    1 - self._b + self._b * length / max(self._average_length, 1)
                )
                score += idf * frequency * (self._k1 + 1) / denominator
            if score > 0:
                hits.append(LexicalHit(item.chunk_id, score))
        return tuple(sorted(hits, key=lambda hit: (-hit.score, hit.chunk_id))[:limit])
