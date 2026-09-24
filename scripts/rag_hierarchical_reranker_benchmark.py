"""Compare two pinned rerankers on the existing frozen hierarchical corpus."""

from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import time
from datetime import date
from pathlib import Path

from clinical_risk_agent.contracts import RetrievalQuery
from clinical_risk_agent.rag.index import BM25Index
from clinical_risk_agent.rag.medcpt import MedCPTEncoder, MedCPTReranker
from clinical_risk_agent.rag.qdrant_index import QdrantScientificIndex
from clinical_risk_agent.rag.retrieval import HybridRetriever

from rag_benchmark import ROOT, _sha256, _snapshot
from rag_general_benchmark import _scores, _validate


def _latency(rows: list[dict]) -> dict[str, float]:
    times = sorted(row["retrieve_latency_ms"] for row in rows)
    return {
        "median_retrieve_latency_ms": statistics.median(times),
        "p95_retrieve_latency_ms": times[math.ceil(0.95 * len(times)) - 1],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment", type=Path, default=ROOT / "agent_docs/RAG_HIERARCHICAL_RERANKER_EXPERIMENT.json")
    parser.add_argument("--corpus", type=Path, default=ROOT / "data/indexes/rag_corpus_manifest.json")
    parser.add_argument("--encoder-pin", type=Path, default=ROOT / "agent_docs/RAG_MEDCPT_ENCODER_PIN.json")
    parser.add_argument("--qdrant-path", type=Path, default=ROOT / "data/indexes/qdrant")
    parser.add_argument("--bert-model", type=Path, default=ROOT / "data/indexes/models/BERTScore-DistilBERT")
    parser.add_argument("--output", type=Path, default=ROOT / "data/indexes/rag_hierarchical_reranker_results.json")
    args = parser.parse_args()

    experiment = json.loads(args.experiment.read_text(encoding="utf-8"))
    gold_path = ROOT / experiment["gold_path"]
    gold = json.loads(gold_path.read_text(encoding="utf-8"))
    corpus = json.loads(args.corpus.read_text(encoding="utf-8"))
    pin = json.loads(args.encoder_pin.read_text(encoding="utf-8"))
    _validate(gold, corpus, gold_path, args.corpus)
    if experiment["gold_sha256"] != _sha256(gold_path):
        raise ValueError("Gold judgments changed after experiment lock")
    if experiment["corpus_manifest_sha256"] != _sha256(args.corpus):
        raise ValueError("Corpus changed after experiment lock")
    if experiment["strategy"] != "hierarchical" or experiment["status"] != "pre_run_locked_exploratory_reuse_of_prior_gold":
        raise ValueError("Unexpected experiment configuration")
    if corpus["query_model_sha256"] != pin["models"]["query"]["model_safetensors_sha256"]:
        raise ValueError("Query encoder differs from indexed artifact")
    if corpus["article_model_sha256"] != pin["models"]["article"]["model_safetensors_sha256"]:
        raise ValueError("Article encoder differs from indexed artifact")
    if _sha256(args.bert_model / "model.safetensors") != "5e3f1108e3cb34ee048634875d8482665b65ac713291a7e32396fb18f6ff0063":
        raise ValueError("BERTScore evaluator differs from frozen comparison")

    import torch
    torch.set_num_threads(4)
    encoder = MedCPTEncoder.from_local(
        ROOT / pin["models"]["query"]["local_dir"],
        ROOT / pin["models"]["article"]["local_dir"],
        query_sha256=corpus["query_model_sha256"],
        article_sha256=corpus["article_model_sha256"],
    )
    from qdrant_client import QdrantClient

    today = date.today()
    snapshot = _snapshot(corpus["snapshots"]["hierarchical"], "hierarchical")
    if snapshot.active_passages(today=today) != snapshot.passages:
        raise ValueError("Corpus contains stale or ineligible passages")
    client = QdrantClient(path=str(args.qdrant_path))
    results: dict[str, dict] = {}
    try:
        name = corpus["collections"]["hierarchical"]
        if not client.collection_exists(name) or client.count(name, exact=True).count != len(snapshot.passages):
            raise ValueError("Qdrant collection does not match frozen snapshot")
        lexical = BM25Index(snapshot)
        qdrant = QdrantScientificIndex(client, name, encoder, lexical)
        for arm, details in experiment["arms"].items():
            reranker = None
            if details.get("local_dir") is not None:
                model_dir = ROOT / details["local_dir"]
                expected = details.get("converted_safetensors_sha256", details.get("model_safetensors_sha256"))
                reranker = MedCPTReranker.from_local(model_dir, sha256=expected)
                # Exclude one-time model initialization from warm retrieval latency.
                reranker.score(gold["cases"][0]["query"], snapshot.passages[0])
            retriever = HybridRetriever(
                snapshot, lexical, qdrant, primary_sparse_searcher=qdrant,
                reranker=reranker, relevance_first=True,
                dense_min_cosine=experiment["candidate_pipeline"]["dense_min_cosine_strictly_greater_than"],
            )
            rows: list[dict] = []
            for case in gold["cases"]:
                start = time.perf_counter()
                result = retriever.retrieve(RetrievalQuery(case["query"]), today=today)
                elapsed = (time.perf_counter() - start) * 1000
                ranked = [item.source_id for item in result.items]
                row = {
                    "id": case["id"], "topic": case["topic"],
                    "answerable": bool(case["grades"]),
                    "top_5_pmids": [item.removeprefix("pmid:") for item in ranked],
                    "top_1_passage": result.items[0].exact_matched_text if result.items else None,
                    "retrieval_mode": result.retrieval_mode.value if result.retrieval_mode else None,
                    "primary_status": result.primary_status.value,
                    "retrieve_latency_ms": round(elapsed, 3),
                }
                if case["grades"]:
                    row.update(_scores(ranked, case["grades"], 5))
                rows.append(row)
            results[arm] = {"cases": rows}
            print(f"Completed {arm}: {len(rows)} queries", flush=True)
            del reranker
    finally:
        client.close()

    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    from bert_score import BERTScorer

    scorer = BERTScorer(model_type=str(args.bert_model), num_layers=5, idf=False,
                        rescale_with_baseline=False, device="cpu", use_fast_tokenizer=True)
    references = {case["id"]: case["reference_answer"] for case in gold["cases"]}
    keys = ("precision_at_5", "recall_at_5", "bert_score_f1_top_1", "ndcg_at_5", "mrr_at_5")
    for arm, run in results.items():
        rows = run["cases"]
        answerable = [row for row in rows if row["answerable"]]
        _, _, f1 = scorer.score(
            [row["top_1_passage"] or "" for row in answerable],
            [references[row["id"]] for row in answerable], batch_size=4,
        )
        for row, score in zip(answerable, f1.tolist(), strict=True):
            row["bert_score_f1_top_1"] = float(score)
        run["metrics"] = {key: statistics.mean(row[key] for row in answerable) for key in keys}
        run["metrics"].update(_latency(rows))
        run["metrics"].update({
            "answerable_cases": len(answerable),
            "no_direct_evidence_cases": len(rows) - len(answerable),
            "primary_hybrid_cases": sum(row["retrieval_mode"] == "primary_hybrid" for row in rows),
            "keyword_fallback_cases": sum(row["retrieval_mode"] == "keyword_fallback" for row in rows),
        })
        print(arm, json.dumps(run["metrics"], sort_keys=True), flush=True)
    output = {
        "schema_version": 1, "run_on": today.isoformat(),
        "status": "research_only_exploratory_not_release_benchmark",
        "experiment_sha256": _sha256(args.experiment),
        "gold_sha256": _sha256(gold_path),
        "corpus_manifest_sha256": _sha256(args.corpus),
        "collection": corpus["collections"]["hierarchical"],
        "candidate_pipeline": experiment["candidate_pipeline"],
        "arms": experiment["arms"], "results": results,
        "limitations": experiment["cautions"] + [
            "Warm per-query latency includes local Qdrant hybrid retrieval and reranking but excludes model load and BERTScore evaluation.",
            "Reranking can only reorder the top 20 fused candidates; it cannot recover an absent source.",
            "No-evidence cases return candidates because no calibrated abstention threshold is implemented.",
        ],
    }
    args.output.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"Results: {args.output}")


if __name__ == "__main__":
    main()
