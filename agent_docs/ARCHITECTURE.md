# Clinical Risk AI Agent — Software Architecture

Status: Initial architecture baseline

Owner: Software Architect

Inputs: [`Problem Statement.md`](../Problem%20Statement.md), approved [`PRODUCT_PLAN.md`](PRODUCT_PLAN.md), and repository/model-artifact inspection

Related: [`INTERFACE_CONTRACTS.md`](INTERFACE_CONTRACTS.md), [`ARCHITECTURE_DECISIONS.md`](ARCHITECTURE_DECISIONS.md), [`SOFTWARE_ARCHITECT_HANDOFF.md`](SOFTWARE_ARCHITECT_HANDOFF.md)

## Architecture goals

- Preserve the runtime sequence and responsibility boundaries in the problem statement.
- Keep risk inference, validation, routing, and graph transitions explicit and testable.
- Treat DCMFNet, retrieval, and LLM providers as replaceable adapters behind typed ports.
- Run in a Framer-plus-Modal portfolio topology with minimal operational complexity while retaining provider-neutral module boundaries and deterministic local test doubles.
- Keep the modular-monolith prototype safely hostable for invited concurrent testers, with volatile state, identity, inference, retrieval, and LLM adapters replaceable behind typed ports.
- Enforce zero persistent application storage for user text, questionnaire content, model inputs/results, probabilities, and personalized responses in `prototype_demo`.
- Fail closed: missing data, unavailable tools, invalid citations, or invalid model outputs produce structured failures, never plausible substitutes.

## System shape

Use a modular monolith for the MVP, exposed through one FastAPI-compatible backend hosted on Modal and consumed by a Framer site. The backend is the composition root and hosts the LangGraph workflow, deterministic validators, locally hosted models, and adapters. DCMFNet remains a logically isolated inference component even when it runs in the same Modal container.

```text
Framer UI
    │ HTTPS + typed JSON / validated SSE
    ▼
Modal Server / eligible zero-payload-retention endpoint
    │
FastAPI boundary
    │
    ├─ input validation + safety policy
    │        │
    │        ▼
    ├─ intent router
    │        │
    │        ▼
    └─ LangGraph application workflow
             ├─ questionnaire validator
             ├─ DCMFNet inference port ──► local PyTorch adapter
             ├─ evidence retrieval port ─► local vector-store adapter
             └─ explanation port ─────────► configured LLM adapter
                         │
                         ▼
               response safety/grounding validator
                         │
                         ▼
          validated JSON/SSE response
```

LLM, embedding, reranking, and classifier models execute in the approved Modal backend and never through public model APIs. User-bearing traffic must use a Modal Server or another endpoint type whose current provider contract does not store request/response payloads; ordinary Modal Function invocation paths are prohibited. Modal is a hosting processor, not an owner of workflow decisions or domain state, and its documented metadata location and edge processing remain deployment-review constraints.

## Runtime responsibility map

| Component | Owns | Must not own | Development owner |
| --- | --- | --- | --- |
| Input validation and safety | Request shape/size checks, normalization, unsafe/unsupported policy result, urgent-content response routing | Intent, questionnaire completeness, diagnosis | AI Architect designs; AI Engineer implements; Backend integrates |
| Intent Router | Classification into the approved intent set, confidence/fallback signal | Missing-field checks or next graph node | AI Architect designs; AI Engineer implements |
| LangGraph workflow | State transitions and selection of the next explicit step | Model computation, retrieval internals, hidden autonomous branches | AI Architect designs; AI Engineer implements |
| Questionnaire validator | Required/valid/missing feature determination from the verified ML contract | Risk calculation or conversational intent | ML Engineer owns requirements; AI Engineer integrates |
| DCMFNet adapter | Artifact validation/loading, preprocessing, deterministic inference, model result | Explanations, citations, diagnosis, thresholds not present in verified artifacts | ML Engineer |
| RAG subsystem | Corpus ingestion, embeddings, retrieval/reranking, source provenance | Risk score or unsupported citation generation | AI Architect designs; RAG Engineer implements |
| Structured context builder | Assembly of validated tool outputs for explanation | Creation or alteration of tool results | AI Architect designs; AI Engineer implements |
| LLM explanation adapter | Natural-language explanation of supplied structured context | Score calculation/change, evidence invention, workflow control | AI Architect designs; AI Engineer implements |
| Response validator | Schema, score-integrity, citation-integrity, required limitation and safety checks | Recalculation or silent repair of invalid risk/evidence | AI Architect designs; AI Engineer implements |
| FastAPI boundary | Transport validation, dependency wiring, session access, error mapping, readiness | Domain/workflow decisions inside route handlers | Backend Engineer |
| Framer UI | Input collection and rendering of API state/results, fixed redirects, evidence drawers, offline availability state | Authoritative validation, routing, inference, evidence creation, offline estimates | Frontend Engineer |

