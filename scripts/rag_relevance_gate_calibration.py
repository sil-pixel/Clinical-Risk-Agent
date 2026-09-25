"""Explore dense relevance and no-evidence gates without changing runtime policy."""

from __future__ import annotations

import argparse
import json
import statistics
from datetime import date
from pathlib import Path

from clinical_risk_agent.contracts import EvidenceStatus, RetrievalQuery
from clinical_risk_agent.rag.index import BM25Index
from clinical_risk_agent.rag.medcpt import MedCPTEncoder
from clinical_risk_agent.rag.qdrant_index import QdrantScientificIndex
from clinical_risk_agent.rag.retrieval import HybridRetriever

from rag_benchmark import ROOT, _sha256, _snapshot
from rag_general_benchmark import _validate


class _UnavailableDense:
    def search(self, query: str, *, limit: int):
        raise RuntimeError("Diagnostic forced dense outage")


def _gate_rows(rows: list[dict], cutoff: float) -> dict:
    positives = [row for row in rows if row["answerable"]]
    negatives = [row for row in rows if not row["answerable"]]
    direct_hits = 0
    accepted_positives = 0
    abstained_negatives = 0
    retained_counts = []
    for row in rows:
        retained = [hit for hit in row["diagnostic_top_5"]
                    if hit["dense_cosine"] is not None and hit["dense_cosine"] > cutoff]
        retained_counts.append(len(retained))
        if row["answerable"]:
            accepted_positives += bool(retained)
            direct_hits += any(hit["pmid"] in row["direct_pmids"] for hit in retained)
        else:
            abstained_negatives += not retained
    return {
        "cutoff_strictly_greater_than": cutoff,
        "direct_source_recall_at_5_answerable": direct_hits / len(positives) if positives else None,
        "answerable_acceptance_rate": accepted_positives / len(positives) if positives else None,
        "no_direct_evidence_abstention_rate": abstained_negatives / len(negatives) if negatives else None,
        "false_evidence_return_rate_no_direct_evidence": 1 - abstained_negatives / len(negatives) if negatives else None,
        "mean_retained_sources": statistics.mean(retained_counts),
        "direct_hits": direct_hits,
        "answerable_count": len(positives),
        "no_direct_evidence_abstentions": abstained_negatives,
        "no_direct_evidence_count": len(negatives),
    }


