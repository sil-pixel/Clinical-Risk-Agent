"""Local, synthetic Qdrant adapter test; no network or real publication content."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from datetime import date
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parents[2] / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from clinical_risk_agent.rag.index import BM25Index, CorpusSnapshot  # noqa: E402
from clinical_risk_agent.rag.qdrant_index import QdrantScientificIndex  # noqa: E402
from tests.unit.test_rag_core import synthetic_source  # noqa: E402

TODAY = date(2026, 9, 24)


class FakeEncoder:
    @staticmethod
    def _vector(text: str) -> list[float]:
        return [1.0, 0.0] if "bullying" in text.lower() else [0.0, 1.0]

    def embed_query(self, query: str) -> list[float]:
        return self._vector(query)

    def embed_passages(self, passages: object) -> list[list[float]]:
        return [self._vector(item.exact_text) for item in passages]


@unittest.skipUnless(importlib.util.find_spec("qdrant_client"), "qdrant-client unavailable")
class QdrantAdapterTests(unittest.TestCase):
    def test_dense_sparse_and_isolation_filter(self) -> None:
        from qdrant_client import QdrantClient

        snapshot = CorpusSnapshot.build((
            synthetic_source(1, "Synthetic bullying evidence about mental health."),
            synthetic_source(2, "Synthetic attention evidence."),
        ), strategy="hierarchical", today=TODAY)
        lexical = BM25Index(snapshot)
        client = QdrantClient(":memory:")
        index = QdrantScientificIndex(client, "scientific_fixture_v1", FakeEncoder(), lexical)
        index.build(snapshot, today=TODAY)
        dense = index.search("bullying", limit=5)
        sparse = index.sparse_search("bullying", limit=5)
        self.assertEqual(dense[0].chunk_id, snapshot.passages[0].chunk_id)
        self.assertEqual(sparse[0].chunk_id, snapshot.passages[0].chunk_id)
        records, _ = client.scroll("scientific_fixture_v1", with_payload=True, limit=5)
        self.assertTrue(all("exact_text" not in item.payload for item in records))
        self.assertTrue(all(item.payload["contains_patient_data"] is False for item in records))
        with self.assertRaises(ValueError):
            index.build(snapshot, today=TODAY)


if __name__ == "__main__":
    unittest.main()
