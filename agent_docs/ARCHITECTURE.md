# Clinical Risk AI Agent — Software Architecture

Status: Initial architecture baseline

Owner: Software Architect

Inputs: [`Problem Statement.md`](../Problem%20Statement.md), approved [`PRODUCT_PLAN.md`](PRODUCT_PLAN.md), and repository/model-artifact inspection

Related: [`INTERFACE_CONTRACTS.md`](INTERFACE_CONTRACTS.md), [`ARCHITECTURE_DECISIONS.md`](ARCHITECTURE_DECISIONS.md), [`SOFTWARE_ARCHITECT_HANDOFF.md`](SOFTWARE_ARCHITECT_HANDOFF.md)

## Architecture goals

- Preserve the runtime sequence and responsibility boundaries in the problem statement.
- Keep risk inference, validation, routing, and graph transitions explicit and testable.
- Treat DCMFNet, retrieval, and LLM providers as replaceable adapters behind typed ports.
- Run locally with minimal operational complexity while retaining production-quality module boundaries.
- Minimize exposure and persistence of mental-health questionnaire content.
- Fail closed: missing data, unavailable tools, invalid citations, or invalid model outputs produce structured failures, never plausible substitutes.

## System shape

Use a modular monolith for the MVP, exposed through one FastAPI backend and consumed by a separate Streamlit process. The backend is the composition root and hosts the LangGraph workflow, deterministic validators, and adapters. DCMFNet remains a logically isolated inference component even when it runs in the backend process.

```text
Streamlit UI
    │ HTTPS/HTTP + typed JSON
    ▼
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
                    FastAPI response
```

