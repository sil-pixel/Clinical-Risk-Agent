"""Signed opaque credentials with memory-only inactivity state and quotas."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


@dataclass(slots=True)
class SessionState:
    last_activity: float
    hourly_operations: deque[float]
    daily_operations: deque[float]
    state_version: int = 1


class SessionStore:
    """No persistence, cookies, identity, raw request text, or telemetry."""

    def __init__(self, key: bytes, *, ttl_seconds: int, max_sessions: int,
                 hourly_limit: int, daily_limit: int, global_daily_limit: int,
                 create_limit: int) -> None:
        self._key = key
        self._ttl = ttl_seconds
        self._max_sessions = max_sessions
        self._hourly_limit = hourly_limit
        self._daily_limit = daily_limit
        self._global_daily_limit = global_daily_limit
        self._create_limit = create_limit
        self._sessions: dict[str, SessionState] = {}
        self._creations: dict[str, deque[float]] = defaultdict(deque)
        self._global_operations: deque[float] = deque()
        self._lock = threading.Lock()

    def network_digest(self, value: str) -> str:
        return hmac.new(self._key, value.encode("utf-8"), hashlib.sha256).hexdigest()

    def _signature(self, session_id: str) -> str:
        return _b64(hmac.new(self._key, session_id.encode("ascii"), hashlib.sha256).digest())

    @staticmethod
    def _prune(values: deque[float], cutoff: float) -> None:
        while values and values[0] <= cutoff:
            values.popleft()

    def _prune_sessions(self, now: float) -> None:
        expired = [sid for sid, state in self._sessions.items()
                   if now - state.last_activity >= self._ttl]
        for sid in expired:
            del self._sessions[sid]

    def create(self, network_key: str, *, now: float | None = None) -> tuple[str, int]:
        now = time.monotonic() if now is None else now
        with self._lock:
            self._prune_sessions(now)
            for key, values in tuple(self._creations.items()):
                self._prune(values, now - 3600)
                if not values:
                    del self._creations[key]
            creations = self._creations[network_key]
            if len(creations) >= self._create_limit:
                raise PermissionError("session_creation_rate_limited")
            if len(self._sessions) >= self._max_sessions:
                raise OverflowError("session_capacity_exhausted")
            session_id = _b64(secrets.token_bytes(24))
            self._sessions[session_id] = SessionState(now, deque(), deque())
            creations.append(now)
        return f"{session_id}.{self._signature(session_id)}", self._ttl

    def _session_id(self, token: str) -> str:
        try:
            session_id, signature = token.split(".", 1)
        except ValueError as error:
            raise PermissionError("invalid_session") from error
        if not hmac.compare_digest(signature, self._signature(session_id)):
            raise PermissionError("invalid_session")
        return session_id

    def authorize(self, token: str, *, renew: bool = True,
                  now: float | None = None) -> SessionState:
        now = time.monotonic() if now is None else now
        session_id = self._session_id(token)
        with self._lock:
            state = self._sessions.get(session_id)
            if state is None or now - state.last_activity >= self._ttl:
                self._sessions.pop(session_id, None)
                raise PermissionError("expired_session")
            if renew:
                state.last_activity = now
                state.state_version += 1
            return state

    def consume_model_operation(self, token: str, *, now: float | None = None) -> SessionState:
        now = time.monotonic() if now is None else now
        session_id = self._session_id(token)
        with self._lock:
            state = self._sessions.get(session_id)
            if state is None or now - state.last_activity >= self._ttl:
                self._sessions.pop(session_id, None)
                raise PermissionError("expired_session")
            self._prune(state.hourly_operations, now - 3600)
            self._prune(state.daily_operations, now - 86400)
            self._prune(self._global_operations, now - 86400)
            if len(state.hourly_operations) >= self._hourly_limit:
                raise PermissionError("hourly_quota_exhausted")
            if len(state.daily_operations) >= self._daily_limit:
                raise PermissionError("daily_quota_exhausted")
            if len(self._global_operations) >= self._global_daily_limit:
                raise OverflowError("global_quota_exhausted")
            state.hourly_operations.append(now)
            state.daily_operations.append(now)
            self._global_operations.append(now)
            state.last_activity = now
            state.state_version += 1
            return state

    def delete(self, token: str) -> None:
        session_id = self._session_id(token)
        with self._lock:
            self._sessions.pop(session_id, None)
