# AI Engineer checkpoint: typed preflight graph

Status: first implementation slice, 2026-09-25. **Not an AI Engineer handoff or public runtime.**

The optional `.[ai]` dependency installs LangGraph. `src/clinical_risk_agent/ai/routing.py` implements a one-turn `StateGraph` that accepts a volatile `PreflightRequest` and returns a typed `RouteDecision`. It has no checkpointer, no public API, no generator, and no ML/RAG/MCP tool binding. The graph never grants inference, retrieval, or LLM permission; a route says which protected stage should be considered next.

## Verified routing boundaries

- Only `prototype_demo` and a backend-asserted valid session may proceed; hospital mode fails closed.
- Safety interception precedes language and intent. A terminal safety decision ends the graph before either downstream classifier runs.
- Structured assessment skips free-text language/intent classification but still requires safety and assessment-view authorization. It routes to questionnaire **validation**, not inference.
- English free text alone reaches a calibrated intent decision. Confidence below `0.85` or explicit clarification routes to the fixed clarification stage. Conversational `risk_assessment` routes only to assessment redirection.
- External LangSmith tracing flags fail closed before the graph receives runtime text. The graph stores no checkpoint or user content and does not call a network provider.

The safety, language, and intent ports are required injection points with no permissive defaults. Tests use synthetic fake decisions; no fine-tuned or calibrated classifier artifact is claimed. The graph's route output is deliberately not a substitute for authorization inside later assessment, retrieval, or generation nodes.

Run `PYTHONPATH=src .venv/bin/python -m pytest tests/unit/test_ai_routing.py -q` for the synthetic route fixtures. The full unit suite remains the regression check.

## Next AI Engineer work

1. Implement and independently evaluate the deterministic safety interceptor plus local classifier, English language gate, and fine-tuned/calibrated intent adapter. Until artifacts and release datasets exist, there is no production classifier route.
2. Add protected questionnaire validation and paired DCMFNet orchestration using the existing ML-owned adapter. Keep backend session/view/deadline authority outside the classifier; enforce exact target/value presentation and typed failures.
3. Add scientific retrieval only behind a trusted query-to-claim support contract. The current MCP search and arbitrary `EvidenceResult` matches are not verified claim support. A missing approved support gate must return a typed safe failure, not a scientific answer.
4. Add the structured-context builder, local generator port, draft schema, deterministic response validator, one bounded regeneration, and fixed fallbacks. No generated medical/scientific claim may reach the public response without current exact-passage support and citation validation.
5. Integrate an expiring memory-only checkpointer and cancellation/purge with Backend ownership, then benchmark graph paths, citation/score integrity, critical safety, cold/warm latency, and the 60-second terminal deadline before handoff.

Architecture decisions remain in [Approved AI Architecture](APPROVED_AI_ARCHITECTURE.md), and the downstream contract registry is [Interface Contracts](INTERFACE_CONTRACTS.md). Any change to intent values, gate policy, tool authority, or public schemas returns to the owning architect.
