"""In-process caches for replies that cannot change for identical input."""

from __future__ import annotations

import hashlib
import threading
from collections import OrderedDict
from typing import Any

from .routing import SafetyCategory

# Replies built only from fixed text: identical input always yields the same reply.
FIXED_RESPONSE_KINDS = frozenset(
    {category.value for category in SafetyCategory} - {"ALLOW_NORMAL_PROCESSING"}
) | {"LANGUAGE_UNSUPPORTED", "INTENT_CLARIFICATION_REQUIRED", "ASSESSMENT_REDIRECTION",
     "UNSUPPORTED"}
RESPONSE_CACHE_SIZE = 2048


class FixedReplyCache:
    """LRU cache of fixed replies keyed by a SHA-256 digest of the message, never its text."""

    def __init__(self, size: int = RESPONSE_CACHE_SIZE) -> None:
        """Create an empty cache holding at most size replies."""
        self._size = size
        self._replies: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._lock = threading.Lock()

    @staticmethod
    def key(text: str, *, deployment_mode: str, confirmed_intent: str | None) -> str:
        """Digest everything that determines a fixed reply into an opaque key."""
        return hashlib.sha256(
            f"{deployment_mode}|{confirmed_intent or ''}|{text.strip()}".encode()
        ).hexdigest()

    def get(self, key: str) -> dict[str, Any] | None:
        """Return a copy of a cached reply marked as cached, or None on a miss."""
        with self._lock:
            reply = self._replies.get(key)
            if reply is None:
                return None
            self._replies.move_to_end(key)
            return {**reply, "cached": True}

    def put(self, key: str, reply: dict[str, Any]) -> None:
        """Store a reply only if it is fixed text that no LLM produced."""
        if reply.get("provider") is not None or reply["response_kind"] not in FIXED_RESPONSE_KINDS:
            return
        with self._lock:
            self._replies[key] = reply
            if len(self._replies) > self._size:
                self._replies.popitem(last=False)


class CuratedAnswerCache:
    """Verified curated wording keyed by approved answer and citation IDs."""

    def __init__(self) -> None:
        """Create an empty cache."""
        self._answers: dict[tuple[str, tuple[str, ...]], str] = {}
        self._lock = threading.Lock()

    def get(self, answer: str, citation_ids: list[str]) -> str | None:
        """Return previously verified wording for this answer and citation set, if any."""
        with self._lock:
            return self._answers.get((answer, tuple(citation_ids)))

    def put(self, answer: str, citation_ids: list[str], text: str) -> None:
        """Remember wording that already passed exact-match validation."""
        with self._lock:
            self._answers[(answer, tuple(citation_ids))] = text