def _path_summary(rows: list[dict], prefix: str) -> dict:
    positives = [row for row in rows if row["answerable"]]
    negatives = [row for row in rows if not row["answerable"]]
    direct = sum(bool(set(row[f"{prefix}_top_5_pmids"]) & set(row["direct_pmids"]))
                 for row in positives)
    return {
        "answerable_count": len(positives), "direct_source_found_at_5": direct,
        "no_direct_evidence_count": len(negatives),
        "no_direct_evidence_returned_sources": sum(bool(row[f"{prefix}_top_5_pmids"])
                                                   for row in negatives),
        "keyword_fallback_cases": sum(row[f"{prefix}_retrieval_mode"] == "keyword_fallback"
                                      for row in rows),
        "no_evidence_status_cases": sum(
            row[f"{prefix}_status"] == EvidenceStatus.NO_ELIGIBLE_EVIDENCE.value
            for row in rows),
        "unavailable_status_cases": sum(
            row[f"{prefix}_status"] == EvidenceStatus.RETRIEVAL_UNAVAILABLE.value
            for row in rows),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, default=ROOT / "agent_docs/RAG_RELEVANCE_GATE_CALIBRATION_SPEC.json")
    parser.add_argument("--corpus", type=Path, default=ROOT / "data/indexes/rag_corpus_manifest.json")
    parser.add_argument("--pin", type=Path, default=ROOT / "agent_docs/RAG_MEDCPT_ENCODER_PIN.json")
    parser.add_argument("--qdrant-path", type=Path, default=ROOT / "data/indexes/qdrant")
    parser.add_argument("--output", type=Path, default=ROOT / "data/indexes/rag_relevance_gate_calibration.json")
    args = parser.parse_args()

    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    corpus = json.loads(args.corpus.read_text(encoding="utf-8"))
    pin = json.loads(args.pin.read_text(encoding="utf-8"))
    gold_path = ROOT / spec["gold_path"]
    gold = json.loads(gold_path.read_text(encoding="utf-8"))
    _validate(gold, corpus, gold_path, args.corpus)
    if spec["gold_sha256"] != _sha256(gold_path):
        raise ValueError("Gold changed after calibration spec lock")
    if spec["corpus_manifest_sha256"] != _sha256(args.corpus):
        raise ValueError("Corpus changed after calibration spec lock")
    if spec["status"] != "pre_run_locked_exploratory_not_approved_threshold":
        raise ValueError("Unexpected calibration specification status")
    if spec["strategy"] != "hierarchical" or spec["ranking"] != "relevance_first_RRF_no_cross_encoder":
        raise ValueError("Unexpected retrieval configuration")
    if gold["predeclared_run"].get("ranking") not in (None, "relevance_first"):
        raise ValueError("Gold ranking differs from calibration specification")
    probes = spec.get("exploratory_no_direct_probes", [])
    if len({case["id"] for case in gold["cases"] + probes}) != len(gold["cases"] + probes):
        raise ValueError("Duplicate calibration case ID")
    if any(case["grades"] or case["reference_answer"] is not None for case in probes):
        raise ValueError("Exploratory probes must be no-direct-evidence questions")
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
    snapshot = _snapshot(corpus["snapshots"]["hierarchical"], "hierarchical")
    if snapshot.active_passages(today=today) != snapshot.passages:
        raise ValueError("Corpus contains stale or ineligible passages")
    client = QdrantClient(path=str(args.qdrant_path))
    rows = []
    try:
        name = corpus["collections"]["hierarchical"]
        if not client.collection_exists(name) or client.count(name, exact=True).count != len(snapshot.passages):
            raise ValueError("Qdrant collection does not match frozen snapshot")
        lexical = BM25Index(snapshot)
        qdrant = QdrantScientificIndex(client, name, encoder, lexical)
        diagnostic = HybridRetriever(
            snapshot, lexical, qdrant, primary_sparse_searcher=qdrant,
            dense_min_cosine=spec["diagnostic_candidate_dense_min_cosine_strictly_greater_than"],
            relevance_first=True,
        )
        configured = HybridRetriever(
            snapshot, lexical, qdrant, primary_sparse_searcher=qdrant,
            dense_min_cosine=spec["current_configured_dense_min_cosine_strictly_greater_than"],
            relevance_first=True,
        )
        outage = HybridRetriever(
            snapshot, lexical, _UnavailableDense(), primary_sparse_searcher=qdrant,
            dense_min_cosine=spec["current_configured_dense_min_cosine_strictly_greater_than"],
            relevance_first=True,
        )
        for case in gold["cases"] + probes:
            query = RetrievalQuery(case["query"])
            measured = diagnostic.retrieve(query, today=today)
            as_configured = configured.retrieve(query, today=today)
            as_outage = outage.retrieve(query, today=today)
            top = [{"pmid": item.pmid, "chunk_id": item.chunk_id,
                    "dense_cosine": item.dense_cosine,
                    "lexical_score": item.lexical_score,
                    "fused_score": item.retrieval_score}
                   for item in measured.items]
            direct = [pmid for pmid, grade in case["grades"].items() if grade == 2]
            rows.append({
                "id": case["id"], "topic": case["topic"],
                "label_origin": "gold" if case in gold["cases"] else "exploratory_probe",
                "answerable": bool(direct), "direct_pmids": direct,
                "diagnostic_top_5": top,
                "max_selected_dense_cosine": max(
                    (item["dense_cosine"] for item in top if item["dense_cosine"] is not None),
                    default=None,
                ),
                "max_direct_selected_dense_cosine": max(
                    (item["dense_cosine"] for item in top
                     if item["pmid"] in direct and item["dense_cosine"] is not None),
                    default=None,
                ),
                "configured_status": as_configured.status.value,
                "configured_retrieval_mode": (
                    as_configured.retrieval_mode.value if as_configured.retrieval_mode else None
                ),
                "configured_top_5_pmids": [item.pmid for item in as_configured.items],
                "configured_primary_status": as_configured.primary_status.value,
                "configured_fallback_status": as_configured.fallback_status.value,
                "outage_status": as_outage.status.value,
                "outage_retrieval_mode": (
                    as_outage.retrieval_mode.value if as_outage.retrieval_mode else None
                ),
                "outage_top_5_pmids": [item.pmid for item in as_outage.items],
                "outage_primary_status": as_outage.primary_status.value,
                "outage_fallback_status": as_outage.fallback_status.value,
            })
    finally:
        client.close()

    sweep = {
        origin: [_gate_rows(group, float(cutoff))
                 for cutoff in spec["dense_cosine_cutoffs_strictly_greater_than"]]
        for origin, group in (("gold", [row for row in rows if row["label_origin"] == "gold"]),
                              ("exploratory_probes", [row for row in rows
                                                       if row["label_origin"] == "exploratory_probe"]))
        if group
    }
    output = {
        "schema_version": 1, "run_on": today.isoformat(),
        "status": "exploratory_no_threshold_approved",
        "spec_sha256": _sha256(args.spec), "gold_sha256": _sha256(gold_path),
        "corpus_manifest_sha256": _sha256(args.corpus),
        "collection": corpus["collections"]["hierarchical"],
        "candidate_gate_rule": spec["candidate_gate_rule"],
        "selection_policy": spec["selection_policy"],
        "cases": rows,
        "sweep": sweep,
        "configured_path": {origin: _path_summary(group, "configured")
                            for origin, group in (("gold", [row for row in rows if row["label_origin"] == "gold"]),
                                                  ("exploratory_probes", [row for row in rows if row["label_origin"] == "exploratory_probe"]))},
        "forced_dense_outage_path": {origin: _path_summary(group, "outage")
                                     for origin, group in (("gold", [row for row in rows if row["label_origin"] == "gold"]),
                                                           ("exploratory_probes", [row for row in rows if row["label_origin"] == "exploratory_probe"]))},
        "limitations": [
            "The gold questions were already used to compare strategies, and exploratory probes were authored for this diagnostic; neither is an untouched calibration split.",
            "The judgments are provisional AI-reviewed source-level labels, not human or independent passage-level adjudications.",
            "Dense cosine is model-specific and does not establish whether an abstract directly supports a particular association.",
            "The simulated gate drops selected passages and does not refill from lower ranks or model lexical-only fallback recovery.",
            "The forced dense outage tests only the independently available BM25 fallback, not all Qdrant failure modes.",
            "No threshold is approved and no runtime behavior is changed by this script.",
        ],
    }
    args.output.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(json.dumps({"configured_path": output["configured_path"],
                      "forced_dense_outage_path": output["forced_dense_outage_path"]}, sort_keys=True))
    for origin, group in sweep.items():
        for row in group:
            print(origin, json.dumps(row, sort_keys=True))
    print(f"Results: {args.output}")


if __name__ == "__main__":
    main()
