# Development Agent Workflow

This document coordinates development agents; it is not runtime orchestration code. [`Problem Statement.md`](../Problem%20Statement.md) is authoritative for roles, architecture, responsibilities, safety boundaries, and goals. Every agent must inspect existing code before changing it, preserve established contracts, document important decisions, report assumptions/blockers, avoid another agent's ownership, and leave a clear handoff.

## Agent documentation location

Create every new agent-generated planning, architecture, decision, contract, handoff, review, test-report, and supporting documentation file under [`agent_docs/`](../agent_docs/). Organize subdirectories there only when the repository needs them. Update an existing canonical document in place when explicitly assigned, but do not create new documentation elsewhere. Source code, tests, configuration, assets, and the operational prompts in `agents/` remain in their architecture-approved locations.

## Invariant runtime design

`User → Input Validation + Safety → Intent Router → LangGraph State Machine → conditional questionnaire collection / DCMFNet inference / RAG retrieval → Structured Context → LLM → Response Validation → User`

- The Intent Router identifies what the user wants; it does not assess questionnaire completeness.
- LangGraph selects the next workflow step.
- Questionnaire validation identifies missing information.
- DCMFNet alone performs deterministic risk inference.
- RAG alone supplies scientific evidence.
- The LLM explains supplied results and evidence; it never calculates or changes scores, fabricates evidence/citations, diagnoses, or recommends medication.

## Skill coverage by role

Skills describe the capabilities needed to perform an existing role; they do not transfer responsibility between roles.

| Agent | Primary skill focus |
| --- | --- |
| Product Manager | MVP planning, prioritization, acceptance criteria, dependencies, healthcare AI product safety |
| Software Architect | Python architecture, contracts, component boundaries, security/privacy, technical decisions |
| ML Engineer | PyTorch inference, artifact/schema validation, preprocessing, reproducibility, model metadata |
| RAG Engineer | Scientific ingestion, embeddings, vector/hybrid retrieval, reranking, provenance, evaluation |
| AI Engineer | LangChain/LangGraph, tool calling, typed state, prompts, grounded generation, LLM safety |
| Backend Engineer | FastAPI/Pydantic, API integration, validation, resilience, observability, service testing |
| Frontend Engineer | Streamlit, accessible questionnaire UX, API integration, state, safe visualization |
| Testing Agent | pytest, contract/integration/E2E testing, failure injection, safety and regression testing |
| Reviewer | Code/architecture review, security/privacy, cross-component correctness, technical debt |
| Documentation Agent | Technical writing, verified setup/API docs, architecture communication, safety language |

## Recommended sequence

### 1. Product Manager

- **Receives:** Problem statement, repository inventory, known constraints.
- **Produces:** MVP scope, milestones, prioritized tasks, acceptance criteria, dependency/risk list.
- **Exit gate:** Work is bounded, testable, assigned to existing roles, and safety/non-goals are explicit.
- **Possible return:** Any later agent may return unclear scope or conflicting acceptance criteria.

### 2. Software Architect

- **Receives:** Product plan and current repository/artifact inventory.
- **Produces:** Repository/component design, service boundaries, contract ownership, dependency decisions, data/state flow, decision records.
- **Exit gate:** Component responsibilities and locations are approved; unresolved model semantics are explicitly deferred to ML rather than guessed.
- **Possible return:** ML, RAG, AI, Backend, Reviewer, or Testing may return interface or boundary problems.

### 3. ML Engineer

- **Receives:** Architecture boundaries, acceptance criteria, DCMFNet artifacts and metadata.
- **Produces:** Verified model loading/inference implementation, typed prediction contract, metadata validation, tests, model handoff.
- **Exit gate:** Inputs, ordering/preprocessing, output semantics, errors, and model version are evidence-based and testable—or a precise artifact blocker is recorded.
- **Possible return:** AI/Backend integration failures, Testing defects, or Reviewer correctness findings return here.

### 4. RAG Engineer

- **Receives:** Architecture boundaries, source/corpus policy, acceptance criteria, dependency decisions.
- **Produces:** Ingestion/retrieval pipeline, provenance-preserving result contract, configuration, quality/failure tests, retrieval handoff.
- **Exit gate:** Results are structured and traceable to real sources; citation and no-evidence behavior are defined.
- **Possible return:** AI integration failures, retrieval-quality gaps from Testing, or provenance findings from Reviewer return here.

