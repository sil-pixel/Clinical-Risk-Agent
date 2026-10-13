"""Non-blocking concurrency gate that bounds simultaneous model work."""

from __future__ import annotations

import threading


class CapacityGate:
    """Limit simultaneous operations with a thread-safe admission counter."""
    def __init__(self, limit: int) -> None:
        """Configure the concurrency limit and its thread-safe active counter."""
        self._limit = limit
        self._active = 0
        self._lock = threading.Lock()

    def acquire(self) -> bool:
        """Admit an operation if the concurrency limit has available capacity."""
        with self._lock:
            if self._active >= self._limit:
                return False
            self._active += 1
            return True

    def release(self) -> None:
        """Release a previously admitted operation from the concurrency counter."""
        with self._lock:
            self._active -= 1
