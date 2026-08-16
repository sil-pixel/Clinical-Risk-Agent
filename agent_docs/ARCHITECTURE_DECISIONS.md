# Architecture Decision Record Index

Status: Accepted architecture decisions for the initial MVP baseline

Owner: Software Architect

## ADR-001 — Use a modular monolith for the local MVP

**Decision:** Run one FastAPI backend containing the application workflow and injected ML/RAG/LLM adapters, plus a separate Streamlit UI process.

**Why:** The repository is a local portfolio prototype with no demonstrated scaling or organizational need for independent services. A modular monolith minimizes deployment and network failure modes while typed ports preserve future extraction boundaries.

**Consequences:** DCMFNet is a logical inference service boundary, not a separate MVP process. Modules may not bypass ports simply because they share a process. Independent services can be introduced only with an evidenced need and an ADR.

## ADR-002 — Make FastAPI the composition and trust boundary

**Decision:** FastAPI validates transport, creates dependencies/adapters, manages session access, maps typed errors, and invokes application use cases. Streamlit calls only the public API.

**Why:** This prevents UI-specific logic and alternate inference paths and provides one observable safety boundary.

**Consequences:** Route handlers stay thin; the frontend cannot import workflow, inference, or RAG internals.

## ADR-003 — Use ports and adapters for model, retrieval, embeddings, and LLMs

**Decision:** Framework-neutral typed ports isolate concrete PyTorch, vector-store, embedding, and LLM providers.

**Why:** Provider selection is unresolved, external calls require deterministic test doubles, and model/RAG contracts must stabilize independently of orchestration.

**Consequences:** Provider SDK objects cannot appear in domain contracts. The AI Architect defines AI/RAG provider criteria and boundaries; implementation engineers provide feasibility evidence and adapters. Concrete dependencies are wired only at the composition root.

## ADR-004 — Keep MVP conversational state ephemeral

**Decision:** Use bounded backend in-memory state with opaque session IDs, inactivity expiry, explicit reset, and no durable questionnaire database.

**Why:** The MVP is local/single-user and questionnaire content is sensitive. Persistence has no approved product requirement.

**Consequences:** Restart loses sessions and the API/UI must represent expiry clearly. Durable state requires a privacy review, retention policy, threat model, and new ADR.

## ADR-005 — Validate both sides of the LLM boundary

**Decision:** Construct LLM input only from validated structured context and validate its structured output for safety, exact score integrity, and citation membership.

**Why:** Prompts alone cannot enforce that the LLM will never modify risk or invent evidence.

**Consequences:** Invalid generated output is rejected; the validator may retry under a bounded policy or return a deterministic safe response, never silently repair evidence or scores.

## ADR-006 — Block downstream model schemas until executable verification

**Decision:** ML-owned questionnaire and inference payloads remain blocked until the supplied artifacts are loaded and their semantics verified.

**Why:** Metadata contains 11 feature groups/105 features despite `num_modalities: 9`, includes non-questionnaire-looking PRS and batch/PC inputs, and supplies positive/negative targets without a documented user-facing relationship.

**Consequences:** AI, Backend, and Frontend agents cannot invent fields, defaults, risk bands, a combined score, or factor attribution. A model-feasibility failure returns to Product Manager.

## ADR-007 — Keep scientific knowledge and citation identity external to prompts

**Decision:** The approved corpus and retrieval index are the scientific source; prompts contain behavior instructions and retrieved evidence only.

**Why:** This supports provenance, updateability, evaluation, and the prohibition on fabricated citations.

**Consequences:** The AI Architect designs the source/provenance and citation flow; the RAG Engineer implements it. Unsupported or out-of-corpus questions produce a limitation unless retrieval returns suitable evidence. Citation identifiers must be validated against the current retrieval result.

## ADR-008 — Use one canonical contract package

**Decision:** Cross-component code contracts live under `src/clinical_risk_agent/contracts/`; transport, adapter-private, and UI rendering types may wrap but not redefine them.

**Why:** Parallel schemas would allow drift in score, citation, and state semantics.

**Consequences:** Semantic changes follow the contract change process and require owner, architecture, test, and documentation updates.

## ADR-009 — Delay exact dependency versions and providers until feasibility spikes

**Decision:** Use `pyproject.toml` plus one committed lockfile, but select the package manager, Python version, PyTorch version, LLM/embedding provider, and vector adapter only after relevant compatibility checks.

**Why:** The repository has no dependency convention or model loader, and premature version/provider choices could make supplied artifacts unusable or compromise local reproducibility.

**Consequences:** The responsible implementation agent records each selection and clean-environment verification. Tests must run with deterministic offline fakes by default.

## ADR-010 — Keep all new agent documentation in `agent_docs/`

**Decision:** Plans, architecture, decisions, contract descriptions, handoffs, reviews, and reports created by development agents live under `agent_docs/`.

**Why:** The product owner explicitly established this repository convention.

**Consequences:** Existing canonical documents may be updated in place when assigned; code, tests, configuration, assets, and operational prompts retain their approved locations.

## Deferred decisions

- Exact Python, PyTorch, LangGraph, FastAPI, Streamlit, vector-store, embedding, and LLM package versions.
- Concrete scientific corpus/source policy and retrieval adapter.
- DCMFNet model class, preprocessing, input feasibility, and output meaning.
- Final questionnaire presentation and user-facing risk terminology.
- Exact inactivity TTL, request/state size bounds, and approved urgent-response content.

Deferred items remain owned by the roles and gates identified in the product plan and interface registry; deferral is not permission for downstream agents to guess.