### 5. AI Engineer

- **Receives:** Approved architecture plus stable ML and RAG tool contracts.
- **Produces:** Intent router, typed LangGraph state/nodes/edges, questionnaire/tool orchestration, prompts, structured response validation, workflow tests.
- **Exit gate:** Supported intents and state transitions are explicit; missing data, tool failure, unsafe requests, and evidence requirements are covered; the LLM cannot alter scores or invent citations.
- **Possible return:** Backend integration, graph failures from Testing, or responsibility-boundary findings from Reviewer return here. Contract defects go to ML/RAG/Architect rather than being patched locally.

### 6. Backend Engineer

- **Receives:** Stable graph, inference, and retrieval contracts plus architecture/API constraints.
- **Produces:** FastAPI schemas/endpoints, service integration, validation, configuration, errors/health behavior, API tests and handoff.
- **Exit gate:** Integrated APIs preserve contract ownership and safety boundaries and are stable for frontend use.
- **Possible return:** Frontend contract issues, API failures from Testing, or boundary/security findings from Reviewer return here.

### 7. Frontend Engineer

- **Receives:** Stable backend contracts, product journeys, safety/display requirements.
- **Produces:** Streamlit questionnaire/chat/result/evidence experience, API client, session/error states, UI checks and handoff.
- **Exit gate:** Core journeys work with real APIs; displayed scores/evidence are unmodified; limitations are clear; no backend workflow logic is duplicated.
- **Possible return:** UI defects from Testing/Reviewer return here; API contract defects return to Backend and, if foundational, Architect.

### 8. Testing Agent

- **Receives:** Acceptance criteria, contracts, implementations, agent test handoffs, runnable configuration.
- **Produces:** Risk-based unit/integration/end-to-end and safety tests, reproducible defect reports, rerun evidence, gap/residual-risk summary.
- **Exit gate:** Critical workflows and safety invariants pass, or failures are assigned and tracked; fixes are rerun by Testing.
- **Possible return:** Route failures to the owning agent—for example, LangGraph transition failure → AI Engineer → Testing rerun; inference mismatch → ML Engineer; citation provenance failure → RAG Engineer; endpoint failure → Backend; UI journey failure → Frontend.

### 9. Reviewer

- **Receives:** Complete changes, architecture/contracts, acceptance traceability, test evidence, known limitations.
- **Produces:** Prioritized code/architecture/safety review, technical-debt record, recheck results, documentation handoff.
- **Exit gate:** Blocking findings are fixed and rechecked or explicitly accepted by the proper owner; residual risks are visible.
- **Possible return:** API boundary issue → Software Architect and/or Backend Engineer → Reviewer recheck. Scope issues return to Product Manager; test gaps return to Testing; component defects return to their owner.

### 10. Documentation Agent

- **Receives:** Reviewer-approved behavior, final contracts/decisions, verified setup/run/test commands, limitations.
- **Produces:** Accurate README, architecture, API, setup, test, configuration, and troubleshooting documentation.
- **Exit gate:** A new contributor can reproduce and understand verified behavior, and safety/limitations are prominent.
- **Possible return:** Documentation/code mismatch returns to the owning implementation agent and Reviewer; documentation-only defects return here.

## Iteration protocol

1. The discovering agent records a reproducible finding, affected acceptance criterion/contract, severity, and proposed owner.
2. The owning agent inspects the current implementation and makes the smallest in-scope correction; cross-contract changes require Architect review and notification to all consumers.
3. Testing reruns the narrow failing check and relevant regression suite.
4. Reviewer rechecks material architecture, safety, or public-contract changes.
5. Documentation updates only after behavior and contracts are verified.

No agent should mask an upstream contract problem with a private duplicate schema or adapter invented without coordination.

## Current repository dependency note

At initial inspection, the repository contains the problem statement, a minimal README, and DCMFNet `.pt` plus metadata artifacts, but no established application directory structure, dependency manifest, API/schema contracts, corpus, or implementation tests. Therefore Product Manager and Software Architect outputs are prerequisites; the ML Engineer must verify the artifact contract before AI or Backend code assumes it; and RAG requires an explicit scientific source/corpus policy before ingestion can be considered complete.
