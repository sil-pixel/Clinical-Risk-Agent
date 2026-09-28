"""Validated, read-only runtime over the pinned local research corpus."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any

from clinical_risk_agent.contracts import EvidenceStatus, RetrievalQuery

from .answering import BoundedResearchAnswerer
from .chunking import Passage
from .corpus import ScientificSource, SourceSection
from .index import BM25Index, CorpusSnapshot
from .medcpt import MedCPTEncoder
from .qdrant_index import QdrantScientificIndex
from .retrieval import HybridRetriever
from .support import CuratedClaimSupport, SupportAssertion


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _source(raw: dict[str, Any]) -> ScientificSource:
    item = dict(raw)
    item["authors"] = tuple(item["authors"])
    item["published_on"] = date.fromisoformat(item["published_on"])
    item["retraction_checked_on"] = date.fromisoformat(item["retraction_checked_on"])
    item["full_text_sections"] = tuple(
        SourceSection(**section) for section in item["full_text_sections"]
    )
    return ScientificSource(**item)


def _snapshot(raw: dict[str, Any], strategy: str) -> CorpusSnapshot:
    return CorpusSnapshot(
        version=raw["corpus_version"], strategy=strategy,
        sources=tuple(_source(item) for item in raw["sources"]),
        passages=tuple(Passage(**item) for item in raw["passages"]),
    )


class ResearchRuntime:
    """One immutable corpus/model view shared by MCP and the HTTP backend."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        corpus_path = self.root / "data/indexes/rag_corpus_manifest.json"
        catalog_path = self.root / "agent_docs/RAG_21_SOURCE_CLAIM_SUPPORT_CATALOG.json"
        pin_path = self.root / "agent_docs/RAG_MEDCPT_ENCODER_PIN.json"
        self.corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        pin = json.loads(pin_path.read_text(encoding="utf-8"))
        if catalog["corpus_manifest_sha256"] != sha256_file(corpus_path):
            raise ValueError("Support catalog and active corpus differ")
        if self.corpus["query_model_sha256"] != pin["models"]["query"]["model_safetensors_sha256"]:
            raise ValueError("Query encoder and corpus differ")
        expected_article_sha = pin["models"]["article"]["model_safetensors_sha256"]
        if self.corpus["article_model_sha256"] != expected_article_sha:
            raise ValueError("Article encoder and corpus differ")

        today = date.today()
        self.snapshots = {
            strategy: _snapshot(self.corpus["snapshots"][strategy], strategy)
            for strategy in ("document", "hierarchical")
        }
        for snapshot in self.snapshots.values():
            if snapshot.active_passages(today=today) != snapshot.passages:
                raise ValueError("Research corpus contains stale or ineligible sources")
        hierarchical = self.snapshots["hierarchical"]
        sources = {source.pmid: source for source in hierarchical.sources}
        if set(sources) != set(self.corpus["source_pmids"]):
            raise ValueError("Source identities differ from corpus manifest")

        assertions = tuple(SupportAssertion(**row) for row in catalog["assertions"])
        support = CuratedClaimSupport(
            hierarchical, assertions,
            expected_version=self.corpus["snapshots"]["hierarchical"]["corpus_version"],
        )
        encoder = MedCPTEncoder.from_local(
            self.root / pin["models"]["query"]["local_dir"],
            self.root / pin["models"]["article"]["local_dir"],
            query_sha256=self.corpus["query_model_sha256"],
            article_sha256=self.corpus["article_model_sha256"],
        )
        from qdrant_client import QdrantClient

        self._client = QdrantClient(path=str(self.root / "data/indexes/qdrant"))
        try:
            collection = self.corpus["collections"]["hierarchical"]
            collection_exists = self._client.collection_exists(collection)
            point_count = (self._client.count(collection, exact=True).count
                           if collection_exists else -1)
            if not collection_exists or point_count != len(hierarchical.passages):
                raise ValueError("Qdrant collection differs from pinned snapshot")
            lexical = BM25Index(hierarchical)
            qdrant = QdrantScientificIndex(self._client, collection, encoder, lexical)
            retriever = HybridRetriever(
                hierarchical, lexical, qdrant, primary_sparse_searcher=qdrant,
                dense_min_cosine=0.85, relevance_first=True, support_checker=support,
            )
            self._general_retriever = HybridRetriever(
                hierarchical, lexical, qdrant, primary_sparse_searcher=qdrant,
                dense_min_cosine=0.85, relevance_first=True,
            )
            self.answerer = BoundedResearchAnswerer(
                claim_ids={item.claim_id for item in assertions},
                retrieve_supported=lambda question, claim_id: retriever.retrieve(
                    RetrievalQuery(question, claim_id=claim_id), today=date.today(),
                ),
                # Public HTTP uses IDs only; this path is retained for MCP/local inspection.
                exploratory_search=lambda _question, _limit: {
                    "match_status": "no_matches", "matches": [],
                },
                bounded_use=lambda pmid: self.corpus["source_review"][pmid]["bounded_use"],
            )
        except Exception:
            self._client.close()
            raise

    def search_general(self, question: str) -> dict[str, Any]:
        """Retrieve relevant appraised passages without claiming curated entailment."""
        result = self._general_retriever.retrieve(
            RetrievalQuery(question, source_cap=3), today=date.today(),
        )
        if result.status is EvidenceStatus.RETRIEVAL_UNAVAILABLE:
            return {
                "status": "retrieval_unavailable",
                "answer": "Research retrieval is unavailable right now.",
                "limitation": "No evidence-based answer was produced.",
                "citations": [],
                "corpus_version": result.corpus_version,
            }
        if result.status is EvidenceStatus.NO_ELIGIBLE_EVIDENCE or not result.items:
            return {
                "status": "no_adequate_evidence",
                "answer": (
                    "I could not find sufficiently relevant evidence in the current "
                    "appraised corpus for that question."
                ),
                "limitation": "The corpus is limited; this is not evidence that no research exists.",
                "citations": [],
                "corpus_version": result.corpus_version,
            }
        displays = {item.citation_id: item for item in result.displays}
        citations = []
        for item in result.items:
            display = displays[item.citation_id]
            citations.append({
                "citation_id": item.citation_id,
                "pmid": item.pmid,
                "chunk_id": item.chunk_id,
                "title": display.title,
                "exact_matched_text": display.exact_matched_text,
                "bounded_use": self.corpus["source_review"][item.pmid]["bounded_use"],
            })
        return {
            "status": "general_evidence_available",
            "answer": None,
            "limitation": (
                "Research-only summary of the current appraised corpus; not a diagnosis, "
                "individual risk estimate, or medical advice."
            ),
            "citations": citations,
            "corpus_version": result.corpus_version,
        }

    @property
    def corpus_version(self) -> str:
        return self.corpus["snapshots"]["hierarchical"]["corpus_version"]

    def close(self) -> None:
        self._client.close()
