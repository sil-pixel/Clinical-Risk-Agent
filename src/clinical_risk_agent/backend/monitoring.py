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
        self._lock = threading.Lock()

    def record(self, operation: str, status: str, seconds: float):
        with self._lock:
            self._samples.append((operation, status, max(0, seconds), time.time()))

    def snapshot(self):
        with self._lock:
            samples = list(self._samples)
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
                "operations": operations, "reports": reports[:50]}