## Proposed repository structure

This is the approved target layout for implementation agents. Agents should create only the portions needed by their assigned stage.

```text
.
├── agent_docs/                     # all new agent-generated documentation
│   ├── ARCHITECTURE.md
│   ├── ARCHITECTURE_DECISIONS.md
│   ├── INTERFACE_CONTRACTS.md
│   ├── PRODUCT_PLAN.md
│   └── SOFTWARE_ARCHITECT_HANDOFF.md
├── agents/                         # operational development-agent prompts
├── model_artifacts/                # supplied immutable DCMFNet artifacts + metadata
├── src/
│   └── clinical_risk_agent/
│       ├── api/                    # FastAPI routes, transport schemas, dependencies
│       ├── application/            # use cases and structured-context assembly
│       ├── contracts/              # shared typed internal/public contracts
│       ├── core/                   # settings, error taxonomy, logging/telemetry policy
│       ├── inference/              # inference port, DCMFNet adapter, metadata validation
│       ├── questionnaire/          # required-field and answer validation
│       ├── rag/                    # retrieval port, ingestion, index adapter, provenance
│       ├── safety/                 # input and response policy/validation
│       └── workflow/               # intent router, LangGraph state/nodes/edges, prompts
├── frontend/                       # Framer code components/API client source when exported or mirrored
│   └── README.md                   # integration contract; no backend or model imports
├── deploy/
│   └── modal_app.py                # Modal-only composition, regions, secrets, scaling
├── tests/
│   ├── unit/
│   ├── contract/
│   ├── integration/
│   └── e2e/
├── data/                           # local corpus/index workspace; generated content ignored
├── pyproject.toml                  # package, dependency groups, tool configuration
└── lockfile                        # exact filename selected with the package manager
```

Do not create a second set of shared schemas under the frontend or individual adapters. `contracts/` is the canonical code location for cross-component types. Adapter-private types remain inside their component.

## Dependency direction

```text
api ─────────────► application/workflow ─────► contracts + ports
Framer frontend ─HTTPS/JSON/SSE───► api
inference adapter ───────────────────────────► inference port/contracts
RAG adapter ─────────────────────────────────► retrieval port/contracts
LLM adapter ─────────────────────────────────► explanation port/contracts
core settings/logging ◄────────────────────── composition root and adapters
```

Rules:

1. Domain contracts and ports do not import FastAPI, Framer/React, Modal, a vector database, an LLM SDK, or a concrete model class.
2. LangGraph nodes call ports injected by the FastAPI composition root; nodes do not instantiate providers.
3. FastAPI route handlers translate transport data and invoke application use cases; they do not decide graph transitions.
4. Framer consumes the API contract and never embeds backend workflow, credentials, model artifacts, or inference modules.
5. Model and retrieval adapters may import shared contracts, but shared contracts may not import adapters.
6. Prompts are version-controlled resources inside `workflow/`; scientific facts do not live in prompts.

## State model and lifecycle

The canonical workflow state is typed and contains only fields required to select the next node or construct a validated response. The AI Architect designs its topology/categories; exact code types are finalized by the AI Engineer against established contracts:

- Opaque session identifier and state/schema version.
- Validated conversation turns needed for current context.
- Current intent classification and safety decision.
- Questionnaire answers keyed by verified feature identifiers, plus validation status and missing identifiers.
- Optional immutable inference result supplied by the inference port.
- Optional retrieval query and immutable evidence results supplied by the retrieval port.
- Structured limitations, tool errors, next-action/status, and final validated response.

MVP state policy:

