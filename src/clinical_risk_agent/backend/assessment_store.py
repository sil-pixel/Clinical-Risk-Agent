"""Session-scoped, in-memory store for the latest validated assessment result."""

from __future__ import annotations

import hashlib
import threading
import time
from collections.abc import Callable
from typing import Any


class AssessmentResultStore:
    """Hold each session's latest assessment, keyed by a hash of its token, for one TTL."""

    def __init__(self, ttl_seconds: float, clock: Callable[[], float] = time.monotonic) -> None:
        """Configure the result lifetime and the monotonic clock used for expiry."""
        self._ttl = ttl_seconds
        self._clock = clock
        self._results: dict[str, tuple[float, dict[str, Any]]] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _key(token: str) -> str:
        """Derive an opaque key so raw session credentials are never stored."""
        return hashlib.sha256(token.encode()).hexdigest()

    def _prune(self) -> None:
        """Drop results older than the session lifetime; caller holds the lock."""
        cutoff = self._clock() - self._ttl
        for key, (created, _) in tuple(self._results.items()):
            if created < cutoff:
                del self._results[key]

    def put(self, token: str, result: dict[str, Any]) -> None:
        """Store a session's latest result, replacing any earlier one."""
        with self._lock:
            self._prune()
            self._results[self._key(token)] = (self._clock(), result)

    def get(self, token: str) -> dict[str, Any] | None:
        """Return the session's unexpired result object, shared for in-place updates."""
        with self._lock:
            self._prune()
            cached = self._results.get(self._key(token))
            return cached[1] if cached else None

    def ready_scores(self, token: str) -> dict[str, Any] | None:
        """Return a copy of the validated scores when the session has a ready result."""
        result = self.get(token)
        if result and result.get("status") == "assessment_ready":
            return dict(result["result"])
        return None

    def remove(self, token: str) -> None:
        """Forget a session's result, for example when the session is deleted."""
        with self._lock:
            self._results.pop(self._key(token), None)

    def clear(self) -> None:
        """Forget every stored result, used at application shutdown."""
        with self._lock:
            self._results.clear()
