import unittest

from clinical_risk_agent.ai.response_cache import CuratedAnswerCache, FixedReplyCache
from clinical_risk_agent.backend.assessment_store import AssessmentResultStore
from clinical_risk_agent.backend.capacity import CapacityGate
from clinical_risk_agent.backend.monitoring import GuardrailTracker, OperationsTracker


class Clock:
    """Manually advanced monotonic clock."""

    def __init__(self):
        """Start at time zero."""
        self.now = 0.0

    def __call__(self):
        """Return the current fake time."""
        return self.now


class AssessmentResultStoreTests(unittest.TestCase):
    """Check per-session storage, expiry and that raw tokens are never keys."""

    def test_put_get_ready_scores_and_expiry(self):
        """Verify results are per session, copied for scores, and expire after the TTL."""
        clock = Clock()
        store = AssessmentResultStore(ttl_seconds=10, clock=clock)
        store.put("token-a", {"status": "assessment_ready", "result": {"x": 1}})
        self.assertIsNone(store.get("token-b"))
        self.assertEqual(store.ready_scores("token-a"), {"x": 1})
        store.ready_scores("token-a")["x"] = 99
        self.assertEqual(store.get("token-a")["result"]["x"], 1)
        self.assertNotIn("token-a", repr(store.__dict__))
        clock.now = 11
        self.assertIsNone(store.get("token-a"))

    def test_only_ready_results_expose_scores_and_remove_clears(self):
        """Verify non-ready results give no scores and remove/clear forget sessions."""
        store = AssessmentResultStore(ttl_seconds=10)
        store.put("t", {"status": "questionnaire_invalid"})
        self.assertIsNone(store.ready_scores("t"))
        store.remove("t")
        self.assertIsNone(store.get("t"))
        store.put("u", {"status": "assessment_ready", "result": {}})
        store.clear()
        self.assertIsNone(store.get("u"))


class CacheTests(unittest.TestCase):
    """Check cache admission rules and LRU eviction."""

    def test_fixed_reply_cache_admits_only_fixed_replies(self):
        """Verify LLM or non-fixed replies are refused and the oldest entry is evicted."""
        cache = FixedReplyCache(size=2)
        key = FixedReplyCache.key("hi", deployment_mode="m", confirmed_intent=None)
        self.assertNotIn("hi", key)
        cache.put(key, {"response_kind": "CONVERSATION", "provider": "gemini"})
        self.assertIsNone(cache.get(key))
        for name in ("a", "b", "c"):
            cache.put(name, {"response_kind": "UNSUPPORTED", "provider": None})
        self.assertIsNone(cache.get("a"))
        self.assertTrue(cache.get("c")["cached"])

    def test_curated_cache_is_keyed_by_answer_and_citations(self):
        """Verify wording is reused only for the same answer and citation set."""
        cache = CuratedAnswerCache()
        cache.put("Answer [S1].", ["S1"], "Answer [S1].")
        self.assertEqual(cache.get("Answer [S1].", ["S1"]), "Answer [S1].")
        self.assertIsNone(cache.get("Answer [S1].", ["S2"]))


class TrackerAndGateTests(unittest.TestCase):
    """Check trackers and the capacity gate in isolation."""

    def test_trackers_are_independent(self):
        """Verify each tracker summarizes only its own records."""
        operations, guardrails = OperationsTracker(), GuardrailTracker()
        operations.record("chat", "error", 0.5)
        guardrails.record({"response_kind": "UNSUPPORTED"})
        guardrails.record({"response_kind": "CONVERSATION"})
        self.assertEqual(operations.summary()[0]["errors"], 1)
        self.assertEqual(guardrails.summary(), {"messages": 2, "outcomes": {"UNSUPPORTED": 1}})

    def test_capacity_gate_limits_and_releases(self):
        """Verify admission stops at the limit and resumes after release."""
        gate = CapacityGate(1)
        self.assertTrue(gate.acquire())
        self.assertFalse(gate.acquire())
        gate.release()
        self.assertTrue(gate.acquire())