External LLM or embedding services, if selected, are infrastructure dependencies. They do not own workflow decisions or domain state.

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
| Streamlit UI | Input collection and rendering of API state/results | Authoritative validation, routing, inference, evidence creation | Frontend Engineer |

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
├── frontend/
│   └── app.py                      # Streamlit entry point; API client only
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
frontend ─HTTP───► api
inference adapter ───────────────────────────► inference port/contracts
RAG adapter ─────────────────────────────────► retrieval port/contracts
LLM adapter ─────────────────────────────────► explanation port/contracts
core settings/logging ◄────────────────────── composition root and adapters
```

Rules:

1. Domain contracts and ports do not import FastAPI, Streamlit, a vector database, an LLM SDK, or a concrete model class.
2. LangGraph nodes call ports injected by the FastAPI composition root; nodes do not instantiate providers.
3. FastAPI route handlers translate transport data and invoke application use cases; they do not decide graph transitions.
4. Streamlit consumes the API contract and never imports backend workflow or inference modules.
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
- A random opaque session ID, explicit reset endpoint, bounded inactivity TTL, and bounded message/state size.
- Process restart invalidates sessions and returns a machine-readable expired/not-found state.
- Raw user input, questionnaire answers, prompts containing those values, and model inputs are excluded from ordinary logs and traces.
- The Frontend may hold the opaque session ID in Streamlit session state but must not treat its local copy as authoritative workflow state.

TTL duration and state-size limits are configuration values selected by the Backend Engineer and tested; they are not hard-coded into domain behavior.

## Runtime flows

### Risk assessment

1. FastAPI validates the transport and invokes input safety handling.
2. Intent Router classifies the request as Risk Assessment.
3. LangGraph invokes questionnaire validation using the ML-owned feature requirement contract.
4. If incomplete, the graph returns structured missing-field requests and saves bounded state.
5. If complete, the graph calls the inference port exactly once for the validated input/version.
6. The inference adapter returns a structured immutable result or a typed error.
7. RAG runs only when scientific explanatory claims are requested/required by the approved workflow.
8. The context builder passes exact tool results, evidence, and limitations to the LLM.
9. Response validation compares output against structured inputs and rejects unsupported citations, score changes, and unsafe claims.

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

Safety policy can terminate or redirect the graph before inference. Deterministic policy rules and schema checks are primary; any probabilistic classifier is advisory unless separately evaluated and approved. Urgent-response wording and jurisdictional resources remain a product/safety decision and must be configuration-backed rather than fabricated by the LLM.

## Safety and validation architecture

Use defense in depth:

- **Transport validation:** type, size, encoding, required identifiers, and rate/concurrency bounds.
- **Input policy:** unsafe/unsupported classification, prompt-injection handling, and separation of user text from tool instructions.
- **Questionnaire validation:** feature identity, presence, type/range/category, and preprocessing eligibility from ML-owned metadata/contract.
- **Tool-output validation:** schema, artifact/corpus version, finite numeric values, source identity, and typed failures.
- **Prompt construction:** structured context with clear provenance; no scientific fact store or risk formula in prompts.
- **Response validation:** required limitations, prohibited medical claims, exact risk-output integrity, citation membership in retrieved results, and safe fallback on validation failure.

The response validator does not rewrite a bad score or invent a replacement citation. It retries only when policy permits with the same immutable tool context; otherwise it returns a deterministic safe error/limitation response.

## RAG architecture constraints

- The AI Architect owns the RAG architecture, source/corpus policy design, provenance semantics, pipeline stages, provider-selection criteria, and evaluation gates. The RAG Engineer validates feasibility, implements the approved design, tunes it from measured evidence, and proposes architectural changes when necessary.
- Each indexed chunk must retain a stable document/source ID and enough metadata to produce a traceable citation.
- Index artifacts are derived, reproducible data and must not be committed unless the RAG Engineer documents size/licensing/reproducibility reasons.
- Retrieval reports corpus/index version and distinguishes no result from infrastructure failure.
- The LLM may summarize retrieved evidence but may cite only identifiers present in the retrieval result.
- A provider-neutral retrieval port permits a local vector store for MVP and replacement later.

The initial preferred local adapter is a persistent local vector store with metadata filtering and deterministic test doubles. The AI Architect defines selection criteria and the RAG Engineer supplies measured feasibility evidence before the concrete store is approved; architecture does not pre-approve a vendor-specific result schema.

## DCMFNet architecture constraints

- Treat `.pt` files as untrusted serialized artifacts: load only repository-supplied, checksum-verified artifacts using the safest PyTorch mode compatible with their confirmed serialization format.
- Load models once during backend startup or first guarded use; use evaluation mode and inference/no-gradient execution.
- Validate metadata structure and artifact compatibility before readiness succeeds.
- Keep raw feature vectors and questionnaire values out of logs.
- Do not infer labels, thresholds, calibration, positive/negative target relationships, or a combined score from names alone.
- Publish an ML-owned contract before questionnaire, graph, API, or UI code binds to feature fields or results.

Repository inspection found 105 features in 11 metadata groups for both artifacts, while each `model_config.num_modalities` is 9. The negative model also uses a scalar `num_layers`, while the positive model uses a nine-element list. These may be valid constructor conventions, but only the ML Engineer may resolve them through the actual DCMFNet implementation and artifact tests.

## API and process boundaries

The public API is versioned under `/v1`. The approved resource shape is session-oriented because workflow state spans turns:

- Create a session.
- Submit a user turn to a session and receive one structured workflow response.
- Reset/delete a session.
- Liveness and readiness checks.

Exact transport paths and schemas are specified in [`INTERFACE_CONTRACTS.md`](INTERFACE_CONTRACTS.md). DCMFNet and RAG are internal ports in the MVP; exposing standalone service endpoints is deferred until an actual deployment need exists. This preserves the logical “inference API” boundary without adding a second process prematurely.

## Configuration and dependency strategy

- Use `pyproject.toml` as the canonical package/tool configuration and commit one reproducible lockfile.
- Use a `src/` package layout and explicit dependency groups/extras so frontend, ML, RAG, and development dependencies remain identifiable.
- Core families: FastAPI/Pydantic/settings, Uvicorn, LangGraph with only required LangChain packages, PyTorch, a RAG/vector adapter, an embedding adapter, an LLM adapter, Streamlit, and HTTP client support.
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
- retrieval no-evidence versus retrieval unavailable/failed
- LLM unavailable/invalid output
- response validation failure

Public errors expose a stable code, safe message, retryability, and correlation ID without stack traces or sensitive values. Logs are structured and include correlation ID, component, event, duration, state transition name, artifact/corpus version, and error code. They exclude raw messages, questionnaire answers, feature vectors, retrieved full text, prompts, model output beyond approved non-sensitive summaries, and secrets.

Readiness fails when required configuration, DCMFNet artifacts, verified model loader, or required retrieval index is unavailable. Optional external LLM readiness may be reported as degraded if the API contract can represent that state safely.

## Testing seams

- Pure functions for questionnaire validation, routing post-processing, transition predicates, score/citation integrity checks, and error mapping.
- Port-level contract suites shared by real adapters and deterministic fakes.
- Golden artifact tests owned by ML for model loading and repeatable inference.
- Retrieval fixtures with explicit synthetic source metadata; fixtures are never presented as real scientific evidence.
- Graph tests for every intent, missing-state branch, tool failure, retry/fallback, unsafe request, and response-validation failure.
- FastAPI integration tests through the public session contract.
- Streamlit end-to-end journeys against a deterministic backend test configuration.

## Architecture exit gate

ARCH-01 and ARCH-02 are complete when implementation agents accept these locations, dependencies, ownership rules, state/data policy, and contract statuses. The ML Engineer is next and must resolve blocked inference contracts before downstream consumers bind to model fields. The AI Architect then produces the detailed AI and RAG design before RAG and AI implementation.
