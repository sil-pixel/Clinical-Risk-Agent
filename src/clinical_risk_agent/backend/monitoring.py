"""Aggregate operational telemetry and versioned offline evaluation reports.

Each tracker owns one kind of telemetry and its own lock (single responsibility).
`Monitor` is a facade that keeps the public API used by the HTTP layer and dashboard.
No tracker retains message text, questionnaire answers or session identifiers.
"""

from collections import deque
from datetime import datetime, timezone
import json
from pathlib import Path
import threading
import time

import numpy as np

from clinical_risk_agent.ai.routing import ROUTING_CONFIDENCE_THRESHOLD, SafetyCategory, suggestion
from clinical_risk_agent.drift import drift_report
from clinical_risk_agent.ood import OOD_MIN_N, score_submission

DRIFT_REFERENCE_PATH = Path("data/monitoring/drift_reference.json")
WINDOW = 2000
ERROR_STATUSES = {"error", "timeout", "unavailable", "GENERATION_UNAVAILABLE",
                  "RETRIEVAL_UNAVAILABLE"}
QUALITY_FIELDS = ("correctness", "groundedness", "judge_model", "judge_provider",
                  "quality_label", "rubric_version", "calibration_status")


def _now() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


class OperationsTracker:
    """Bounded window of operation outcomes and latencies for the operations table."""

    def __init__(self) -> None:
        """Start an empty bounded sample window."""
        self._samples = deque(maxlen=WINDOW)
        self._lock = threading.Lock()

    def record(self, operation: str, status: str, seconds: float) -> None:
        """Record one operation's outcome and latency without request content."""
        with self._lock:
            self._samples.append((operation, status, max(0, seconds), time.time()))

    def summary(self) -> list[dict]:
        """Return count, error rate, median and p95 latency per operation."""
        with self._lock:
            samples = list(self._samples)
        operations = []
        for operation in sorted({row[0] for row in samples}):
            rows = [row for row in samples if row[0] == operation]
            times = [row[2] * 1000 for row in rows]
            errors = sum(row[1] in ERROR_STATUSES for row in rows)
            operations.append({
                "operation": operation, "count": len(rows), "errors": errors,
                "error_rate": errors / len(rows),
                "median_ms": float(np.median(times)), "p95_ms": float(np.percentile(times, 95)),
                "last_status": rows[-1][1],
            })
        return operations


class QualityTracker:
    """Bounded window of live LLM-judge scores plus the pending evaluation count."""

    def __init__(self) -> None:
        """Start an empty score window with no pending evaluations."""
        self._rows = deque(maxlen=WINDOW)
        self._pending = 0
        self._lock = threading.Lock()

    def started(self) -> None:
        """Count one live evaluation as in progress."""
        with self._lock:
            self._pending += 1

    def finished(self, status: str, response_kind: str, verdict=None) -> None:
        """Record allowlisted verdict fields and settle the pending count."""
        row = {"status": status, "response_kind": response_kind, "created_at": _now()}
        if verdict:
            # Explicit allowlist: never retain questions, answers, passages or tokens.
            row.update({key: verdict.get(key) for key in QUALITY_FIELDS})
        with self._lock:
            if status != "skipped":
                self._pending = max(0, self._pending - 1)
            self._rows.append(row)

    def summary(self) -> dict:
        """Return mean scores, outcome counts, pending count and the latest 20 records."""
        with self._lock:
            rows, pending = list(self._rows), self._pending

        def mean(key):
            """Average one available score and count how many replies it covers."""
            values = [row[key] for row in rows if row.get(key) is not None]
            return {"mean": sum(values) / len(values) if values else None, "n": len(values)}

        return {"groundedness": mean("groundedness"), "correctness": mean("correctness"),
                "evaluated": sum(row["status"] == "scored" for row in rows),
                "errors": sum(row["status"] == "error" for row in rows),
                "skipped": sum(row["status"] == "skipped" for row in rows),
                "pending": pending, "recent": rows[-20:][::-1]}


