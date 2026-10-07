"""Aggregate operational telemetry and versioned offline evaluation reports."""

from collections import deque
from datetime import datetime, timezone
import json
from pathlib import Path
import threading
import time

import numpy as np

from clinical_risk_agent.ai.routing import ROUTING_CONFIDENCE_THRESHOLD, suggestion
from clinical_risk_agent.drift import MIN_CURRENT_N, drift_report
from clinical_risk_agent.ood import score_submission

DRIFT_REFERENCE_PATH = Path("data/monitoring/drift_reference.json")


class Monitor:
    """Aggregate bounded in-memory operational and live-quality telemetry."""
    def __init__(self, root: Path):
        """Initialize bounded telemetry windows and synchronization for live monitoring."""
        self.root = root
        self.started = datetime.now(timezone.utc).isoformat()
        self._samples = deque(maxlen=2000)
        self._quality = deque(maxlen=2000)
        self._routing = deque(maxlen=2000)
        self._pending = 0
        self._lock = threading.Lock()
        # Cumulative per-category counts only; individual submissions are never retained.
        self._input_counts: dict[str, dict[str, int]] = {}
        self._input_n = 0
        self._ood_flags = {"surprise": 0, "mahalanobis": 0, "either": 0}
        try:
            self._drift_reference = json.loads((root / DRIFT_REFERENCE_PATH).read_text())
        except (OSError, ValueError):
            self._drift_reference = None
        self._ood_reference = (self._drift_reference or {}).get("ood")

    def record(self, operation: str, status: str, seconds: float):
        """Record an operation outcome and latency without retaining request content."""
        with self._lock:
            self._samples.append((operation, status, max(0, seconds), time.time()))

    def quality_started(self):
        """Increment the number of live answer evaluations in progress."""
        with self._lock:
            self._pending += 1

    def quality_finished(self, status: str, response_kind: str, verdict=None):
        # Explicit allowlist: never retain questions, answers, passages or tokens.
        """Record allowlisted live quality metadata and settle its pending count."""
        row = {"status": status, "response_kind": response_kind,
               "created_at": datetime.now(timezone.utc).isoformat()}
        if verdict:
            row.update({key: verdict.get(key) for key in
                        ("correctness", "groundedness", "judge_model", "judge_provider",
                         "quality_label", "rubric_version", "calibration_status")})
        with self._lock:
            if status != "skipped":
                self._pending = max(0, self._pending - 1)
            self._quality.append(row)

    def record_inputs(self, codes: dict[str, int]):
        """Add one submission's answer codes to aggregate drift and OOD counters."""
        # Scored then discarded: only the flag counts below are retained.
        ood = score_submission(codes, self._ood_reference) if self._ood_reference else None
        with self._lock:
            if ood:
                self._ood_flags["surprise"] += ood["surprise_ood"]
                self._ood_flags["mahalanobis"] += ood["mahalanobis_ood"]
                self._ood_flags["either"] += ood["surprise_ood"] or ood["mahalanobis_ood"]
            self._input_n += 1
            for name, code in codes.items():
                counts = self._input_counts.setdefault(name, {})
                counts[str(code)] = counts.get(str(code), 0) + 1

    def input_drift(self):
        """Compare live aggregate answer codes with the reference profile, if configured."""
        reference = self._drift_reference
        if reference is None:
            return {"status": "no_reference", "n": self._input_n}
        with self._lock:
            counts = {name: dict(values) for name, values in self._input_counts.items()}
            n = self._input_n
        report = drift_report(reference["counts"], counts, n)
        report["reference"] = {key: reference.get(key) for key in
                               ("dataset", "dataset_sha256", "n", "created_at")}
        return report

    def record_intent(self, decision):
        """Record allowlisted routing metadata for one free-text message; never its text."""
        routed = (not decision.requires_clarification
                  and decision.calibrated_confidence >= ROUTING_CONFIDENCE_THRESHOLD)
        source = ("confirmed" if decision.rationale_code == "user_confirmed_suggestion" else
                  "rule" if decision.model_id == "deterministic-prototype-rules" else "semantic")
        row = (decision.intent.value, routed, float(decision.calibrated_confidence), source,
               decision.rationale_code == "semantic_unfamiliar",
               not routed and suggestion(decision) is not None)
        with self._lock:
            self._routing.append(row)

    def live_routing(self):
        """Summarize live routing: clarification rate, decision source and routed intents."""
        with self._lock:
            rows = list(self._routing)
        if not rows:
            return {"n": 0}
        routed = [row for row in rows if row[1]]
        clarified = len(rows) - len(routed)
        suggested = sum(row[5] for row in rows)
        return {"n": len(rows), "threshold": ROUTING_CONFIDENCE_THRESHOLD,
                "clarification_rate": clarified / len(rows),
                # Share of clarifications that named a best guess instead of the generic menu.
                "suggestion_share": suggested / clarified if clarified else None,
                "confirmed_suggestions": sum(row[3] == "confirmed" for row in rows),
                "unfamiliar_rate": sum(row[4] for row in rows) / len(rows),
                "rule_share": sum(row[3] == "rule" for row in rows) / len(rows),
                "mean_confidence": sum(row[2] for row in rows) / len(rows),
                "routed_intents": {intent: sum(row[0] == intent for row in routed)
                                   for intent in sorted({row[0] for row in routed})}}

    def input_ood(self):
        """Report the share of live submissions flagged out of distribution."""
        reference = self._ood_reference
        with self._lock:
            n, flags = self._input_n, dict(self._ood_flags)
        if reference is None:
            return {"status": "no_reference", "n": n}
        if n < MIN_CURRENT_N:
            return {"status": "insufficient_data", "n": n, "min_n": MIN_CURRENT_N}
        return {"status": "scored", "n": n, "min_n": MIN_CURRENT_N,
                "expected_rate": round(1 - reference["quantile"], 6),
                "surprise_rate": flags["surprise"] / n,
                "mahalanobis_rate": flags["mahalanobis"] / n,
                "either_rate": flags["either"] / n}

    def snapshot(self):
        """Return aggregate operations, live quality scores and archived evaluation reports."""
        with self._lock:
            samples = list(self._samples)
            quality = list(self._quality)
            pending = self._pending
        def quality_mean(key):
            """Average available live scores and count the scored replies for one metric."""
            values = [row[key] for row in quality if row.get(key) is not None]
            return {"mean": sum(values) / len(values) if values else None, "n": len(values)}
        operations = []
        for operation in sorted({row[0] for row in samples}):
            rows = [row for row in samples if row[0] == operation]
            times = [row[2] * 1000 for row in rows]
            errors = sum(row[1] in {"error", "timeout", "unavailable", "GENERATION_UNAVAILABLE",
                                   "RETRIEVAL_UNAVAILABLE"} for row in rows)
            operations.append({
                "operation": operation, "count": len(rows), "errors": errors,
                "error_rate": errors / len(rows),
                "median_ms": float(np.median(times)),
                "p95_ms": float(np.percentile(times, 95)),
                "last_status": rows[-1][1],
            })
        reports = []
        for path in sorted((self.root / "data/evaluations").glob("*.json")):
            try:
                report = json.loads(path.read_text())
                if report.get("schema_version") == 1:
                    reports.append(report)
            except (ValueError, OSError):
                continue
        reports.sort(key=lambda item: item["created_at"], reverse=True)
        return {"started_at": self.started, "updated_at": datetime.now(timezone.utc).isoformat(),
                "window": "Most recent 2,000 operations since process start",
                "operations": operations, "reports": reports[:50],
                "input_drift": self.input_drift(), "input_ood": self.input_ood(),
                "live_routing": self.live_routing(),
                "live_quality": {"groundedness": quality_mean("groundedness"),
                                 "correctness": quality_mean("correctness"),
                                 "evaluated": sum(row["status"] == "scored" for row in quality),
                                 "errors": sum(row["status"] == "error" for row in quality),
                                 "skipped": sum(row["status"] == "skipped" for row in quality),
                                 "pending": pending, "recent": quality[-20:][::-1]}}