- Backend memory only; no database or durable LangGraph checkpointer.
- A cryptographically random opaque session ID, explicit reset endpoint, exactly 30 minutes of inactivity, and bounded message/state size.
- Client and server enforce expiry independently. Background polling and keep-alives do not renew activity. Expiry, reset, crisis purge, or process restart cancels active work where possible, wipes volatile state, invalidates the session, and returns a machine-readable expired/not-found state.
- Raw user input, questionnaire tokens/answers, prompts containing those values, model inputs/results, probabilities, and personalized responses are excluded from all persistence, logs, traces, metrics, analytics events, caches, crash dumps, and backups.
- The frontend may hold the opaque session ID and questionnaire state only in volatile application memory. It cannot use cookies for payload state, `localStorage`, `sessionStorage`, IndexedDB, service-worker caches, or URL/query parameters. Sensitive responses use `Cache-Control: no-store`.

State-size limits remain configured and tested. The 30-minute TTL is an approved product invariant, not a provider default.

## Runtime flows

### Conversational assessment request

1. FastAPI validates transport, then safety and language gates run.
2. The intent router recognizes direct or rephrased risk-calculation intent.
3. The chat route returns deterministic `ASSESSMENT_REDIRECTION`; it has no DCMFNet binding and performs no inline calculation or interpretation.
4. The Framer action opens a fresh volatile structured assessment state. It does not run inference.

### Structured risk assessment

1. Framer enables submission only after every approved manual field is locally valid; the structured route then independently validates the active session, route authorization, safety state, and questionnaire against the ML-owned feature contract.
2. If incomplete, it returns structured missing-field information in volatile state.
3. The backend adds only `generic_genetic_profile_v1`, assembles and validates the exact complete 105-variable matrix, and ignores forged client-completion flags.
4. If complete, it calls the inference port once for the validated input/version. Only an allowlisted transient execution interruption before a result exists may repeat that call once using the identical volatile vector, target, artifact, and idempotency key.
5. The inference adapter returns an immutable result or typed error. A deterministic boundary gate requires finite values in inclusive `[0.0, 1.0]`; an invalid value is never retried, remains only in the protected volatile request object, and becomes a fail-closed internal-system-variance error.
6. RAG runs only when scientific explanatory claims are requested or required.
7. The context builder passes exact results, evidence, and limitations to the LLM; response validation rejects unsupported citations, score changes, causal overstatement, and unsafe claims.

### Explain existing risk

1. Router selects Explain My Risk.
2. LangGraph checks state for a valid inference result; the router does not perform this check.
3. If absent, the graph routes to assessment completion.
4. If present, the graph retrieves relevant evidence, builds structured context, obtains an explanation, and validates it.

### Scientific or educational question

1. Router selects Scientific Question or Mental Health Education.
2. LangGraph bypasses questionnaire and inference unless the user explicitly starts an assessment.
3. RAG retrieves evidence; no/low-confidence evidence becomes an explicit limitation.
4. The LLM explains only retrieved content, and citation validation runs before return.

Questions outside the approved corpus—such as a personalized diabetes-risk question—must never invoke DCMFNet. The system either provides evidence-grounded general education if the corpus policy covers the topic or clearly reports that adequate evidence is unavailable; it does not estimate personalized risk.

### Unsupported, unsafe, or urgent content

Safety policy terminates or redirects the graph before intent routing, retrieval, prompt construction, or inference. The deterministic priority is emergency/self-harm, acute distress, minor, third-party data, diagnosis, medication/treatment prescription, then normal processing. Exact rules and an evaluated local classifier may detect safety cases, but safety-critical uncertainty fails closed. Terminal routes render versioned local scripts; the LLM never authors or modifies them.

Self-harm interception cancels active generation, clears operational chat context, and emits only redacted event metadata. Third-party health data is rejected rather than made apparently anonymous by stripping relational words. The under-18 gate blocks inference as a product eligibility rule; architecture must not assert an adult-only training population without artifact evidence. India emergency and crisis resources are versioned, source-verified configuration and readiness fails if required resources are missing or stale.

## Safety and validation architecture

Use defense in depth:

