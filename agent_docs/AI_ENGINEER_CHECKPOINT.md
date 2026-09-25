# AI Engineer checkpoint: preflight and protected assessment graphs

Status: routing and protected assessment implementation slices, 2026-09-25. **Not an AI Engineer handoff or public runtime.**

The optional `.[ai]` dependency installs LangGraph. `src/clinical_risk_agent/ai/routing.py` implements a one-turn `StateGraph` that accepts a volatile `PreflightRequest` and returns a typed `RouteDecision`. It has no checkpointer, no public API, no generator, and no tool binding. The routing graph never grants inference, retrieval, or LLM permission; a route says which protected stage should be considered next.

`src/clinical_risk_agent/ai/assessment.py` implements that separate protected stage for structured assessments. Its entry point reruns routing preflight, checks a monotonic deadline, calls the ML-owned `validate_questionnaire`, and only for a complete valid version calls the ML-owned `predict_questionnaire` with the pinned positive and negative predictors. It does not recreate private option-to-feature mapping or generic-profile assembly. A second deterministic gate checks target identity, output name, artifact identity, one value per target, finite inclusive `[0,1]` values, and the approved generic-profile version before making separate one-decimal percentage displays. The raw `QuestionnaireAssessmentResult` remains in a protected internal outcome and is never a generated or public response here.

## Verified routing boundaries

- Only `prototype_demo` and a backend-asserted valid session may proceed; hospital mode fails closed.
- Safety interception precedes language and intent. A terminal safety decision ends the graph before either downstream classifier runs.
- Structured assessment skips free-text language/intent classification but still requires safety and assessment-view authorization. It routes to questionnaire **validation**, not inference.
- English free text alone reaches a calibrated intent decision. Confidence below `0.85` or explicit clarification routes to the fixed clarification stage. Conversational `risk_assessment` routes only to assessment redirection.
- External LangSmith tracing flags fail closed before the graph receives runtime text. The graph stores no checkpoint or user content and does not call a network provider.
- The assessment graph denies invalid session/mode/view, terminal safety, expired deadline, missing/invalid/unscored answers, and unsupported questionnaire version before inference. An invalid or unavailable inference returns no result/display. Non-finite or out-of-range output maps to the exact fixed internal-system-variance message, without exposing the raw value.

The safety, language, and intent ports are required injection points with no permissive defaults. Tests use synthetic fake decisions; no fine-tuned or calibrated classifier artifact is claimed. The graph's route output is deliberately not a substitute for authorization inside later assessment, retrieval, or generation nodes. Backend must derive session/view authorization, deadline, and request kind from protected transport state; none may be accepted from a client boolean. No public assessment endpoint is enabled.

Run `PYTHONPATH=src .venv/bin/python -m pytest tests/unit/test_ai_routing.py tests/unit/test_ai_assessment.py -q` for route/assessment fixtures and a real pinned-artifact integration case. The full unit suite remains the regression check. The present ML adapter raises a generic `ValueError` with a stable message for an out-of-range result; this graph maps that exact message to `INTERNAL_SYSTEM_VARIANCE`. A future ML-owned typed invalid-probability error would remove that brittle bridge without changing the safety behavior.

## Next AI Engineer work

1. Implement and independently evaluate the deterministic safety interceptor plus local classifier, English language gate, and fine-tuned/calibrated intent adapter. Until artifacts and release datasets exist, there is no production classifier route.
2. Add scientific retrieval only behind a trusted query-to-claim support contract. The current MCP search and arbitrary `EvidenceResult` matches are not verified claim support. A missing approved support gate must return a typed safe failure, not a scientific answer.
3. Add the structured-context builder, local generator port, draft schema, deterministic response validator, one bounded regeneration, and fixed fallbacks. No generated medical/scientific claim may reach the public response without current exact-passage support and citation validation.
4. Integrate an expiring memory-only checkpointer and cancellation/purge with Backend ownership, then benchmark graph paths, citation/score integrity, critical safety, cold/warm latency, and the 60-second terminal deadline before handoff.

Architecture decisions remain in [Approved AI Architecture](APPROVED_AI_ARCHITECTURE.md), and the downstream contract registry is [Interface Contracts](INTERFACE_CONTRACTS.md). Any change to intent values, gate policy, tool authority, or public schemas returns to the owning architect.
