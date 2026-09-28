"""Aggregate operational telemetry and versioned offline evaluation reports."""

from collections import deque
from datetime import datetime, timezone
import json
from pathlib import Path
import threading
import time

import numpy as np


class Monitor:
    def __init__(self, root: Path):
        self.root = root
        self.started = datetime.now(timezone.utc).isoformat()
        self._samples = deque(maxlen=2000)
        self._quality = deque(maxlen=2000)
        self._pending = 0
        self._lock = threading.Lock()

    def record(self, operation: str, status: str, seconds: float):
        with self._lock:
            self._samples.append((operation, status, max(0, seconds), time.time()))

    def quality_started(self):
        with self._lock:
            self._pending += 1

    def quality_finished(self, status: str, response_kind: str, verdict=None):
        # Explicit allowlist: never retain questions, answers, passages or tokens.
        row = {"status": status, "response_kind": response_kind,
               "created_at": datetime.now(timezone.utc).isoformat()}
        if verdict:
            row.update({key: verdict.get(key) for key in
                        ("correctness", "groundedness", "judge_model", "judge_provider")})
        with self._lock:
            if status != "skipped":
                self._pending = max(0, self._pending - 1)
            self._quality.append(row)

    def snapshot(self):
        with self._lock:
            samples = list(self._samples)
            quality = list(self._quality)
            pending = self._pending
        def quality_mean(key):
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
                "live_quality": {"groundedness": quality_mean("groundedness"),
                                 "correctness": quality_mean("correctness"),
                                 "evaluated": sum(row["status"] == "scored" for row in quality),
                                 "errors": sum(row["status"] == "error" for row in quality),
                                 "skipped": sum(row["status"] == "skipped" for row in quality),
                                 "pending": pending, "recent": quality[-20:][::-1]}}