- **Transport validation:** type, size, encoding, required identifiers, and rate/concurrency bounds.
- **Input policy:** unsafe/unsupported classification, prompt-injection handling, and separation of user text from tool instructions.
- **Questionnaire validation:** feature identity, presence, type/range/category, and preprocessing eligibility from ML-owned metadata/contract.
- **Tool-output validation:** schema, artifact/corpus version, finite numeric values, source identity, and typed failures.
- **Prompt construction:** structured context with clear provenance; no scientific fact store or risk formula in prompts.
- **Response validation:** required limitations, prohibited medical claims, exact risk-output integrity, claim-level inline citation completeness and membership, source-cap/excerpt-placement rules, attribution-gate integrity, and safe fallback on validation failure.

The response validator does not rewrite a bad score or invent a replacement citation. It retries only when policy permits with the same immutable tool context; otherwise it returns a deterministic safe error/limitation response.

After safety returns `ALLOW_NORMAL_PROCESSING`, a local language gate admits only supported English free text. Unsupported or uncertain language returns exactly `Input error: Language unsupported. Please resubmit your query in English.` and cannot reach intent classification or tools. Rephrased English intent and scope classification then uses a project-fine-tuned `distilbert/distilbert-base-uncased` Hugging Face sequence-classification encoder. A deterministic adapter owns label mapping, calibration, abstention, typed output, and model provenance. The classifier cannot generate text, create labels, call tools, or authorize DCMFNet. A calibrated maximum confidence below `0.85`, an out-of-distribution result, or unresolved incompatible intent produces `INTENT_CLARIFICATION_REQUIRED` with the approved two actions and no RAG, LLM, or inference. The base checkpoint is not a production classifier until project-specific fine-tuning and evaluation pass approved thresholds.

For any raw probability below `0.0` or above `1.0`, the UI returns exactly `Error: Unable to compute estimate due to an internal system variance. Please try again later.` The system never clamps, displays, logs, transmits, or persists the raw value. It remains only in the protected volatile failure object until request teardown.

This system performs prediction, not causal inference. Today it cannot rank individual inputs or explain why a result is high. Without validated feature importance, the application inserts: `This is a prediction, not a causal explanation. The model evaluates all 105 inputs together; no single answer can be identified as the cause of the result. Validated feature importance is not available for this result.` Valid result views also include the required synthetic-data warning.

A future local SHAP adapter may report which inputs most influenced a specific prediction. It is a separately validated ML port, must bind to the exact model result, and exposes only structured provenance plus the top three SHAP values. SHAP describes model behavior; it does not identify what caused a clinical outcome. Clinical relevance is discussed separately only when supported by inline-cited retrieved evidence. Alternative feature-importance methods require separately versioned contracts.

## RAG architecture constraints

- The AI Architect owns the RAG architecture, source/corpus policy design, provenance semantics, pipeline stages, provider-selection criteria, and evaluation gates. The RAG Engineer validates feasibility, implements the approved design, tunes it from measured evidence, and proposes architectural changes when necessary.
- Each indexed chunk must retain a stable document/source ID and enough metadata to produce a traceable citation.
- Index artifacts are derived, reproducible data and must not be committed unless the RAG Engineer documents size/licensing/reproducibility reasons.
- Retrieval reports corpus/index version and distinguishes no result from infrastructure failure.
- The LLM may summarize retrieved evidence but may cite only identifiers present in the retrieval result.
- Every factual medical/scientific claim requires an explicit inline citation to current verified evidence. Uncited, speculative, or extrapolated claims fail response validation.
- The per-generation distinct-source cap is configurable from 3 through 5 and defaults to 5. Fewer sources are allowed; weak evidence is never added to fill the cap. Conflict-aware selection represents each supported position within the cap or returns a limitation.
- Matched evidence text never appears raw in response prose. The API/UI carries separate retrieval-owned display records so collapsed tooltips or side drawers can show the exact matched string, DOI/PMID, and source metadata.
- Feature associations may be discussed only when current matched text explicitly states them and the claim is inline-cited. Literature provides clinical context; SHAP provides model feature importance. Neither is causal inference.
- A provider-neutral retrieval port permits a local vector store for MVP and replacement later.
- General web sources are prohibited. Authority discovery uses a versioned allowlist initially covering `*.who.int`, `*.cdc.gov`, `*.nih.gov`, `*.nhs.uk`, and configured Indian health-ministry/public-health domains under `*.gov.in`; URL canonicalization and redirects are revalidated, and DOI/PMID plus all quality gates remain mandatory.
- The scientific vector collection is disconnected from patient-specific data. Questionnaire tokens/matrices, feature vectors, inference payloads, session IDs, and identities are never embedded or indexed. Mandatory pre-search metadata filters require the scientific-publication/general-mental-health/non-patient data class and fail closed if absent or mismatched.
- Every two weeks, automated retraction scrubbing verifies all active PMIDs/DOIs against PubMed and/or another approved active retraction index. Newly deprecated/retracted vectors are immediately purged from active retrieval and context, caches are invalidated, the index is versioned, and only a non-retrievable tombstone remains.

