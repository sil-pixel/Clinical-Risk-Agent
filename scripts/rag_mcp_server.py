"""Local read-only MCP playground for the pinned public research corpus."""

from __future__ import annotations

import atexit
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mcp.server import MCPServer  # noqa: E402
from mcp.types import ToolAnnotations  # noqa: E402

from clinical_risk_agent.contracts import RetrievalQuery  # noqa: E402
from clinical_risk_agent.rag.index import BM25Index  # noqa: E402
from clinical_risk_agent.rag.medcpt import MedCPTEncoder  # noqa: E402
from clinical_risk_agent.rag.qdrant_index import QdrantScientificIndex  # noqa: E402
from clinical_risk_agent.rag.retrieval import HybridRetriever  # noqa: E402
from clinical_risk_agent.rag.support import CuratedClaimSupport, SupportAssertion  # noqa: E402

from rag_benchmark import _sha256, _snapshot  # noqa: E402


class ResearchCorpus:
    """One process-local, immutable view; no tool opens files supplied by callers."""

    def __init__(self) -> None:
        corpus_path = ROOT / "data/indexes/rag_corpus_manifest.json"
        catalog_path = ROOT / "agent_docs/RAG_21_SOURCE_CLAIM_SUPPORT_CATALOG.json"
        pin_path = ROOT / "agent_docs/RAG_MEDCPT_ENCODER_PIN.json"
        self.corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
        self.catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        pin = json.loads(pin_path.read_text(encoding="utf-8"))
        if self.catalog["corpus_manifest_sha256"] != _sha256(corpus_path):
            raise ValueError("Support catalog and active corpus differ")
        if self.corpus["query_model_sha256"] != pin["models"]["query"]["model_safetensors_sha256"]:
            raise ValueError("Query encoder and corpus differ")
        if self.corpus["article_model_sha256"] != pin["models"]["article"]["model_safetensors_sha256"]:
            raise ValueError("Article encoder and corpus differ")
        today = date.today()
        self.snapshots = {
            strategy: _snapshot(self.corpus["snapshots"][strategy], strategy)
            for strategy in ("document", "hierarchical")
        }
        for snapshot in self.snapshots.values():
            if snapshot.active_passages(today=today) != snapshot.passages:
                raise ValueError("Research corpus contains stale or ineligible sources")
        self.sources = {
            source.pmid: source for source in self.snapshots["hierarchical"].sources
        }
        if set(self.sources) != set(self.corpus["source_pmids"]):
            raise ValueError("Source identities differ from corpus manifest")
        hierarchical = self.snapshots["hierarchical"]
        self.passages = {item.chunk_id: item for item in hierarchical.passages}
        self.assertions = tuple(SupportAssertion(**row) for row in self.catalog["assertions"])
        self.support = CuratedClaimSupport(
            hierarchical, self.assertions,
            expected_version=self.corpus["snapshots"]["hierarchical"]["corpus_version"],
        )
        encoder = MedCPTEncoder.from_local(
            ROOT / pin["models"]["query"]["local_dir"],
            ROOT / pin["models"]["article"]["local_dir"],
            query_sha256=self.corpus["query_model_sha256"],
            article_sha256=self.corpus["article_model_sha256"],
        )
        from qdrant_client import QdrantClient

        self.client = QdrantClient(path=str(ROOT / "data/indexes/qdrant"))
        try:
            self.retrievers = {}
            for strategy, snapshot in self.snapshots.items():
                collection = self.corpus["collections"][strategy]
                if (not self.client.collection_exists(collection)
                        or self.client.count(collection, exact=True).count != len(snapshot.passages)):
                    raise ValueError("Qdrant collection differs from pinned snapshot")
                lexical = BM25Index(snapshot)
                qdrant = QdrantScientificIndex(self.client, collection, encoder, lexical)
                self.retrievers[strategy] = HybridRetriever(
                    snapshot, lexical, qdrant, primary_sparse_searcher=qdrant,
                    dense_min_cosine=0.0, relevance_first=True,
                )
        except Exception:
            self.client.close()
            raise

    def close(self) -> None:
        self.client.close()

    @staticmethod
    def _question(question: str) -> str:
        question = question.strip()
        if not 3 <= len(question) <= 500:
            raise ValueError("Question must be 3 to 500 characters")
        return question

    @staticmethod
    def _limit(limit: int) -> int:
        if not 1 <= limit <= 5:
            raise ValueError("Limit must be 1 to 5")
        return limit

    def _matches(self, strategy: str, question: str, limit: int) -> dict:
        question = self._question(question)
        limit = self._limit(limit)
        result = self.retrievers[strategy].retrieve(
            RetrievalQuery(question), today=date.today())
        records = []
        for item in result.items[:limit]:
            review = self.corpus["source_review"][item.pmid]
            records.append({
                "citation_id": item.citation_id, "pmid": item.pmid,
                "title": item.title, "chunk_id": item.chunk_id,
                "exact_matched_text": item.exact_matched_text,
                "bounded_use": review["bounded_use"],
                "study_design_tier": item.evidence_tier,
            })
        return {
            "strategy": strategy,
            "research_only": True,
            "support_status": "not_evaluated_for_the_question",
            "match_status": ("matches_found" if result.items else
                             "retrieval_unavailable" if result.status.value == "retrieval_unavailable"
                             else "no_matches"),
            "retrieval_mode": result.retrieval_mode.value if result.retrieval_mode else None,
            "matches": records,
            "corpus_version": result.corpus_version,
        }

    def search_evidence(self, question: str, limit: int = 5) -> dict:
        return self._matches("hierarchical", question, limit)

    def compare_retrieval(self, question: str, limit: int = 5) -> dict:
        question = self._question(question)
        limit = self._limit(limit)
        return {
            "research_only": True,
            "comparison": "document_vs_hierarchical_unjudged_live_query",
            "document": self._matches("document", question, limit),
            "hierarchical": self._matches("hierarchical", question, limit),
        }

    def get_paper(self, pmid: str) -> dict:
        if not re.fullmatch(r"[1-9]\d{0,9}", pmid):
            raise ValueError("PMID must be a positive integer string")
        source = self.sources.get(pmid)
        if source is None:
            return {"found": False, "pmid": pmid, "research_only": True}
        review = self.corpus["source_review"][pmid]
        return {
            "found": True, "research_only": True, "pmid": pmid,
            "title": source.title, "authors": list(source.authors),
            "publication": source.publication,
            "published_on": source.published_on.isoformat(),
            "doi": source.doi, "study_design": source.study_design,
            "abstract": source.abstract,
            "bounded_use": review["bounded_use"],
            "release_status": review["release_status"],
            "passage_ids": [item.chunk_id for item in self.snapshots["hierarchical"].passages
                            if item.source_id == source.source_id],
        }

    def list_curated_claims(self) -> dict:
        return {
            "research_only": True,
            "catalog_status": self.catalog["status"],
            "claim_ids": sorted({item.claim_id for item in self.assertions}),
            "note": "These are bounded curated assertions, not a classifier for arbitrary questions.",
        }

    def get_curated_claim(self, claim_id: str) -> dict:
        if not re.fullmatch(r"[a-z][a-z0-9_]{2,100}", claim_id):
            raise ValueError("Invalid claim ID")
        matches = []
        for assertion in self.assertions:
            if assertion.claim_id != claim_id:
                continue
            pmid = assertion.source_id.removeprefix("pmid:")
            passage = self.passages[assertion.chunk_id]
            matches.append({
                "pmid": pmid, "title": self.sources[pmid].title,
                "chunk_id": passage.chunk_id, "exact_matched_text": passage.exact_text,
                "anchor": assertion.anchor,
                "bounded_use": self.corpus["source_review"][pmid]["bounded_use"],
            })
        return {
            "research_only": True, "claim_id": claim_id,
            "catalog_status": self.catalog["status"],
            "curated_passages": matches,
            "support_status": "curated_assertion_available" if matches else "no_curated_assertion",
        }


