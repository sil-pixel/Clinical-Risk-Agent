# AI Engineer checkpoint: preflight and protected assessment graphs

Status: routing, protected assessment, and bounded conversational-RAG implementation slices, updated 2026-09-27. **Functional prototype; not a production/clinical release handoff.**

The completed five-claim RAG baseline is integrated behind a FastAPI boundary with signed memory-only sessions, opaque public question IDs, and `POST /v1/messages`. The JSON chat route runs the protected preflight graph and permits generation only after exact trusted claim routing and claim-supported retrieval. It validates exact approved prose and citation membership before returning any generated result. SSE and public questionnaire submission remain closed. See [Backend deployment handoff](BACKEND_DEPLOYMENT_HANDOFF.md).

Product clarification (2026-09-27): the target presentation is chat-first, with the questionnaire available as an optional left-side assessment workflow. Root `.env`/Modal configuration selects an explicit provider and model through `LLM_PROVIDER` and `LLM_MODEL`; structured-output adapters exist for the official OpenAI, Anthropic, and Google Gen AI SDKs, using the backend-only `LLM_API_KEY`. Enabling external generation changes the earlier local-model/zero-external-payload assumption and therefore still requires the conversational privacy, safety, and response-validation boundary to be updated before arbitrary messages are sent.

The optional `.[ai]` dependency installs LangGraph. `src/clinical_risk_agent/ai/routing.py` implements a one-turn `StateGraph` that accepts a volatile `PreflightRequest` and returns a typed `RouteDecision`. It has no checkpointer, no public API, no generator, and no tool binding. The routing graph never grants inference, retrieval, or LLM permission; a route says which protected stage should be considered next.

`src/clinical_risk_agent/ai/assessment.py` implements that separate protected stage for structured assessments. Its entry point reruns routing preflight, checks a monotonic deadline, calls the ML-owned `validate_questionnaire`, and only for a complete valid version calls the ML-owned `predict_questionnaire` with the pinned positive and negative predictors. It does not recreate private option-to-feature mapping or generic-profile assembly. A second deterministic gate checks target identity, output name, artifact identity, one value per target, finite inclusive `[0,1]` values, and the approved generic-profile version before making separate one-decimal percentage displays. The raw `QuestionnaireAssessmentResult` remains in a protected internal outcome and is never a generated or public response here.

## Verified routing boundaries

- Only `prototype_demo` and a backend-asserted valid session may proceed; hospital mode fails closed.
- Safety interception precedes language and intent. A terminal safety decision ends the graph before either downstream classifier runs.
- Structured assessment skips free-text language/intent classification but still requires safety and assessment-view authorization. It routes to questionnaire **validation**, not inference.
- English free text alone reaches a calibrated intent decision. Confidence below `0.85` or explicit clarification routes to the fixed clarification stage. Conversational `risk_assessment` routes only to assessment redirection.
- External LangSmith tracing flags fail closed before the graph receives runtime text. The graph stores no checkpoint or user content and does not call a network provider.
- The assessment graph denies invalid session/mode/view, terminal safety, expired deadline, missing/invalid/unscored answers, and unsupported questionnaire version before inference. An invalid or unavailable inference returns no result/display. Non-finite or out-of-range output maps to the exact fixed internal-system-variance message, without exposing the raw value.

The public composition uses conservative deterministic prototype safety, language, and intent ports so the bounded demo is functional without unavailable classifier artifacts. They are explicitly not fine-tuned, calibrated, or release-approved. The graph's route output is not treated as tool authorization: the conversational orchestrator separately requires trusted exact claim mapping and verified retrieval before generation. Backend derives session authorization, deadline, and request kind from protected transport state; none may be accepted from a client boolean. No public assessment endpoint is enabled.

Run `PYTHONPATH=src .venv/bin/python -m pytest tests/unit/test_ai_routing.py tests/unit/test_ai_assessment.py -q` for route/assessment fixtures and a real pinned-artifact integration case. The full unit suite remains the regression check. The present ML adapter raises a generic `ValueError` with a stable message for an out-of-range result; this graph maps that exact message to `INTERNAL_SYSTEM_VARIANCE`. A future ML-owned typed invalid-probability error would remove that brittle bridge without changing the safety behavior.

## Next AI Engineer work

1. Independently evaluate the prototype safety and language rules, then replace or augment them with pinned local classifier artifacts. Fine-tune/calibrate the intent adapter and run the frozen release datasets before production use.
2. Expand trusted query-to-claim routing beyond the five exact reviewed questions only after each mapping has reviewed support judgments. Arbitrary retrieval matches and MCP search results cannot authorize generated claims.
3. Add validated SSE delivery and cancellation without exposing raw provider tokens. Keep the existing structured context, exact response/citation validator, bounded regeneration, and typed fallbacks as the non-streaming reference path.
4. Integrate an expiring memory-only checkpointer and cancellation/purge with Backend ownership, then benchmark graph paths, citation/score integrity, critical safety, cold/warm latency, and the 60-second terminal deadline before handoff.

Architecture decisions remain in [Approved AI Architecture](APPROVED_AI_ARCHITECTURE.md), and the downstream contract registry is [Interface Contracts](INTERFACE_CONTRACTS.md). Any change to intent values, gate policy, tool authority, or public schemas returns to the owning architect.
