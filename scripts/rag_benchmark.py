"""Run a locked, source-level retrieval diagnostic on the local Qdrant corpus."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import time
from datetime import date
from pathlib import Path

from clinical_risk_agent.contracts import EvidenceStatus, RetrievalQuery
from clinical_risk_agent.rag.chunking import Passage
from clinical_risk_agent.rag.corpus import ScientificSource, SourceSection
from clinical_risk_agent.rag.index import BM25Index, CorpusSnapshot
from clinical_risk_agent.rag.medcpt import MedCPTEncoder
from clinical_risk_agent.rag.qdrant_index import QdrantScientificIndex
from clinical_risk_agent.rag.retrieval import HybridRetriever


ROOT = Path(__file__).resolve().parents[1]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _source(raw: dict) -> ScientificSource:
    item = dict(raw)
    item["authors"] = tuple(item["authors"])
    item["published_on"] = date.fromisoformat(item["published_on"])
    item["retraction_checked_on"] = date.fromisoformat(item["retraction_checked_on"])
    item["full_text_sections"] = tuple(
        SourceSection(**section) for section in item["full_text_sections"]
    )
    return ScientificSource(**item)


def _snapshot(raw: dict, strategy: str) -> CorpusSnapshot:
    return CorpusSnapshot(
        version=raw["corpus_version"], strategy=strategy,
        sources=tuple(_source(item) for item in raw["sources"]),
        passages=tuple(Passage(**item) for item in raw["passages"]),
    )


def _metrics(rows: list[dict]) -> dict:
    positive = [row for row in rows if row["positive_pmids"]]
    negative = [row for row in rows if not row["positive_pmids"]]
    ranks = [row["positive_rank"] for row in positive]
    latency = sorted(row["retrieve_latency_ms"] for row in rows)
    predicted_empty = [row for row in rows if row["status"] == EvidenceStatus.NO_ELIGIBLE_EVIDENCE.value]
    true_empty = [row for row in predicted_empty if not row["positive_pmids"]]
    return {
        "cases": len(rows), "answerable_cases": len(positive),
        "no_evidence_cases": len(negative),
        "hit_at_1_answerable": sum(rank == 1 for rank in ranks) / len(ranks),
        "recall_at_5_answerable": sum(rank is not None and rank <= 5 for rank in ranks) / len(ranks),
        "recall_at_10_answerable": sum(rank is not None and rank <= 10 for rank in ranks) / len(ranks),
        "mrr_at_10_answerable": statistics.mean(
            1 / rank if rank is not None and rank <= 10 else 0 for rank in ranks
        ),
        "ndcg_at_10_answerable": statistics.mean(
            1 / math.log2(rank + 1) if rank is not None and rank <= 10 else 0
            for rank in ranks
        ),
        "no_evidence_precision": len(true_empty) / len(predicted_empty) if predicted_empty else None,
        "no_evidence_recall": len(true_empty) / len(negative),
        "primary_hybrid_cases": sum(row["retrieval_mode"] == "primary_hybrid" for row in rows),
        "keyword_fallback_cases": sum(row["retrieval_mode"] == "keyword_fallback" for row in rows),
        "dense_candidate_cases": sum(row["primary_status"] == "success" for row in rows),
        "median_retrieve_latency_ms": statistics.median(latency),
        "p95_retrieve_latency_ms": latency[math.ceil(0.95 * len(latency)) - 1],
        "max_retrieve_latency_ms": latency[-1],
    }


def _run(retriever: HybridRetriever, cases: list[dict], today: date) -> dict:
    rows = []
    for case in cases:
        query = RetrievalQuery(case["query"])
        start = time.perf_counter()
        result = retriever.retrieve(query, today=today)
        latency_ms = (time.perf_counter() - start) * 1000
        ranked = retriever.rank_source_ids_for_evaluation(query, today=today, limit=20)
        positive_ids = {f"pmid:{pmid}" for pmid in case["positive_pmids"]}
        rank = next((position for position, item in enumerate(ranked, start=1)
                     if item in positive_ids), None)
        rows.append({
            "id": case["id"], "origin": case["origin"],
            "positive_pmids": case["positive_pmids"],
            "positive_rank": rank,
            "top_5_pmids": [item.removeprefix("pmid:") for item in ranked[:5]],
            "status": result.status.value,
            "retrieval_mode": result.retrieval_mode.value if result.retrieval_mode else None,
            "primary_status": result.primary_status.value,
            "retrieve_latency_ms": round(latency_ms, 3),
        })
    return {"metrics": _metrics(rows), "cases": rows}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=ROOT / "data/indexes/rag_corpus_manifest.json")
    parser.add_argument("--qrels", type=Path, default=ROOT / "agent_docs/RAG_BENCHMARK_16_SOURCE_QRELS.json")
    parser.add_argument("--pin", type=Path, default=ROOT / "agent_docs/RAG_MEDCPT_ENCODER_PIN.json")
    parser.add_argument("--qdrant-path", type=Path, default=ROOT / "data/indexes/qdrant")
    parser.add_argument("--output", type=Path, default=ROOT / "data/indexes/rag_benchmark_16_source_results.json")
    args = parser.parse_args()

    corpus = json.loads(args.corpus.read_text(encoding="utf-8"))
    qrels = json.loads(args.qrels.read_text(encoding="utf-8"))
    pin = json.loads(args.pin.read_text(encoding="utf-8"))
    if _sha256(args.corpus) != qrels["corpus_manifest_sha256"]:
        raise ValueError("Corpus changed after qrels lock")
    if _sha256(Path(corpus["source_manifest"])) != qrels["source_manifest_sha256"]:
        raise ValueError("Source approvals changed after qrels lock")
    if _sha256(ROOT / "agent_docs/RAG_RELEVANCE_JUDGMENTS_DRAFT.json") != qrels["prior_draft_sha256"]:
        raise ValueError("Original query draft changed after qrels lock")
    if qrels["status"] != "pre_run_locked_assistant_judgments_not_dual_adjudicated":
        raise ValueError("Unexpected relevance-judgment state")
    cases = qrels["cases"]
    if not cases or len({item["id"] for item in cases}) != len(cases):
        raise ValueError("Cases must be unique and nonempty")
    corpus_pmids = set(corpus["source_pmids"])
    if {pmid for case in cases for pmid in case["positive_pmids"]} != corpus_pmids:
        raise ValueError("Qrels must cover every source in this small diagnostic corpus")
    if any(len(case["positive_pmids"]) > 1 for case in cases):
        raise ValueError("This diagnostic expects zero or one source-level positive per case")
    if corpus["query_model_sha256"] != pin["models"]["query"]["model_safetensors_sha256"]:
        raise ValueError("Query encoder differs from indexed artifact")
    if corpus["article_model_sha256"] != pin["models"]["article"]["model_safetensors_sha256"]:
        raise ValueError("Article encoder differs from indexed artifact")

    encoder = MedCPTEncoder.from_local(
        ROOT / pin["models"]["query"]["local_dir"],
        ROOT / pin["models"]["article"]["local_dir"],
        query_sha256=corpus["query_model_sha256"],
        article_sha256=corpus["article_model_sha256"],
    )
    from qdrant_client import QdrantClient

    today = date.today()
    client = QdrantClient(path=str(args.qdrant_path))
    try:
        prepared = {}
        for strategy in ("document", "hierarchical"):
            snapshot = _snapshot(corpus["snapshots"][strategy], strategy)
            if snapshot.active_passages(today=today) != snapshot.passages:
                raise ValueError("Corpus contains stale or ineligible passages")
            name = corpus["collections"][strategy]
            if not client.collection_exists(name) or client.count(name, exact=True).count != len(snapshot.passages):
                raise ValueError("Qdrant collection does not match frozen snapshot")
            lexical = BM25Index(snapshot)
            qdrant = QdrantScientificIndex(client, name, encoder, lexical)
            prepared[strategy] = (snapshot, lexical, qdrant)
        results = {}
        for run in qrels["predeclared_runs"]:
            variants = {}
            for strategy in ("document", "hierarchical"):
                snapshot, lexical, qdrant = prepared[strategy]
                retriever = HybridRetriever(
                    snapshot, lexical, qdrant,
                    primary_sparse_searcher=qdrant,
                    dense_min_cosine=run["dense_min_cosine_strictly_greater_than"],
                    relevance_first=False,  # Reproduce the historical evidence-first run.
                )
                variants[strategy] = _run(retriever, cases, today)
            results[run["name"]] = variants
    finally:
        client.close()

    output = {
        "schema_version": 1, "run_on": today.isoformat(),
        "status": "provisional_source_level_diagnostic_not_release_benchmark",
        "qrels_sha256": _sha256(args.qrels),
        "corpus_manifest_sha256": _sha256(args.corpus),
        "source_pmids": corpus["source_pmids"],
        "collections": corpus["collections"],
        "model_sha256": {
            "query": corpus["query_model_sha256"],
            "article": corpus["article_model_sha256"],
        },
        "runs": results,
        "caveats": qrels["limitations"] + [
            "No cross-encoder reranker was pinned; both strategies use the same MedCPT encoders and hybrid/BM25 pipeline",
            "Retrieve latency is local warm sequential wall time and excludes the separate evaluation-ranking call",
            "No-evidence probes test answerability, not whether a topically related article can be retrieved",
        ],
    }
    args.output.write_text(json.dumps(output, indent=2), encoding="utf-8")
    for run_name, strategies in results.items():
        for strategy, result in strategies.items():
            print(run_name, strategy, json.dumps(result["metrics"], sort_keys=True))
    print(f"Report: {args.output}")


if __name__ == "__main__":
    main()