The initial preferred local adapter is a persistent local vector store with metadata filtering and deterministic test doubles. The AI Architect defines selection criteria and the RAG Engineer supplies measured feasibility evidence before the concrete store is approved; architecture does not pre-approve a vendor-specific result schema.

## DCMFNet architecture constraints

- Treat `.pt` files as untrusted serialized artifacts: load only repository-supplied, checksum-verified artifacts using the safest PyTorch mode compatible with their confirmed serialization format.
- Load models once during backend startup or first guarded use; use evaluation mode and inference/no-gradient execution.
- Validate metadata structure and artifact compatibility before readiness succeeds.
- Keep raw feature vectors, questionnaire tokens/values, and raw probabilities out of all persistence, standard logs, traces, metrics, analytics, caches, crash dumps, and backups. They exist only in protected volatile memory for the current session/request.
- Preserve the separate positive- and negative-symptom research risk probabilities, their normalized target labels, and raw outputs; do not add thresholds, calibration, risk bands, or a combined probability.
- Fail closed before presentation when a raw probability falls outside inclusive `[0.0, 1.0]`; do not clamp it or pass it to the LLM.
- Publish an ML-owned contract before questionnaire, graph, API, or UI code binds to feature fields or results.

ML verification against the user-designated Thesis implementation resolved the artifact structure: the 11 groups are one anchor, nine iteratively fused modalities, and one independent modality. Scalar versus list-valued layer configuration is supported by the verified constructor. The target-specific CPU inference adapter, preprocessing, immutable results, and golden tests are implemented under `src/clinical_risk_agent/`. For the portfolio MVP, `generic_genetic_profile_v1` supplies PRS and batch-by-PC fields from the selected artifact's training medians with explicit unmeasured/generic provenance. End-user questionnaire semantics remain blocked only until reviewed wording, encodings, units, and ranges exist for the manually collected fields.

## API and process boundaries

Product-direction update (2026-09-01): the current application is `prototype_demo`; a future India-first `hospital_silent_research` mode is clinician-only, never patient-facing, and cannot affect care. The mode boundary must be explicit and fail-closed. Generic genetic inputs are not valid in hospital mode by default. All modes use the same fail-closed out-of-range gate. Portfolio state and consent objects carry jurisdiction, data-fence, purpose, and policy-version metadata only in volatile memory. Any future hospital persistence requires separate schemas, retention policy, governance, and ADR; it cannot inherit or weaken the prototype boundary silently.

The public API is versioned under `/v1`. The approved resource shape is session-oriented because workflow state spans turns:

- Create a session.
- Submit a user turn to a session and receive one structured workflow response.
- Reset/delete a session.
- Liveness and readiness checks.

Exact transport paths and schemas are specified in [`INTERFACE_CONTRACTS.md`](INTERFACE_CONTRACTS.md). DCMFNet and RAG are internal ports in the MVP; exposing standalone service endpoints is deferred until an actual deployment need exists. This preserves the logical “inference API” boundary without adding a second process prematurely.

The Framer browser communicates only with the Modal-hosted API. Scientific-RAG text uses SSE events for status and validated content; raw LLM tokens are never emitted before response validation. Fixed safety, language, and assessment-redirection results may use typed JSON or a terminal SSE event. Sensitive responses use `Cache-Control: no-store`; reconnects cannot replay user content from persistent storage.

The Modal adapter pins compute and routing to `ap-south`, sets zero minimum containers and a short measured scale-down window, injects backend secrets with `modal.Secret`, and applies CORS/origin restrictions, signed ephemeral sessions, rate/concurrency/request-size controls, and cost alerts. Zero idle compute is a target, not an absolute zero-cost guarantee. Warm validation and first-progress-event latency target sub-second performance; cold starts and full RAG latency are measured separately.

