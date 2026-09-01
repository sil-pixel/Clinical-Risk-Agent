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

**Decision:** Use cryptographically random opaque session IDs, inactivity expiry, explicit reset, and no durable operational questionnaire/state database. Local development uses bounded in-memory state; the hosted prototype uses an anonymous, shared, expiring adapter behind the same state port. A separate encrypted, access-controlled audit-trail database is the sole permitted persistence destination for raw probabilities and questionnaire tokens, keyed only by cryptographic session ID and never user identity.

**Why:** Questionnaire content is sensitive, while invited concurrent testers and multiple application instances require consistent ephemeral session state. Durable health-record persistence has no approved prototype requirement.

**Consequences:** The API/UI represents expiry clearly, and prototype operational sessions are intentionally temporary. The audit store is not a session checkpointer or application log and cannot be used to reconstruct user identity. Its encryption, access control, India data fence, consent/purpose metadata, retention/deletion policy, and access audit are mandatory. Concrete hosted-store technology, TTL, capacity, and deletion behavior remain pending privacy/operations decisions. Other durable state requires a privacy review, retention policy, threat model, and new ADR.

This does not authorize durable health records.

## ADR-005 — Validate both sides of the LLM boundary

**Decision:** Construct LLM input only from validated structured context and validate its structured output for safety, exact score integrity, and citation membership.

**Why:** Prompts alone cannot enforce that the LLM will never modify risk or invent evidence.

**Consequences:** Invalid generated output is rejected; the validator may retry under a bounded policy or return a deterministic safe response, never silently repair evidence or scores.

## ADR-006 — Require executable verification before downstream model schemas

**Decision:** ML-owned questionnaire and inference payloads remain blocked until the supplied artifacts are loaded and their semantics verified.

**Why:** Metadata contains 11 feature groups/105 features despite `num_modalities: 9`, includes non-questionnaire-looking PRS and batch/PC inputs, and supplies positive/negative targets without a documented user-facing relationship.

**Verification update (2026-08-16):** The user-designated Thesis implementation and report established the model construction, preprocessing, targets, and golden outputs. `InferenceInputSchema` and `InferenceResult` are now implemented. The product owner defines the outputs as separate positive- and negative-symptom research risk probabilities and approved `generic_genetic_profile_v1`, using artifact medians for PRS and batch-by-PC inputs in the portfolio MVP. `QuestionnaireRequirements` remains blocked only on reviewed user-facing definitions for manually collected fields.

**Consequences:** AI and Backend may integrate the exact internal inference contract and generic-profile provenance. Agents cannot invent other questionnaire defaults, derive genetic values from family history or population descriptors, add risk bands or a combined probability, or claim factor attribution.

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

## ADR-011 — Separate prototype and hospital research modes

**Decision:** Define `prototype_demo` and future `hospital_silent_research` as explicit, non-interchangeable deployment modes carried through configuration, workflow state, results, telemetry, and tests.

**Why:** The Product Manager approved a public-facing research demonstration now and an India-first, clinician-only hospital silent-validation product later. Prototype-only generic genetic assumptions, synthetic weights, and display behavior must not leak into hospital research workflows.

**Consequences:** Composition fails closed when a mode requests an unapproved adapter or policy. `generic_genetic_profile_v1` is valid only in `prototype_demo`; fail-closed rejection of out-of-range probabilities applies in every mode. Hospital mode remains unimplemented until its regulatory, ethics, privacy, clinical-evidence, security, and data contracts are approved. Clinical decision support is not implied by hospital silent validation.

## ADR-012 — Restrict scientific evidence and continuously monitor retractions

**Decision:** Scientific RAG admits only eligible peer-reviewed or PubMed-indexed literature, DOI/PMID-bearing authoritative health-organization publications, and DOI/PMID-bearing clinical guidelines from the rolling prior 20 years. It hard-excludes preprints, theses/dissertations, curated local PDFs, general websites, retracted papers, and evidence failing a versioned quality appraisal. Authority discovery uses a versioned domain allowlist initially covering `*.who.int`, `*.cdc.gov`, `*.nih.gov`, `*.nhs.uk`, and configured Indian health-ministry/public-health domains under `*.gov.in`. Incremental ingestion and complete-corpus retraction scrubbing run every two weeks.

**Why:** Scientific answers require reproducible provenance and ongoing validity. Ingestion-time retraction checks alone cannot detect a later retraction, while authority domains and local files alone do not establish publication identity or quality.

**Consequences:** DOI or PMID, publication date, source class, quality state, evidence tier, and retraction verification no older than 14 days are mandatory eligibility metadata. Relevant evidence is metadata-reranked as clinical guidelines, systematic reviews/meta-analyses, RCTs, observational studies, then expert opinion, with recency and quality applied within tiers. Material conflicts produce a controversy response representing both sides without selecting a conclusion. Bi-weekly scrubbing immediately deactivates newly detected deprecated/retracted sources, purges affected vectors/chunks and caches, versions the corpus, and records a non-retrievable tombstone. The scientific vector namespace is metadata-isolated from questionnaire tokens, patient matrices, inference state, session IDs, and identities. Citations can refer only to eligible evidence retrieved for the current answer.

## ADR-013 — Fail closed on invalid probabilities and isolate sensitive audit data

**Decision:** Any DCMFNet probability outside inclusive `[0.0, 1.0]` is an internal system variance. The application records the raw value only through the encrypted audit port, sends no estimate to the LLM or UI, and returns the fixed safe error message. Raw probabilities and questionnaire tokens are prohibited from standard logs and may persist only in an access-controlled audit database keyed by a cryptographically random session ID, never user identity.

**Why:** Clamping or friendly display mappings would conceal invalid model behavior, while standard logging would unnecessarily expose sensitive assessment data. India-first deployment also requires state, consent, and storage contracts capable of enforcing jurisdictional data fences and localization policy.

**Consequences:** Result views require an Indian-ecosystem synthetic-data bias indicator. The LLM cannot attribute risk to an individual answer and must use the approved collective-105-input statement for feature-impact questions. State, consent, audit, and database schemas carry jurisdiction, data-fence, purpose, retention, and policy-version metadata aligned with the DPDP compliance mapping; non-compliant storage or routing fails closed.

## Deferred decisions

- Exact Python, PyTorch, LangGraph, FastAPI, Streamlit, vector-store, embedding, and LLM package versions.
- Concrete retrieval adapter and quality-appraisal instruments; the scientific source/corpus eligibility policy is approved in ADR-012.
- DCMFNet input feasibility and provenance.
- Final questionnaire presentation.
- Exact inactivity TTL, request/state size bounds, and approved urgent-response content.

Deferred items remain owned by the roles and gates identified in the product plan and interface registry; deferral is not permission for downstream agents to guess.
