# AI Architecture Implementation Handoffs

Status: Approved implementation handoff; release remains gated by measured evidence

Date: 2026-09-17

Canonical architecture: [`APPROVED_AI_ARCHITECTURE.md`](APPROVED_AI_ARCHITECTURE.md)

## RAG Engineer

- Ingest PubMed abstracts and only explicitly licensed eligible full text within the approved mental-health topic scope. Record DOI/PMID, license, publication date, evidence tier, appraisal, and current retraction status.
- Implement section-aware parent/child chunking, MedCPT and comparison embeddings, dense plus BM25 retrieval, RRF, MedCPT comparison reranking, the independent lexical fallback, and one bounded live PubMed escalation.
- Use Qdrant only for the versioned public scientific corpus. Persist the corpus snapshot and independent BM25 index as non-user artifacts; never persist runtime query or assessment data.
- Implement the `RetrievalQuery`, `EvidenceResult`, and `EvidenceDisplayRecord` semantics in the interface registry, including conflict representation, source cap, and typed no-evidence/unavailable states.
- Execute the retrieval and resource sections of [`AI_MODEL_BENCHMARK_REPORT.md`](AI_MODEL_BENCHMARK_REPORT.md). Return threshold or feasibility changes to the AI Architect; do not silently tune the `0.85` gate.

## AI Engineer

- Implement the fixed LangGraph nodes and routes defined in the approved architecture: transport validation, safety, language, intent, assessment validation, inference authorization, retrieval, context construction, generation, response validation, and terminal presentation.
- Bind DCMFNet only to complete structured assessment submissions. Chat assessment intent returns redirection; explanation uses an immutable existing result and cannot rerun inference.
- Implement provider-neutral adapters for the CPU generator, fastText language gate, fine-tuned intent classifier, and fine-tuned safety classifier. Models emit typed decisions or structured drafts, never tool authority.
- Build prompts from validated purpose, immutable result values, eligible evidence, and approved limitations only. Enforce claim-level citations and one bounded regeneration.
- Implement deterministic fakes before downloading production candidates. Execute generator, language, intent, safety, BERTScore, cold-start, and latency benchmarks before requesting artifact approval.

## Backend Engineer

- Expose anonymous signed ephemeral sessions with narrow CORS, `Cache-Control: no-store`, request-size limits, validated JSON/SSE, disconnect cancellation, and no persistent replay.
- Enforce 50 simultaneous HTTP requests, initially eight CPU-heavy model jobs, 10 model-backed turns/hour/session, 25/day/session, three assessment submissions/day/session, five session creations/hour/transient network key, and a global 1,000 model-backed-operation daily ceiling.
- Keep rate-limit digests one-way and volatile. Never emit session, network, query, questionnaire, result, probability, or evidence content to telemetry.
- Integrate Modal CPU-only deployment with zero minimum containers, `$0` out-of-pocket spend limit, available-credit usage budget, and the fixed budget-exhaustion response.
- Preserve the 60-second accepted-request terminal-state deadline and typed capacity, quota, dependency, and budget errors.
- Implement aggregate monitoring for end-to-end and stage-level p50/p95/p99/maximum latency, cold starts, queue wait, both DCMFNet calls, timeouts, disconnects, `429`, quota, capacity, budget, `503`, typed component failures, retries, concurrency, CPU, memory, containers, and restarts. Keep rejection and inference-failure denominators separate.
- Emit only bounded version and typed status/error dimensions. Do not persist per-request telemetry rows, raw predictions, prediction intervals, session/network identifiers, or user-bearing timing traces.

## Frontend Engineer

- Render the 85 visible required controls from [`questionnaire.md`](../questionnaire.md); never expose the 20 generic-profile fields as editable controls.
- Treat `I do not remember` as non-scored and submission-blocking. Disable submission until every visible field is locally valid, while showing an accessible missing/invalid summary; backend validation remains authoritative.
- Disclose the generic unmeasured genetic profile, synthetic training data, research-only status, no diagnosis/advice, and no personalized genetic-risk interpretation.
- Support anonymous session, rate-limit, capacity, offline, budget-exhausted, no-evidence, dependency, and timeout states. Never display raw unvalidated SSE tokens.
- Display budget exhaustion exactly as specified in the approved architecture, including reset time and `No calculation has been performed.`

## ML Engineer

- Implement `QuestionnaireRequirements` and `QuestionnaireValidationResult` from the approved questionnaire contract.
- Verify every manual field's order, encoding, range, missing-state handling, time frame, and transformation against the authoritative training codebook before enabling public inference.
- Fail readiness if the source codebook does not support the approved UI mapping. Do not privately remap the questionnaire; return the conflict to product and architecture review.
- Preserve generic-profile construction from artifact medians and the complete exact 105-feature validation already defined by the inference contract.

## Testing Agent

- Verify every deterministic graph route, tool denial, questionnaire completeness rule, 105-feature assembly, result-integrity rule, citation membership rule, and fixed failure response.
- Run adversarial safety, prompt-injection, code-mixed-language, rate-limit, concurrency, budget, cold-start, disconnect, reset, expiry, and dependency-failure cases.
- Independently reproduce benchmark aggregate results from frozen non-user fixtures and verify model IDs, revisions, checksums, quantization, runtime versions, and metric definitions.
- Block release on any critical safety miss, altered probability/target, fabricated citation, unsupported displayed scientific claim, questionnaire codebook mismatch, persistent user data, unvalidated raw token, or controlled request without terminal state by 60 seconds.
- Verify monitoring counters, denominators, latency percentiles, cold/warm separation, typed failure categories, timeout cancellation, rate-limit/capacity/budget separation, and absence of user-bearing observability data.
- Verify that no `95%` per-user interval is displayed unless a separately approved calibration artifact and coverage test are present; deterministic point estimates must never receive a fabricated interval.

## Documentation and review

- Reviewer verifies architecture compliance, licenses, privacy boundaries, threat model, benchmark evidence, and absence of hidden public-provider calls.
- Documentation Agent updates setup, local CPU requirements, Modal budget controls, model download procedure, corpus build, benchmark commands, public limitations, and troubleshooting only after implementation and tests pass.
- Any shared API or contract change returns to the Software Architect. Any AI/RAG threshold or model-family change returns to the AI Architect. Any questionnaire wording or encoding change returns to the Product Manager and ML Engineer.
