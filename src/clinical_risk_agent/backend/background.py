"""Fire-and-forget background work: assessment explanations and live answer judging."""

from __future__ import annotations

import asyncio
import time
from typing import Any

from .capacity import CapacityGate

JUDGED_KINDS = frozenset({"GROUNDED_ANSWER", "GENERAL_EDUCATION", "CONVERSATION"})
EXPLANATION_FAILURE = "Your scores are ready, but the explanation is temporarily unavailable."


class BackgroundJobs:
    """Run explanation and live-judge tasks with bounded concurrency and clean shutdown."""

    def __init__(self, conversation: Any, monitor: Any, *, timeout_seconds: float,
                 explanation_limit: int) -> None:
        """Bind the conversation service, telemetry facade and concurrency limits."""
        self._conversation = conversation
        self._monitor = monitor
        self._timeout = timeout_seconds
        self._explanation_slots = asyncio.Semaphore(explanation_limit)
        # One live evaluation at a time; extra replies are counted as skipped, not queued.
        self._judge_gate = CapacityGate(1)
        self._tasks: set[asyncio.Task] = set()

    def _spawn(self, coroutine) -> None:
        """Start a task and keep a reference until it finishes."""
        task = asyncio.create_task(coroutine)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    def explain(self, result: dict[str, Any]) -> None:
        """Mark a cached assessment result pending and explain it in the background."""
        result["explanation_status"] = "pending"
        result.pop("explanation", None)
        self._spawn(self._explain(result))

    async def _explain(self, result: dict[str, Any]) -> None:
        """Generate the explanation in place on the cached result, preserving the scores."""
        started = time.monotonic()

        async def generate():
            """Invoke the explainer within its concurrency limit."""
            async with self._explanation_slots:
                return await asyncio.to_thread(self._conversation.explain_assessment,
                                               dict(result["result"]))
        try:
            explanation = await asyncio.wait_for(generate(), timeout=self._timeout)
            result.update({
                "explanation": explanation["message"],
                "explanation_provider": explanation.get("provider"),
                "explanation_model": explanation.get("model"),
                "explanation_generated_by_llm": explanation.get("generated_by_llm", False),
                "explanation_status": ("ready" if explanation.get("generated_by_llm")
                                       else "unavailable"),
            })
            self._monitor.record("assessment_explanation", result["explanation_status"],
                                 time.monotonic() - started)
        except Exception:
            result["explanation_status"] = "unavailable"
            result["explanation"] = EXPLANATION_FAILURE
            self._monitor.record("assessment_explanation", "error", time.monotonic() - started)

    def judge(self, text: str, result: dict[str, Any]) -> None:
        """Schedule a live quality check for a generated reply, or count it as skipped."""
        if result.get("response_kind") not in JUDGED_KINDS:
            return
        evaluator = getattr(self._conversation, "evaluate_response", None)
        if evaluator is None or not result.get("model") or not self._judge_gate.acquire():
            self._monitor.quality_finished("skipped", result["response_kind"])
            return
        self._monitor.quality_started()
        self._spawn(self._judge(evaluator, text, result))

    async def _judge(self, evaluator, text: str, result: dict[str, Any]) -> None:
        """Judge one reply and retain only scores and safe operational metadata."""
        started = time.monotonic()
        try:
            verdict = await asyncio.to_thread(evaluator, text, result)
            self._monitor.quality_finished("scored", result["response_kind"], verdict)
            self._monitor.record("live_quality_judge", "scored", time.monotonic() - started)
        except Exception:
            self._monitor.quality_finished("error", result["response_kind"])
            self._monitor.record("live_quality_judge", "error", time.monotonic() - started)
        finally:
            self._judge_gate.release()

    async def shutdown(self) -> None:
        """Cancel outstanding tasks and wait for them to finish."""
        tasks = tuple(self._tasks)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
