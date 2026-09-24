"""Versioned Qdrant dense/sparse scientific index; no runtime user writes."""

from __future__ import annotations

import math
import re
import uuid
from collections.abc import Sequence
from datetime import date
from typing import Protocol

from .chunking import Passage
from .index import BM25Index, CorpusSnapshot, LexicalHit
from .retrieval import DenseHit


class PassageEncoder(Protocol):
    def embed_query(self, query: str) -> Sequence[float]: ...
    def embed_passages(self, passages: Sequence[Passage]) -> Sequence[Sequence[float]]: ...


class QdrantScientificIndex:
    def __init__(
        self,
        client: object,
        collection_name: str,
        encoder: PassageEncoder,
        lexical_index: BM25Index,
    ) -> None:
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,120}", collection_name):
            raise ValueError("Invalid scientific collection name")
        self.client = client
        self.collection_name = collection_name
        self.encoder = encoder
        self.lexical_index = lexical_index
        self.corpus_version = lexical_index.version.removeprefix("bm25-")

    def _filter(self) -> object:
        from qdrant_client import models

        return models.Filter(must=[
            models.FieldCondition(
                key="data_class", match=models.MatchValue(value="scientific_publication")
            ),
            models.FieldCondition(
                key="document_scope", match=models.MatchValue(value="general_mental_health")
            ),
            models.FieldCondition(
                key="contains_patient_data", match=models.MatchValue(value=False)
            ),
            models.FieldCondition(
                key="corpus_version", match=models.MatchValue(value=self.corpus_version)
            ),
        ])

    def build(self, snapshot: CorpusSnapshot, *, today: date) -> None:
        """Create a new immutable collection; never overwrite an existing version."""
        from qdrant_client import models

        if self.lexical_index.version != f"bm25-{snapshot.version}":
            raise ValueError("Lexical and corpus versions differ")
        if snapshot.active_passages(today=today) != snapshot.passages:
            raise ValueError("Corpus contains stale or ineligible source material")
        if not snapshot.passages:
            raise ValueError("Cannot index an empty corpus")
        if self.client.collection_exists(self.collection_name):
            raise ValueError("Collection version already exists")
        first_vector = list(self.encoder.embed_passages(snapshot.passages[:1])[0])
        if not first_vector or not all(math.isfinite(value) for value in first_vector):
            raise ValueError("Encoder returned an invalid vector")
        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config={"dense": models.VectorParams(
                size=len(first_vector), distance=models.Distance.COSINE
            )},
            sparse_vectors_config={"bm25": models.SparseVectorParams()},
        )
        for offset in range(0, len(snapshot.passages), 64):
            batch = snapshot.passages[offset:offset + 64]
            vectors = self.encoder.embed_passages(batch)
            if len(vectors) != len(batch):
                raise ValueError("Encoder returned the wrong vector count")
            points = []
            for passage, embedding in zip(batch, vectors, strict=True):
                embedding = list(embedding)
                if len(embedding) != len(first_vector) or not all(
                    math.isfinite(value) for value in embedding
                ):
                    raise ValueError("Encoder returned incompatible vectors")
                sparse_indices, sparse_values = self.lexical_index.sparse_document(
                    passage.chunk_id
                )
                points.append(models.PointStruct(
                    id=str(uuid.uuid5(uuid.NAMESPACE_URL, passage.chunk_id)),
                    vector={
                        "dense": embedding,
                        "bm25": models.SparseVector(
                            indices=sparse_indices, values=sparse_values
                        ),
                    },
                    payload={
                        "chunk_id": passage.chunk_id,
                        "source_id": passage.source_id,
                        "corpus_version": snapshot.version,
                        "data_class": "scientific_publication",
                        "document_scope": "general_mental_health",
                        "contains_patient_data": False,
                    },
                ))
            self.client.upsert(self.collection_name, wait=True, points=points)

    def search(self, query: str, *, limit: int) -> tuple[DenseHit, ...]:
        vector = list(self.encoder.embed_query(query))
        if not vector or not all(math.isfinite(value) for value in vector):
            raise ValueError("Query encoder returned an invalid vector")
        results = self.client.query_points(
            collection_name=self.collection_name,
            query=vector,
            using="dense",
            query_filter=self._filter(),
            limit=limit,
            with_payload=True,
        )
        return tuple(DenseHit(item.payload["chunk_id"], float(item.score))
                     for item in results.points if item.payload and "chunk_id" in item.payload)

    def sparse_search(self, query: str, *, limit: int) -> tuple[LexicalHit, ...]:
        from qdrant_client import models

        indices, values = self.lexical_index.sparse_query(query)
        if not indices:
            return ()
        results = self.client.query_points(
            collection_name=self.collection_name,
            query=models.SparseVector(indices=indices, values=values),
            using="bm25",
            query_filter=self._filter(),
            limit=limit,
            with_payload=True,
        )
        return tuple(LexicalHit(item.payload["chunk_id"], float(item.score))
                     for item in results.points if item.payload and "chunk_id" in item.payload)
