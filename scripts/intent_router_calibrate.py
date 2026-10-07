"""Calibrate and evaluate the hybrid semantic intent router on held-out routing cases.

Fits the softmax temperature and similarity floor on the calibration split, then scores
the test split once against the rules-only router. No model weights are trained.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from clinical_risk_agent.ai import PrototypeIntentPort  # noqa: E402
from clinical_risk_agent.ai.routing import ROUTING_CONFIDENCE_THRESHOLD  # noqa: E402
from clinical_risk_agent.ai.semantic_router import (  # noqa: E402
    CALIBRATION_PATH,
    CERTAIN_RULES,
    UTTERANCES_PATH,
    SemanticIntentRouter,
    SentenceEncoder,
    sha256_text,
)

THRESHOLD = ROUTING_CONFIDENCE_THRESHOLD
RETRIEVAL = {"scientific_question", "mental_health_education"}
EVAL_PATH = ROOT / "agent_docs/INTENT_ROUTER_EVAL.json"


def route(intent):
    """Collapse intents that share a downstream route."""
    return "retrieval" if intent in RETRIEVAL else intent


def outcome(expected, intent, confidence, clarify):
    """Classify one decision as correct, clarified or misrouted at route level."""
    routed = not clarify and confidence >= THRESHOLD
    if expected is None:
        return "correct" if not routed else "misrouted"
    if not routed:
        return "clarified"
    return "correct" if route(intent) == route(expected) else "misrouted"


def summarize(rows):
    """Aggregate route-level outcomes and exact-intent accuracy for routed cases."""
    n = len(rows)
    counts = {key: sum(row["outcome"] == key for row in rows)
              for key in ("correct", "clarified", "misrouted")}
    routed = [row for row in rows if row["routed"] and row["expected"] is not None]
    return {"n": n, **{f"{key}_rate": value / n for key, value in counts.items()},
            "exact_intent_accuracy_when_routed":
                sum(row["intent"] == row["expected"] for row in routed) / len(routed)
                if routed else None}


def evaluate(cases, decide):
    """Run a decision function over cases and record route-level outcomes."""
    rows = []
    for case in cases:
        intent, confidence, clarify, source = decide(case)
        rows.append({"text": case["text"], "expected": case["intent"], "intent": intent,
                     "confidence": confidence, "source": source,
                     "routed": not clarify and confidence >= THRESHOLD,
                     "outcome": outcome(case["intent"], intent, confidence, clarify)})
    return rows


def main():
    """Run the command-line workflow: calibrate, evaluate and optionally save the router."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--pooling", choices=("mean", "cls"), required=True)
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--save", action="store_true",
                        help="write the calibration record used at runtime")
    args = parser.parse_args()

    model_dir = args.model_dir.resolve()
    weights_sha = hashlib.sha256((model_dir / "model.safetensors").read_bytes()).hexdigest()
    encoder = SentenceEncoder.from_local(model_dir, sha256=weights_sha, pooling=args.pooling)
    utterance_text = (ROOT / UTTERANCES_PATH).read_text(encoding="utf-8")
    utterances = json.loads(utterance_text)["intents"]
    router = SemanticIntentRouter(encoder, utterances, temperature=1.0, min_similarity=0.0,
                                  top_k=args.top_k)
    cases = json.loads(EVAL_PATH.read_text(encoding="utf-8"))["cases"]
    rules = PrototypeIntentPort()
    for case in cases:
        case["rule"] = rules.classify(case["text"])
    started = time.perf_counter()
    scores = router.similarities([case["text"] for case in cases])
    latency_ms = 1000 * (time.perf_counter() - started) / len(cases)
    for case, row in zip(cases, scores, strict=True):
        case["scores"] = row
    split = {name: [case for case in cases if case["split"] == name]
             for name in ("calibration", "test")}

    def hybrid(case):
        """Certain rule decisions first, otherwise the semantic decision."""
        rule = case["rule"]
        if rule.rationale_code in CERTAIN_RULES:
            return rule.intent.value, rule.calibrated_confidence, False, "rule"
        intent, confidence, clarify = router.decide(case["scores"])
        return intent.value, confidence, clarify, "semantic"

    def rules_only(case):
        """The current deterministic prototype router."""
        rule = case["rule"]
        return (rule.intent.value, rule.calibrated_confidence,
                rule.requires_clarification, "rule")

    # Temperature scaling: minimize log-loss on labeled calibration cases so the
    # reported confidence is a probability the graph's routing threshold can act on.
    labeled = [case for case in split["calibration"] if case["intent"] is not None]
    targets = np.array([[intent.value for intent in router.intents].index(case["intent"])
                        for case in labeled])
    matrix = np.stack([case["scores"] for case in labeled])

    def log_loss(temperature):
        """Mean negative log-probability of the expected intent at this temperature."""
        logits = matrix / temperature
        logits -= logits.max(axis=1, keepdims=True)
        log_probs = logits - np.log(np.exp(logits).sum(axis=1, keepdims=True))
        return -log_probs[np.arange(len(targets)), targets].mean()

    router.temperature = float(min(np.geomspace(0.001, 1.0, 200), key=log_loss))
    # The similarity floor is then tuned for routing outcomes; a misroute costs twice
    # a clarification because asking again is safer than a wrong path.
    best = None
    for floor in np.arange(0.0, 0.9, 0.01):
        router.min_similarity = float(floor)
        summary = summarize(evaluate(split["calibration"], hybrid))
        utility = summary["correct_rate"] - 2 * summary["misrouted_rate"]
        if best is None or utility > best[0] + 1e-12:
            best = (utility, float(floor))
    router.min_similarity = best[1]

    test_rows = evaluate(split["test"], hybrid)
    report = {
        "model": {"repo": args.repo, "revision": args.revision, "pooling": args.pooling,
                  "local_dir": str(model_dir.relative_to(ROOT)) if model_dir.is_relative_to(ROOT)
                  else str(model_dir), "model_safetensors_sha256": weights_sha},
        "settings": {"temperature": router.temperature, "min_similarity": router.min_similarity,
                     "top_k": args.top_k, "routing_threshold": THRESHOLD},
        "calibration": {"hybrid": summarize(evaluate(split["calibration"], hybrid)),
                        "rules_only": summarize(evaluate(split["calibration"], rules_only))},
        "test": {"hybrid": summarize(test_rows),
                 "rules_only": summarize(evaluate(split["test"], rules_only))},
        "mean_embedding_latency_ms_per_message": latency_ms,
        "test_errors": [row for row in test_rows if row["outcome"] != "correct"],
    }
    print(json.dumps({key: value for key, value in report.items() if key != "test_errors"},
                     indent=2))
    for row in report["test_errors"]:
        print(f"  {row['outcome']:9s} expected={row['expected']} got={row['intent']} "
              f"conf={row['confidence']:.2f} [{row['source']}] {row['text']}")
    if args.save:
        report.update(schema_version=1, created_at=datetime.now(timezone.utc).isoformat(),
                      calibration_version=f"intent-router-calibration-{datetime.now(timezone.utc):%Y%m%d}",
                      utterances_sha256=sha256_text(utterance_text),
                      eval_sha256=hashlib.sha256(EVAL_PATH.read_bytes()).hexdigest(),
                      eval_status=json.loads(EVAL_PATH.read_text(encoding="utf-8"))["status"],
                      utterances_status=json.loads(utterance_text)["status"])
        path = ROOT / CALIBRATION_PATH
        path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"Saved {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
