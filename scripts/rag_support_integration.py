"""Exercise curated claim support and recovery against the pinned local Qdrant corpus."""

from __future__ import annotations

import argparse
import json
import statistics
import time
from datetime import date
from pathlib import Path

from clinical_risk_agent.contracts import EvidenceStatus, RetrievalQuery
from clinical_risk_agent.rag.index import BM25Index
from clinical_risk_agent.rag.medcpt import MedCPTEncoder
from clinical_risk_agent.rag.qdrant_index import QdrantScientificIndex
from clinical_risk_agent.rag.retrieval import HybridRetriever
from clinical_risk_agent.rag.support import CuratedClaimSupport, SupportAssertion

from rag_benchmark import ROOT, _sha256, _snapshot


class UnavailableDense:
    def search(self, query: str, *, limit: int):
        raise RuntimeError("Injected dense outage")


class UnavailableSparse:
    def sparse_search(self, query: str, *, limit: int):
        raise RuntimeError("Injected primary sparse outage")


class UnavailableBM25(BM25Index):
    def search(self, *args, **kwargs):
        raise RuntimeError("Injected independent fallback outage")


CASES = (
    ("ADHD disorder", "Is childhood ADHD associated with later substance abuse or dependence?",
     "childhood_adhd_later_abuse_dependence", "21382538"),
    ("ADHD use", "Did the MTA childhood ADHD cohort find more frequent cannabis use and smoking by age 25?",
     "mta_childhood_adhd_later_use_frequency", "29315559"),
    ("Peer use", "Is fifth-grade peer victimization associated with later adolescent substance use?",
     "peer_victimization_later_substance_use", "28562268"),
    ("Cyber experimentation", "Is cyberbullying victimization associated with later substance experimentation?",
     "cybervictimization_later_experimentation", "40625792"),
    ("Perpetration use", "Is bullying perpetration associated with smoking or drinking at age 13?",
     "bullying_perpetration_early_smoking_drinking", "33224066"),
    ("Cyber disorder", "Does cyberbullying victimization predict diagnosed substance use disorder?",
     "cybervictimization_later_diagnosed_sud", None),
    ("Peer disorder", "Does fifth-grade peer victimization predict diagnosed substance use disorder?",
     "peer_victimization_later_diagnosed_sud", None),
    ("Perpetration disorder", "Does bullying perpetration predict diagnosed substance use disorder?",
     "bullying_perpetration_later_diagnosed_sud", None),
    ("MTA disorder", "Does the MTA childhood ADHD cohort report diagnosed substance use disorder?",
     "mta_childhood_adhd_later_diagnosed_sud", None),
)