class InputTracker:
    """Aggregate questionnaire answer counts for drift and OOD flag counts."""

    def __init__(self, reference: dict | None) -> None:
        """Bind the drift/OOD reference profile, if one has been built."""
        self._reference = reference
        self._ood_reference = (reference or {}).get("ood")
        # Cumulative per-category counts only; individual submissions are never retained.
        self._counts: dict[str, dict[str, int]] = {}
        self._n = 0
        self._surprise_sum = 0.0
        self._flags = {"surprise": 0, "mahalanobis": 0, "either": 0}
        self._lock = threading.Lock()

    def record(self, codes: dict[str, int]) -> None:
        """Score one submission for OOD, add its codes to the counts, then discard it."""
        ood = score_submission(codes, self._ood_reference) if self._ood_reference else None
        with self._lock:
            if ood:
                self._surprise_sum += ood["surprise"]
                self._flags["surprise"] += ood["surprise_ood"]
                self._flags["mahalanobis"] += ood["mahalanobis_ood"]
                self._flags["either"] += ood["surprise_ood"] or ood["mahalanobis_ood"]
            self._n += 1
            for name, code in codes.items():
                counts = self._counts.setdefault(name, {})
                counts[str(code)] = counts.get(str(code), 0) + 1

    def drift(self) -> dict:
        """Return the drift report against the reference profile, if configured."""
        if self._reference is None:
            return {"status": "no_reference", "n": self._n}
        with self._lock:
            counts = {name: dict(values) for name, values in self._counts.items()}
            n, surprise_sum = self._n, self._surprise_sum
        ood = self._ood_reference or {}
        report = drift_report(self._reference["counts"], counts, n,
                              surprise_sum=surprise_sum if ood else None,
                              surprise_mean=ood.get("surprise_mean"),
                              surprise_std=ood.get("surprise_std"))
        report["reference"] = {key: self._reference.get(key) for key in
                               ("dataset", "dataset_sha256", "n", "created_at")}
        return report

    def ood(self) -> dict:
        """Return the share of submissions flagged out of distribution."""
        with self._lock:
            n, flags = self._n, dict(self._flags)
        if self._ood_reference is None:
            return {"status": "no_reference", "n": n}
        if n < OOD_MIN_N:
            return {"status": "insufficient_data", "n": n, "min_n": OOD_MIN_N}
        return {"status": "scored", "n": n, "min_n": OOD_MIN_N,
                "expected_rate": round(1 - self._ood_reference["quantile"], 6),
                "surprise_rate": flags["surprise"] / n,
                "mahalanobis_rate": flags["mahalanobis"] / n,
                "either_rate": flags["either"] / n}


class RoutingTracker:
    """Bounded window of allowlisted intent decisions for the live routing panel."""

    def __init__(self) -> None:
        """Start an empty decision window."""
        self._rows = deque(maxlen=WINDOW)
        self._lock = threading.Lock()

    def record(self, decision) -> None:
        """Record intent, routed flag, confidence and decision source; never text."""
        routed = (not decision.requires_clarification
                  and decision.calibrated_confidence >= ROUTING_CONFIDENCE_THRESHOLD)
        source = ("confirmed" if decision.rationale_code == "user_confirmed_suggestion" else
                  "prompt_guard" if decision.rationale_code == "prompt_injection" else
                  "rule" if decision.model_id.startswith("deterministic-") else "semantic")
        row = (decision.intent.value, routed, float(decision.calibrated_confidence), source,
               decision.rationale_code == "semantic_unfamiliar",
               not routed and suggestion(decision) is not None)
        with self._lock:
            self._rows.append(row)

    def summary(self) -> dict:
        """Return clarification rate, decision sources, confidence and routed intents."""
        with self._lock:
            rows = list(self._rows)
        if not rows:
            return {"n": 0}
        routed = [row for row in rows if row[1]]
        clarified = len(rows) - len(routed)
        return {"n": len(rows), "threshold": ROUTING_CONFIDENCE_THRESHOLD,
                "clarification_rate": clarified / len(rows),
                # Share of clarifications that named a best guess instead of the generic menu.
                "suggestion_share": (sum(row[5] for row in rows) / clarified
                                     if clarified else None),
                "confirmed_suggestions": sum(row[3] == "confirmed" for row in rows),
                "prompt_guard_blocked": sum(row[3] == "prompt_guard" for row in rows),
                "unfamiliar_rate": sum(row[4] for row in rows) / len(rows),
                "rule_share": sum(row[3] == "rule" for row in rows) / len(rows),
                "mean_confidence": sum(row[2] for row in rows) / len(rows),
                "routed_intents": {intent: sum(row[0] == intent for row in routed)
                                   for intent in sorted({row[0] for row in routed})}}