Offline Framer behavior is display-only: it may preserve current volatile UI state, render static disclosures, navigate, and reset. It blocks RAG, LLM, assessment submission, and DCMFNet and shows `You're offline. Research estimates and evidence-based answers require a connection. No calculation has been performed.` The generic profile is never used to fabricate an offline estimate.

## Configuration and dependency strategy

- Use `pyproject.toml` as the canonical package/tool configuration and commit one reproducible lockfile.
- Use a `src/` package layout and explicit dependency groups/extras so frontend, ML, RAG, and development dependencies remain identifiable.
- Core families: FastAPI/Pydantic/settings, an ASGI server, Modal deployment SDK, LangGraph with only required LangChain packages, PyTorch, a RAG/vector adapter, an embedding adapter, a locally hosted LLM adapter, Hugging Face classifiers, and HTTP/SSE support. Framer/React dependencies remain in the frontend project rather than the Python package.
- Development families: pytest and async/integration support, lint/format, static type checking, and security/dependency checks.
- Pin versions in the lockfile only after ML artifact compatibility and provider adapters are verified. Do not guess a PyTorch version before loading tests identify the artifact's requirements.
- Provider packages are adapters, never imported by domain contracts. Tests use deterministic fakes and must not require network access or paid credentials by default.
- Secrets come only from environment/configuration; commit a safe example containing names and descriptions but no values.

The implementation owner should select the package manager and exact supported Python version during the dependency bootstrap, record the decision, and demonstrate it from a clean environment. No current repository convention exists to justify choosing one now.

## Errors and observability

Use a stable error taxonomy across internal and public boundaries:

- validation/safety rejection
- session missing/expired
- questionnaire incomplete/invalid
- artifact/configuration incompatibility
- inference unavailable/failed
- internal system variance for a probability outside `[0.0, 1.0]`
- retrieval no-evidence versus retrieval unavailable/failed
- LLM unavailable/invalid output
- response validation failure

Public errors expose a stable code, safe message, and retryability without stack traces or sensitive values. Internal logs use allowlisted component/route, latency bucket, artifact/corpus/policy version, and error/status code fields. They exclude raw messages, request/response bodies, questionnaire tokens/answers, feature vectors, retrieved full text, prompts, probabilities, session/correlation IDs, IP addresses, user agents, referrers, headers, secrets, and stack-local sensitive values.

Failure routing is typed and deterministic:

- `INTENT_CLARIFICATION_REQUIRED` renders the approved two-button clarification; each button opens a new bounded flow and neither executes a tool.
- invalid/non-finite DCMFNet values, schema errors, and artifact/configuration failures are non-retryable; transient execution failures alone may retry once with immutable inputs and idempotency.
- `NO_ELIGIBLE_EVIDENCE`, `RETRIEVAL_UNAVAILABLE`, and `GENERATION_UNAVAILABLE` have distinct fixed messages and never fall back to uncited model knowledge.
- A valid existing result may remain visible when only explanation dependencies fail, with a deterministic target-aware limitation. A standalone RAG request never receives a risk summary.
- Citation failure rejects the associated factual claim block rather than deleting its citation. If the remaining response is incomplete or incoherent, reject the whole response; one bounded regeneration is allowed before the fixed failure response.

There is no sensitive audit sink in `prototype_demo`, and runtime creation of `ticket.jsonl` is prohibited. Exact invalid probabilities and full exception objects may be inspected only inside protected volatile request memory and are wiped on teardown. Operational failure telemetry is limited to allowlisted coarse time/latency buckets, component/operation/error codes, retry count, deployment mode, and version identifiers; it contains no raw stack/locals, query, target metrics, probability, evidence, or session/user/network identifier. Persisted product metrics, if enabled, are aggregate counters or coarse duration buckets created before persistence with no event rows, time stamps, session/correlation IDs, network/device fields, route sequences, safety text, questionnaire data, or probabilities. Crisis counts use minimum aggregation and disclosure thresholds.

