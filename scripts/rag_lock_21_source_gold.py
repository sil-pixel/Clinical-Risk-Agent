"""Consolidate authorized provisional AI judgments and lock before retrieval."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "agent_docs"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    names = ["RAG_GENERAL_ASSOCIATION_GOLD_16_SOURCE.json",
             "RAG_GENERAL_ASSOCIATION_GOLD_EXPANSION_REVIEW_DRAFT.json",
             "RAG_GENERAL_ASSOCIATION_GOLD_INDEPENDENT_AI_FIRST_PASS.json",
             "RAG_GENERAL_ASSOCIATION_GOLD_AI_ADJUDICATION_DRAFT.json"]
    parent, expansion, independent, reconciliation = [
        json.loads((DOCS / name).read_text()) for name in names]
    corpus_path = ROOT / "data/indexes/rag_corpus_manifest.json"
    corpus = json.loads(corpus_path.read_text())
    assert sha(DOCS / names[0]) == expansion["parent_gold_sha256"]
    assert sha(corpus_path) == expansion["corpus_manifest_sha256"]
    cases = {case["id"]: dict(case) for case in parent["cases"]}
    for proposal in expansion["parent_case_overrides"] + expansion["new_cases"]:
        case = cases.setdefault(proposal["id"], {
            "id": proposal["id"], "topic": proposal.get("topic"),
            "query": proposal.get("query")})
        case.update(grades=proposal["proposed_grades"],
                    reference_answer=proposal["proposed_reference_answer"])
    first = {case["id"]: case for case in independent["cases"]}
    for case_id in ("GEN-01", "ACE-01", "ACE-02"):
        cases[case_id]["reference_answer"] = first[case_id]["reference_answer"]
    for decision in reconciliation["decisions"]:
        case = cases[decision["id"]]
        case["grades"] = decision["recommended_grades"]
        case["reconciliation"] = decision["resolution"]
        if "recommended_reference_answer" in decision:
            case["reference_answer"] = decision["recommended_reference_answer"]
    assert len(cases) == 20 and set(cases) == set(first)
    for case in cases.values():
        assert set(case["grades"]) <= set(corpus["source_pmids"])
        assert bool(case["reference_answer"]) == (2 in case["grades"].values())
    timestamp = datetime.now(timezone.utc).isoformat()
    gold = {
        "schema_version": 1, "version": "general-association-21-v1",
        "status": "pre_run_locked_provisional_ai_reviewed_research_only",
        "locked_at_utc": timestamp, "human_review": {"reviewer": None, "status": "pending_later_validation"},
        "corpus_manifest_sha256": sha(corpus_path),
        "source_manifest_sha256": sha(Path(corpus["source_manifest"])),
        "input_sha256": {name: sha(DOCS / name) for name in names},
        "consolidation_rule": "Parent plus expansion; reconciliation overrides grade maps and explicit answers. GEN-01/ACE-01/ACE-02 use bounded independent answers. Other answers retain original bounded proposals, including full-text-informed BULLY-DIRECT-03. Historical NONE-ADHD ID is retained but now answerable.",
        "judgment_rule": expansion["judgment_rule"] + " Binary precision/recall/MRR use grade 2 only; nDCG uses gain 2^grade-1. No grade-2 cases are excluded from all five macro means and reported separately.",
        "predeclared_run": dict(parent["predeclared_run"], ranking="relevance_first"),
        "cases": list(cases.values()),
        "limitations": [
            "Provisional AI-reviewed research labels, not human-adjudicated or clinical approval.",
            "21-source abstract retrieval; full-text appraisal cautions do not make the indexed passages full text.",
            "Small reused set with paraphrases and multiple cases per source; no independent held-out generalization claim.",
            "19 answerable cases and one context-only negative cannot validate an abstention threshold.",
            "Diagnostic dense cosine >0.0 is not the runtime >0.85 gate; no threshold change is authorized.",
            "ACE source reports a combined psychiatric endpoint, not a separate substance estimate; perpetration, victimization, use and SUD must remain distinct."]}
    target = DOCS / "RAG_GENERAL_ASSOCIATION_GOLD_21_SOURCE.json"
    lock_path = target.with_suffix(".lock.json")
    if target.exists() or lock_path.exists():
        raise FileExistsError("Refusing to overwrite frozen research labels")
    with target.open("x") as stream:
        stream.write(json.dumps(gold, indent=2) + "\n")
    with lock_path.open("x") as stream:
        json.dump({"locked_at_utc": timestamp, "gold_file": target.name,
                   "gold_sha256": sha(target), "corpus_manifest_sha256": sha(corpus_path)}, stream, indent=2)
    print(target, sha(target))


if __name__ == "__main__":
    main()