class GuardrailTracker:
    """Counts of refusal and redirection outcomes since process start."""

    GUARDED = ({category.value for category in SafetyCategory}
               - {"ALLOW_NORMAL_PROCESSING"}) | {"UNSUPPORTED"}

    def __init__(self) -> None:
        """Start with no recorded replies."""
        self._messages = 0
        self._outcomes: dict[str, int] = {}
        self._lock = threading.Lock()

    def record(self, result: dict) -> None:
        """Count one chat reply and its guardrail outcome, if it was refused or redirected."""
        kind = result.get("response_kind")
        with self._lock:
            self._messages += 1
            if kind in self.GUARDED:
                self._outcomes[kind] = self._outcomes.get(kind, 0) + 1

    def summary(self) -> dict:
        """Return reply and outcome counts."""
        with self._lock:
            return {"messages": self._messages, "outcomes": dict(self._outcomes)}


class ReportStore:
    """Read-only access to versioned offline evaluation reports on disk."""

    def __init__(self, directory: Path) -> None:
        """Bind the directory that holds evaluation report JSON files."""
        self._directory = directory

    def latest(self, limit: int = 50) -> list[dict]:
        """Return up to limit schema-v1 reports, newest first, skipping unreadable files."""
        reports = []
        for path in sorted(self._directory.glob("*.json")):
            try:
                report = json.loads(path.read_text())
            except (ValueError, OSError):
                continue
            if report.get("schema_version") == 1:
                reports.append(report)
        reports.sort(key=lambda item: item["created_at"], reverse=True)
        return reports[:limit]


def _load_reference(root: Path) -> dict | None:
    """Load the drift/OOD reference profile, or None when it has not been built."""
    try:
        return json.loads((root / DRIFT_REFERENCE_PATH).read_text())
    except (OSError, ValueError):
        return None


class Monitor:
    """Facade over the telemetry trackers that keeps the HTTP layer's monitoring API."""

    def __init__(self, root: Path):
        """Create one tracker per telemetry concern for this application root."""
        self.root = root
        self.started = _now()
        self.operations = OperationsTracker()
        self.quality = QualityTracker()
        self.inputs = InputTracker(_load_reference(root))
        self.routing = RoutingTracker()
        self.guardrails = GuardrailTracker()
        self.reports = ReportStore(root / "data/evaluations")

    def record(self, operation: str, status: str, seconds: float):
        """Record an operation outcome and latency without retaining request content."""
        self.operations.record(operation, status, seconds)

    def quality_started(self):
        """Increment the number of live answer evaluations in progress."""
        self.quality.started()

    def quality_finished(self, status: str, response_kind: str, verdict=None):
        """Record allowlisted live quality metadata and settle its pending count."""
        self.quality.finished(status, response_kind, verdict)

    def record_inputs(self, codes: dict[str, int]):
        """Add one submission's answer codes to aggregate drift and OOD counters."""
        self.inputs.record(codes)

    def record_intent(self, decision):
        """Record allowlisted routing metadata for one free-text message; never its text."""
        self.routing.record(decision)

    def record_guardrails(self, result):
        """Count the guardrail outcome of one chat reply; no text."""
        self.guardrails.record(result)

    def input_drift(self):
        """Compare live aggregate answer codes with the reference profile, if configured."""
        return self.inputs.drift()

    def input_ood(self):
        """Report the share of live submissions flagged out of distribution."""
        return self.inputs.ood()

    def live_routing(self):
        """Summarize live routing: clarification rate, decision source and routed intents."""
        return self.routing.summary()

    def live_guardrails(self):
        """Return guardrail counts since process start."""
        return self.guardrails.summary()

    def snapshot(self):
        """Return aggregate operations, live quality, ML input monitoring and reports."""
        return {"started_at": self.started, "updated_at": _now(),
                "window": "Most recent 2,000 operations since process start",
                "operations": self.operations.summary(), "reports": self.reports.latest(),
                "input_drift": self.input_drift(), "input_ood": self.input_ood(),
                "live_routing": self.live_routing(), "live_guardrails": self.live_guardrails(),
                "live_quality": self.quality.summary()}