def _check(result, expected_pmid, passages):
    ids = [item.pmid for item in result.items]
    if expected_pmid is None:
        if result.status != EvidenceStatus.NO_ELIGIBLE_EVIDENCE or result.items or result.displays:
            raise AssertionError(f"Unsupported claim outcome: {result.status.value}, {ids}")
    elif result.status != EvidenceStatus.SUFFICIENT or expected_pmid not in ids:
        raise AssertionError("Expected direct evidence was not returned")
    if len(ids) != len(set(ids)) or len(ids) > 5:
        raise AssertionError("Source cap or deduplication failed")
    for rank, (item, display) in enumerate(zip(result.items, result.displays, strict=True), 1):
        if item.chunk_id not in passages or item.exact_matched_text != passages[item.chunk_id].exact_text:
            raise AssertionError("Citation excerpt differs from indexed passage")
        if item.citation_id != f"S{rank}" or display.citation_id != item.citation_id:
            raise AssertionError("Citation IDs are not contiguous")
        if display.exact_matched_text != item.exact_matched_text or display.source_id != item.source_id:
            raise AssertionError("Display record differs from retrieved evidence")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=ROOT / "data/indexes/rag_corpus_manifest.json")
    parser.add_argument("--catalog", type=Path, default=ROOT / "agent_docs/RAG_21_SOURCE_CLAIM_SUPPORT_CATALOG.json")
    parser.add_argument("--pin", type=Path, default=ROOT / "agent_docs/RAG_MEDCPT_ENCODER_PIN.json")
    parser.add_argument("--qdrant-path", type=Path, default=ROOT / "data/indexes/qdrant")
    parser.add_argument("--output", type=Path, default=ROOT / "data/indexes/rag_support_integration_results.json")
    args = parser.parse_args()
    corpus = json.loads(args.corpus.read_text())
    catalog = json.loads(args.catalog.read_text())
    pin = json.loads(args.pin.read_text())
    if catalog["corpus_manifest_sha256"] != _sha256(args.corpus) or catalog["strategy"] != "hierarchical":
        raise ValueError("Claim catalog differs from active corpus or strategy")
    if corpus["query_model_sha256"] != pin["models"]["query"]["model_safetensors_sha256"]:
        raise ValueError("Query encoder differs from indexed artifact")
    if corpus["article_model_sha256"] != pin["models"]["article"]["model_safetensors_sha256"]:
        raise ValueError("Article encoder differs from indexed artifact")
    today = date.today()
    snapshot = _snapshot(corpus["snapshots"]["hierarchical"], "hierarchical")
    if snapshot.active_passages(today=today) != snapshot.passages:
        raise ValueError("Corpus has stale or ineligible passages")
    support = CuratedClaimSupport(snapshot, [SupportAssertion(**row) for row in catalog["assertions"]],
                                  expected_version=corpus["snapshots"]["hierarchical"]["corpus_version"])
    passages = {item.chunk_id: item for item in snapshot.passages}
    encoder = MedCPTEncoder.from_local(
        ROOT / pin["models"]["query"]["local_dir"],
        ROOT / pin["models"]["article"]["local_dir"],
        query_sha256=corpus["query_model_sha256"], article_sha256=corpus["article_model_sha256"])
    from qdrant_client import QdrantClient

    rows = []
    open_start = time.perf_counter()
    client = QdrantClient(path=str(args.qdrant_path))
    try:
        collection = corpus["collections"]["hierarchical"]
        if not client.collection_exists(collection) or client.count(collection, exact=True).count != len(passages):
            raise ValueError("Pinned Qdrant collection missing or wrong size")
        lexical = BM25Index(snapshot)
        qdrant = QdrantScientificIndex(client, collection, encoder, lexical)
        routes = {
            "primary": HybridRetriever(snapshot, lexical, qdrant, primary_sparse_searcher=qdrant,
                                        dense_min_cosine=0.0, support_checker=support),
            "configured": HybridRetriever(snapshot, lexical, qdrant, primary_sparse_searcher=qdrant,
                                           dense_min_cosine=0.85, support_checker=support),
            "dense_outage": HybridRetriever(snapshot, lexical, UnavailableDense(),
                                             primary_sparse_searcher=qdrant, support_checker=support),
            "primary_sparse_outage": HybridRetriever(snapshot, lexical, qdrant,
                                                      primary_sparse_searcher=UnavailableSparse(),
                                                      dense_min_cosine=0.0, support_checker=support),
        }
        for route, retriever in routes.items():
            for name, question, claim_id, expected in CASES:
                start = time.perf_counter()
                result = retriever.retrieve(RetrievalQuery(question, claim_id=claim_id), today=today)
                try:
                    _check(result, expected, passages)
                except AssertionError as error:
                    raise AssertionError(f"{route}/{name}: {error}; primary={result.primary_status.value}; fallback={result.fallback_status.value}") from error
                rows.append({"route": route, "case": name, "status": result.status.value,
                             "mode": result.retrieval_mode.value if result.retrieval_mode else None,
                             "primary_status": result.primary_status.value,
                             "fallback_status": result.fallback_status.value,
                             "pmids": [item.pmid for item in result.items],
                             "latency_ms": round((time.perf_counter() - start) * 1000, 2)})
        dual = HybridRetriever(snapshot, UnavailableBM25(snapshot), UnavailableDense(),
                               support_checker=support).retrieve(
            RetrievalQuery(CASES[0][1], claim_id=CASES[0][2]), today=today)
        if dual.status != EvidenceStatus.RETRIEVAL_UNAVAILABLE or dual.items:
            raise AssertionError("Dual outage did not return typed unavailable")
    finally:
        client.close()
    # Embedded Qdrant keeps a local storage lock: reopening after close tests restore.
    restored = QdrantClient(path=str(args.qdrant_path))
    try:
        if restored.count(corpus["collections"]["hierarchical"], exact=True).count != len(passages):
            raise AssertionError("Collection was not restored with the same passage count")
    finally:
        restored.close()
    output = {"schema_version": 1, "status": "research_only_integration_diagnostic",
              "run_on": today.isoformat(), "corpus_sha256": _sha256(args.corpus),
              "catalog_sha256": _sha256(args.catalog), "rows": rows,
              "dual_outage_status": dual.status.value,
              "qdrant_restore_passed": True,
              "median_latency_ms": statistics.median(row["latency_ms"] for row in rows),
              "p95_latency_ms": sorted(row["latency_ms"] for row in rows)[int(.95 * len(rows)) - 1],
              "retrieval_checks_and_restore_ms": round((time.perf_counter() - open_start) * 1000, 2),
              "limitations": ["Typed claim IDs and five curated assertions cover a bounded research subset.",
                              "This does not approve a runtime gate or test a user-query claim extractor.",
                              "The local injected outages do not simulate every dependency failure."]}
    args.output.write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps({"routes": len(routes), "checks": len(rows),
                      "dual_outage_status": dual.status.value,
                      "median_latency_ms": output["median_latency_ms"],
                      "p95_latency_ms": output["p95_latency_ms"]}))


if __name__ == "__main__":
    main()