Raw runtime payloads cannot be sent to public model or telemetry APIs. LLMs, embeddings, rerankers, safety/intent classifiers, and DCMFNet run inside the approved Modal backend. User-bearing transport uses only documented no-payload-storage endpoint types; ordinary function invocation, async/spawn payloads, user-data logs/snapshots, and persistent Modal stores are prohibited. Compute/routing is pinned to Mumbai and the provider's metadata/log location and TLS edge remain explicit compliance limitations. Bibliographic APIs receive only generated non-sensitive scientific search terms.

Readiness fails when required configuration, DCMFNet artifacts, verified model loader, required self-hosted models, privacy/deployment controls, or required retrieval index is unavailable. Configuration of a public runtime inference/embedding/telemetry provider, an ineligible Modal invocation path, or an incompatible data-residency policy is a failed-readiness condition, not a degraded option.

## Quality gates

- Intent routing on the frozen labeled suite requires `>0.85` accuracy and `>0.85` macro-F1, with per-class metrics, calibration, abstention, and confusion matrices reported. The separate per-request confidence threshold is `0.85`; it is not dataset accuracy.
- Every finite critical-safety release fixture must route correctly with zero observed false negatives. This blocks a failing release but is not described as a guarantee of zero production misses.
- Dense candidates require cosine similarity `>0.85` for the selected normalized embedding artifact. The score is not a probability and must be recalibrated after any embedding change; Precision@k, Recall@k, MRR, nDCG, zero-result behavior, and conflict coverage are also reported.
- The unvalidated first-pass generator targets `>85%` citation-context matching and `<=5%` unsupported claims. Public output requires `100%` citation provenance and `0%` displayed unsupported medical/scientific claims; aggregate draft quality never weakens the hard validator.
- DCMFNet raw output/identity preservation requires exact equality across inference and public result contracts. Deterministic percentage formatting is a separate presenter operation and cannot overwrite the raw field.
- Controlled end-to-end runs must produce terminal validated success or safe failure in `<=60 seconds`, reporting cold/warm p50, p95, p99, and maximum separately.
- Evaluations use versioned synthetic or approved non-user fixtures and produce aggregate CI artifacts. They do not use `ticket.jsonl` or retained production content.

## Testing seams

- Pure functions for questionnaire validation, routing post-processing, transition predicates, score/citation integrity checks, and error mapping.
- Port-level contract suites shared by real adapters and deterministic fakes.
- Golden artifact tests owned by ML for model loading and repeatable inference.
- Boundary tests for below-zero and above-one probabilities, the exact public error, volatile-only raw-value handling, teardown wiping, and log/trace/cache leakage.
- Privacy tests for 30-minute client/server expiry, polling resistance, reset idempotency, browser storage, `no-store` headers, provider egress, aggregate-only analytics, crash/swap controls, and multipart/upload rejection.
- Retrieval fixtures with explicit synthetic source metadata; fixtures are never presented as real scientific evidence.
- Retrieval tests for authority allowlisting, mandatory patient/scientific metadata isolation, stale-retraction rejection, and active-index purging.
- Response tests for claim-level citation completeness/entailment, the 3-to-5 source cap, collapsed evidence-display separation, and conflict coverage.
- Explainability tests for absent/invalid feature importance, deterministic prediction-only messaging, exact-result binding, top-three SHAP JSON integrity, value/rank preservation, and causal-language rejection.
- Graph tests for every intent, missing-state branch, tool failure, retry/fallback, unsafe request, and response-validation failure.
- Failure tests for the calibrated `0.85` boundary, two-action clarification, zero retry on invalid outputs, single retry on allowlisted transient failures, no-evidence/outage separation, claim-level citation rejection, and absence of `ticket.jsonl` or sensitive exception telemetry.
- FastAPI integration tests through the public session contract.
- Framer end-to-end journeys against a deterministic backend test configuration, including validated SSE ordering/cancellation, assessment redirection, offline no-inference behavior, secret absence, CORS, and no persistent replay.

## Architecture exit gate

ARCH-01 and ARCH-02 are complete. The ML Engineer has published verified inference contracts, and the Product Manager has approved the generic genetic-input policy. The AI Architect is next and must preserve its provenance and the exact ML result semantics while designing the detailed AI and RAG architecture before RAG and AI implementation. Reviewed definitions for manually collected questionnaire fields remain a downstream contract dependency.
