"""Validate a completed independent first-pass gold-review worksheet."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path


def validate(path: Path, packet_path: Path) -> list[str]:
    review = json.loads(path.read_text(encoding="utf-8"))
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    problems: list[str] = []
    if not isinstance(review.get("reviewer"), str) or not review["reviewer"].strip():
        problems.append("reviewer identity is missing")
    try:
        reviewed_on = date.fromisoformat(review["reviewed_on"])
        if reviewed_on > date.today():
            problems.append("review date is in the future")
    except (KeyError, TypeError, ValueError):
        problems.append("reviewed_on must be an ISO date")
    expected_ids = [case["id"] for case in packet["cases"]]
    cases = review.get("cases")
    if not isinstance(cases, list) or [case.get("id") for case in cases] != expected_ids:
        return problems + ["case IDs/order differ from the blinded packet"]
    source_ids = {source["pmid"] for source in packet["sources"]}
    if set(review.get("source_universe", [])) != source_ids:
        problems.append("source universe differs from the blinded packet")
    if review.get("corpus_manifest_sha256") != packet["corpus_manifest_sha256"]:
        problems.append("corpus manifest hash differs from the blinded packet")
    for case in cases:
        label = case["id"]
        grades = case.get("grades")
        spans = case.get("evidence_spans")
        answer = case.get("reference_answer")
        if not isinstance(grades, dict):
            problems.append(f"{label}: grades must be a PMID-to-grade object")
            continue
        if set(grades) - source_ids:
            problems.append(f"{label}: unknown PMID in grades")
        if any(type(grade) is not int or grade not in (1, 2) for grade in grades.values()):
            problems.append(f"{label}: listed grades must be integer 1 or 2; omit grade 0")
        if not isinstance(spans, dict) or any(
            not isinstance(spans.get(pmid), str) or not spans[pmid].strip()
            for pmid in grades
        ):
            problems.append(f"{label}: evidence_spans must explain each nonzero grade")
        has_direct = 2 in grades.values()
        if has_direct and (not isinstance(answer, str) or not answer.strip()):
            problems.append(f"{label}: a grade-2 case needs a bounded reference answer")
        if not has_direct and answer is not None:
            problems.append(f"{label}: no grade-2 source requires null reference_answer")
    return problems


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("worksheet", type=Path)
    parser.add_argument(
        "--packet", type=Path,
        default=Path(__file__).resolve().parents[1]
        / "agent_docs/RAG_GOLD_21_SOURCE_BLINDED_PACKET.json",
    )
    args = parser.parse_args()
    problems = validate(args.worksheet, args.packet)
    if problems:
        raise SystemExit("Review incomplete:\n- " + "\n- ".join(problems))
    print("Independent first-pass worksheet is structurally complete")


if __name__ == "__main__":
    main()