_corpus: ResearchCorpus | None = None


def corpus() -> ResearchCorpus:
    global _corpus
    if _corpus is None:
        _corpus = ResearchCorpus()
        atexit.register(_corpus.close)
    return _corpus


mcp = MCPServer(
    "Clinical Risk Research Corpus",
    instructions=("Read-only local PubMed-abstract research playground. Retrieval matches are "
                  "unverified for arbitrary questions; never describe them as claim support. "
                  "Use only public or synthetic questions, never patient data."),
    version="0.1.0",
)
READ_ONLY = ToolAnnotations(read_only_hint=True, open_world_hint=False)


@mcp.tool(annotations=READ_ONLY, structured_output=True)
async def search_evidence(question: str, limit: int = 5) -> dict[str, Any]:
    """Find hierarchical passage matches; relevance and claim support are unverified."""
    return corpus().search_evidence(question, limit)


@mcp.tool(annotations=READ_ONLY, structured_output=True)
async def get_paper(pmid: str) -> dict[str, Any]:
    """Read an indexed PubMed paper's exact abstract, citation metadata and bounded use."""
    return corpus().get_paper(pmid)


@mcp.tool(annotations=READ_ONLY, structured_output=True)
async def compare_retrieval(question: str, limit: int = 5) -> dict[str, Any]:
    """Compare document and hierarchical matches for one exploratory question."""
    return corpus().compare_retrieval(question, limit)


@mcp.tool(annotations=READ_ONLY, structured_output=True)
async def list_curated_claims() -> dict[str, Any]:
    """List the five bounded research assertions available in the local catalog."""
    return corpus().list_curated_claims()


@mcp.tool(annotations=READ_ONLY, structured_output=True)
async def get_curated_claim(claim_id: str) -> dict[str, Any]:
    """Read exact anchored passages for a catalog claim ID, if available."""
    return corpus().get_curated_claim(claim_id)


if __name__ == "__main__":
    mcp.run(transport="stdio")
