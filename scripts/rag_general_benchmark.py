"""Compare document and hierarchical retrieval on frozen general-association questions."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import statistics
from datetime import date
from pathlib import Path

from clinical_risk_agent.contracts import RetrievalQuery
from clinical_risk_agent.rag.index import BM25Index
from clinical_risk_agent.rag.medcpt import MedCPTEncoder
from clinical_risk_agent.rag.qdrant_index import QdrantScientificIndex
from clinical_risk_agent.rag.retrieval import HybridRetriever

from rag_benchmark import ROOT, _sha256, _snapshot


def _scores(ranked: list[str], grades: dict[str, int], k: int) -> dict[str, float]:
    positives = {pmid for pmid, grade in grades.items() if grade == 2}
    top = [item.removeprefix("pmid:") for item in ranked[:k]]
    hits = [item for item in top if item in positives]
    ideal = sorted(grades.values(), reverse=True)[:k]

    def dcg(values: list[int]) -> float:
        return sum((2**grade - 1) / math.log2(rank + 1)
                   for rank, grade in enumerate(values, start=1))

    first = next((rank for rank, pmid in enumerate(top, start=1)
                  if pmid in positives), None)
    return {
        "precision_at_5": len(hits) / k,
        "recall_at_5": len(hits) / len(positives),
        "ndcg_at_5": dcg([grades.get(item, 0) for item in top]) / dcg(ideal),
        "mrr_at_5": 1 / first if first else 0.0,
    }


def _answerable(case: dict) -> bool:
    return 2 in case["grades"].values()


def _relevance_first(gold: dict) -> bool:
    ranking = gold["predeclared_run"].get("ranking", "evidence_first")
    if ranking not in ("evidence_first", "relevance_first"):
        raise ValueError("Unknown ranking configuration")
    return ranking == "relevance_first"


def _validate(gold: dict, corpus: dict, gold_path: Path, corpus_path: Path) -> None:
    if gold["status"] not in ("pre_run_locked_assistant_judgments_not_dual_adjudicated",
                              "pre_run_locked_provisional_ai_reviewed_research_only"):
        raise ValueError("Gold set is not in expected locked state")
    if gold["status"] == "pre_run_locked_provisional_ai_reviewed_research_only":
        lock = json.loads(gold_path.with_suffix(".lock.json").read_text())
        if lock["gold_sha256"] != _sha256(gold_path):
            raise ValueError("Gold bytes changed after lock")
    _relevance_first(gold)
    if gold["corpus_manifest_sha256"] != _sha256(corpus_path):
        raise ValueError("Corpus changed after gold lock")
    if gold["source_manifest_sha256"] != _sha256(Path(corpus["source_manifest"])):
        raise ValueError("Source manifest changed after gold lock")
    if gold["predeclared_run"]["k"] != 5:
        raise ValueError("Only predeclared k=5 is supported")
    cases = gold["cases"]
    if len({case["id"] for case in cases}) != len(cases):
        raise ValueError("Duplicate gold case")
    source_ids = set(corpus["source_pmids"])
    for case in cases:
        if not set(case["grades"]).issubset(source_ids):
            raise ValueError(f"Unknown gold PMID in {case['id']}")
        if any(type(grade) is not int or grade not in (0, 1, 2)
               for grade in case["grades"].values()):
            raise ValueError("Invalid relevance grade")
        if _answerable(case) and not case["reference_answer"]:
            raise ValueError(f"Answerable case lacks a direct source or reference: {case['id']}")
        if not _answerable(case) and case["reference_answer"] is not None:
            raise ValueError(f"No-evidence case has a reference answer: {case['id']}")
    if not gold_path.is_file():
        raise ValueError("Gold set missing")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=ROOT / "data/indexes/rag_corpus_manifest.json")
    parser.add_argument("--gold", type=Path, default=ROOT / "agent_docs/RAG_GENERAL_ASSOCIATION_GOLD_16_SOURCE.json")
    parser.add_argument("--pin", type=Path, default=ROOT / "agent_docs/RAG_MEDCPT_ENCODER_PIN.json")
    parser.add_argument("--qdrant-path", type=Path, default=ROOT / "data/indexes/qdrant")
    parser.add_argument("--bert-model", type=Path, default=ROOT / "data/indexes/models/BERTScore-DistilBERT")
    parser.add_argument("--output", type=Path, default=ROOT / "data/indexes/rag_general_benchmark_results.json")
    args = parser.parse_args()

    corpus = json.loads(args.corpus.read_text(encoding="utf-8"))
    gold = json.loads(args.gold.read_text(encoding="utf-8"))
    pin = json.loads(args.pin.read_text(encoding="utf-8"))
    _validate(gold, corpus, args.gold, args.corpus)
    if corpus["query_model_sha256"] != pin["models"]["query"]["model_safetensors_sha256"]:
        raise ValueError("Query encoder differs from indexed artifact")
    if corpus["article_model_sha256"] != pin["models"]["article"]["model_safetensors_sha256"]:
        raise ValueError("Article encoder differs from indexed artifact")
    bert_weights = args.bert_model / "model.safetensors"
    bert_sha256 = _sha256(bert_weights)
    if bert_sha256 != "5e3f1108e3cb34ee048634875d8482665b65ac713291a7e32396fb18f6ff0063":
        raise ValueError("BERTScore evaluator differs from pinned weights")

    encoder = MedCPTEncoder.from_local(
        ROOT / pin["models"]["query"]["local_dir"],
        ROOT / pin["models"]["article"]["local_dir"],
        query_sha256=corpus["query_model_sha256"],
        article_sha256=corpus["article_model_sha256"],
    )
    from qdrant_client import QdrantClient

    today = date.today()
    client = QdrantClient(path=str(args.qdrant_path))
    results: dict[str, dict] = {}
    try:
        for strategy in ("document", "hierarchical"):
            snapshot = _snapshot(corpus["snapshots"][strategy], strategy)
            if snapshot.active_passages(today=today) != snapshot.passages:
                raise ValueError("Corpus contains stale or ineligible passages")
            name = corpus["collections"][strategy]
            if not client.collection_exists(name) or client.count(name, exact=True).count != len(snapshot.passages):
                raise ValueError("Qdrant collection does not match frozen snapshot")
            lexical = BM25Index(snapshot)
            qdrant = QdrantScientificIndex(client, name, encoder, lexical)
            retriever = HybridRetriever(
                snapshot, lexical, qdrant, primary_sparse_searcher=qdrant,
                dense_min_cosine=gold["predeclared_run"]["dense_min_cosine_strictly_greater_than"],
                relevance_first=_relevance_first(gold),
            )
            rows = []
            for case in gold["cases"]:
                query = RetrievalQuery(case["query"])
                retrieved = retriever.retrieve(query, today=today)
                ranked = list(retriever.rank_source_ids_for_evaluation(query, today=today, limit=20))
                row = {
                    "id": case["id"], "topic": case["topic"], "query": case["query"],
                    "answerable": _answerable(case),
                    "evidence_status": retrieved.status.value,
                    "returned_count": len(retrieved.items),
                    "top_5_pmids": [item.removeprefix("pmid:") for item in ranked[:5]],
                    "top_1_passage": retrieved.items[0].exact_matched_text if retrieved.items else None,
                    "retrieval_mode": retrieved.retrieval_mode.value if retrieved.retrieval_mode else None,
                    "primary_status": retrieved.primary_status.value,
                }
                if _answerable(case):
                    row.update(_scores(ranked, case["grades"], 5))
                rows.append(row)
            results[strategy] = {"cases": rows}
    finally:
        client.close()

    # BERTScore is a supplementary passage-vs-reference semantic similarity,
    # not a replacement for source-level relevance judgments.
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    from bert_score import BERTScorer

    scorer = BERTScorer(model_type=str(args.bert_model), num_layers=5, idf=False,
                        rescale_with_baseline=False, device="cpu", use_fast_tokenizer=True)
    for strategy in ("document", "hierarchical"):
        rows = results[strategy]["cases"]
        answerable = [row for row in rows if row["answerable"]]
        references = {case["id"]: case["reference_answer"] for case in gold["cases"]}
        candidates = [row["top_1_passage"] or "" for row in answerable]
        _, _, f1 = scorer.score(candidates, [references[row["id"]] for row in answerable],
                                batch_size=4)
        for row, value in zip(answerable, f1.tolist(), strict=True):
            row["bert_score_f1_top_1"] = float(value)
        keys = ("precision_at_5", "recall_at_5", "bert_score_f1_top_1",
                "ndcg_at_5", "mrr_at_5")
        results[strategy]["metrics"] = {
            key: statistics.mean(row[key] for row in answerable) for key in keys
        }
        results[strategy]["metrics"].update({
            "answerable_cases": len(answerable),
            "no_direct_evidence_cases": len(rows) - len(answerable),
            "primary_hybrid_cases": sum(row["retrieval_mode"] == "primary_hybrid" for row in rows),
            "keyword_fallback_cases": sum(row["retrieval_mode"] == "keyword_fallback" for row in rows),
        })

    output = {
        "schema_version": 1, "run_on": today.isoformat(),
        "status": "research_only_provisional_not_clinical_or_release_benchmark",
        "gold_sha256": _sha256(args.gold), "corpus_manifest_sha256": _sha256(args.corpus),
        "collections": corpus["collections"], "source_pmids": corpus["source_pmids"],
        "encoder_sha256": {"query": corpus["query_model_sha256"],
                            "article": corpus["article_model_sha256"]},
        "bert_score_model": {"model_id": "distilbert/distilbert-base-uncased",
                             "revision": "12040accade4e8a0f71eabdb258fecc2e7e948be",
                             "weights_sha256": bert_sha256, "num_layers": 5,
                             "idf": False, "rescale_with_baseline": False},
        "metric_rule": gold["judgment_rule"], "predeclared_run": gold["predeclared_run"],
        "strategies": results, "limitations": gold["limitations"] + [
            "BERTScore compares top-1 retrieved passage with an assistant-written reference answer and is length-sensitive; it is not answer-generation quality or clinical correctness.",
            "Retrieval has no cross-encoder reranker; ranking is explicitly recorded in predeclared_run (historical default: evidence_first).",
            "No-evidence controls are reported separately and excluded from five-metric macro averages.",
        ],
    }
    args.output.write_text(json.dumps(output, indent=2), encoding="utf-8")
    for strategy, result in results.items():
        print(strategy, json.dumps(result["metrics"], sort_keys=True))
    print(f"Results: {args.output}")


if __name__ == "__main__":
    main()
