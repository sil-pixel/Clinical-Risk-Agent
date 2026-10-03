"""Prepare synthetic response review fixtures, run the separate judge and report agreement."""

import argparse
import hashlib
import json
from pathlib import Path

from clinical_risk_agent.ai.judge_agreement import agreement_report

ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / "agent_docs/LLM_JUDGE_REVIEW_100.json"


def case_hash(cases):
    """Hash immutable fixture content while excluding human and judge annotations."""
    fields = ("id", "query_id", "split", "question", "response", "reference_answer", "pmids")
    frozen = [{key: c[key] for key in fields} for c in cases]
    return hashlib.sha256(json.dumps(frozen, sort_keys=True).encode()).hexdigest()


def prepare():
    """Build five controlled quality variants for each of twenty frozen corpus questions."""
    gold = json.loads((ROOT / "agent_docs/RAG_GENERAL_ASSOCIATION_GOLD_21_SOURCE.json").read_text())
    cases = []
    for index, source in enumerate(gold["cases"]):
        reference = source["reference_answer"] or (
            "This corpus does not provide adequate direct evidence for bullying victimization "
            "and later diagnosed substance-use disorder. Use and experimentation outcomes "
            "cannot be substituted for a diagnosed disorder.")
        short = reference.split(". ")[0].split(";")[0].rstrip(".") + "."
        variants = [
            (reference, "good", "good", "Matches the bounded reference without adding claims."),
            (short, "acceptable", "acceptable", "Concise but may omit important study limits or distinctions."),
            (reference + " This proves a cause-and-effect relationship for every individual.",
             "bad", "bad", "Adds unsupported universal causation to an association or bounded finding."),
            ("The available papers do not let us calculate your personal risk from this association alone. "
             + short, "acceptable", "good", "Safe and informative but abbreviated; you may prefer its direct style."),
            ("There is no need to consider the research evidence. This answer applies equally to everyone "
             "and guarantees what will happen to you.", "bad", "bad",
             "Irrelevant, unsupported certainty and inappropriate individual extrapolation."),
        ]
        split = ("calibration" if index in {0, 2, 4, 5, 7, 8, 10, 11, 14, 16}
                 else "validation" if index in {1, 6, 9, 13, 17} else "holdout")
        for variant, (response, label, prediction, rationale) in enumerate(variants, 1):
            cases.append({"id": f"JUDGE-{len(cases) + 1:03d}", "query_id": source["id"],
                          "split": split, "question": source["query"], "response": response,
                          "reference_answer": reference,
                          "pmids": [p for p, grade in source["grades"].items() if grade == 2],
                          "assistant_annotation": label, "assistant_rationale": rationale,
                          "predicted_human_annotation": prediction,
                          "prediction_provenance": "AI guess of Silpa's preference, NOT a human label",
                          "human_annotation": None, "human_reviewed": False, "human_note": "",
                          "judge_annotation": None, "judge_status": "not_run"})
    if len(cases) != 100:
        raise ValueError("Expected exactly twenty questions and one hundred responses")
    if PACKET.exists():
        raise ValueError("Refusing to overwrite an existing review packet")
    packet = {"version": "bodhica-judge-review-v1", "rubric_version": "bodhica-quality-v1",
              "status": "prepared_not_calibrated", "reviewer": "Silpa",
              "response_provenance": "Assistant-authored synthetic controlled variants, NOT live chat logs",
              "reference_provenance": "Frozen provisional AI-reviewed corpus summaries, NOT independently verified gold",
              "source_gold_version": gold["version"],
              "corpus_manifest_sha256": gold["corpus_manifest_sha256"],
              "rubric": {"good": "Accurate, relevant and sufficiently complete; evidence claims stay bounded.",
                         "acceptable": "Useful and safe, with minor omissions or imprecision.",
                         "bad": "Material error, unsupported central claim, irrelevant answer or unsafe advice."},
              "case_sha256": case_hash(cases), "cases": cases}
    PACKET.write_text(json.dumps(packet, indent=2) + "\n")


def load_packet(path):
    """Validate immutable fixture content before accepting a reviewed or scored export."""
    packet = json.loads(path.read_text())
    original = json.loads(PACKET.read_text())
    if packet.get("case_sha256") != original["case_sha256"] or case_hash(packet["cases"]) != original["case_sha256"]:
        raise ValueError("Fixture hash mismatch; do not change questions, responses or splits")
    for case in packet["cases"]:
        if case.get("human_reviewed") is True and case.get("human_annotation") not in packet["rubric"]:
            raise ValueError("A confirmed review requires a valid human label")
    return packet


def score(packet, output, limit):
    """Score bounded synthetic fixtures through the configured separate provider model."""
    from clinical_risk_agent.ai import ProtectedConversationOrchestrator, create_generator
    from clinical_risk_agent.backend.settings import BackendSettings

    settings = BackendSettings.from_env(root=ROOT)
    generator = create_generator(settings.llm_provider, settings.llm_api_key,
                                 settings.llm_judge_model or settings.llm_model)
    service = ProtectedConversationOrchestrator(None, None, generator)
    attempted = 0
    try:
        for case in packet["cases"]:
            if case.get("judge_status") == "scored":
                continue
            if attempted >= limit:
                break
            attempted += 1
            try:
                # Summaries are a reference proxy, explicitly not verbatim full-text evidence.
                verdict = service.evaluate_response(case["question"], {
                    "message": case["response"], "citations": [{"citation_id": "reference-summary",
                    "exact_matched_text": "Provisional reference summary (not a source quotation): "
                                          + case["reference_answer"]}]})
                if verdict["quality_label"] not in packet["rubric"]:
                    raise ValueError("Missing ordinal judge label")
                case.update(judge_annotation=verdict["quality_label"], judge_status="scored", judge_verdict=verdict)
            except Exception as error:
                case.update(judge_annotation=None, judge_status="error", judge_error_type=type(error).__name__)
            output.write_text(json.dumps(packet, indent=2) + "\n")
    finally:
        service.close()


def main():
    """Prepare fixtures or calculate reviewed agreement without inventing human labels."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "score", "report"))
    parser.add_argument("--input", type=Path, default=PACKET)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()
    if args.action == "prepare":
        prepare()
        print(f"Prepared {PACKET}")
        return
    packet = load_packet(args.input)
    if args.action == "score":
        if not 1 <= args.limit <= 100 or args.output is None or args.output.resolve() == PACKET.resolve():
            parser.error("score requires --output (not the frozen packet) and --limit 1..100")
        score(packet, args.output, args.limit)
    else:
        print(json.dumps(agreement_report(packet["cases"]), indent=2))


if __name__ == "__main__":
    main()
