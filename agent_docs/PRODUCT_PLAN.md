# Clinical Risk AI Agent — MVP Product Plan

Status: Approved by product owner on 2026-08-16; amended through 2026-08-26 to define the AI architecture inputs and startup evolution path

Source of truth: [`Problem Statement.md`](../Problem%20Statement.md)

Development workflow: [`agents/workflow.md`](../agents/workflow.md)

## Product outcome

Deliver a locally runnable and safely hostable research demonstration in which invited testers can complete structured data collection, receive DCMFNet's separate research outputs under explicit prototype limitations, and receive a plain-language explanation grounded in traceable scientific literature. The system must demonstrate the explicit stateful architecture in the problem statement rather than behave as an unconstrained chatbot, while retaining typed boundaries that can support a later India-first hospital research product without reusing unsafe demonstration assumptions.

Success means a new contributor can clone, configure, run, test, and inspect the complete workflow, including its safety boundaries and failure behavior.

## Users and primary journeys

The MVP is an AI engineering portfolio and research demonstration for invited testers such as friends, developers, evaluators, and researchers. Testers are not treated as patients, the application does not participate in their care, and no result may be used for a health decision.

The planned startup product is separate: an India-first, clinician-only platform for hospital silent research validation. It will not face patients, and its outputs will not influence care during the silent-validation stage.

1. **Complete a research risk assessment:** request an assessment, supply missing required information over one or more turns, receive separate DCMFNet-produced positive- and negative-symptom risk probabilities only after validation, and see uncertainty and research-only limitations.
2. **Explain an existing result:** ask why a result may be elevated or reduced, retrieve relevant scientific evidence, and receive an explanation that keeps model output distinct from literature-backed contextual claims.
3. **Ask an educational/scientific question:** receive an evidence-grounded answer with traceable citations, or a clear statement that adequate evidence was not retrieved.
4. **Make a general or unsupported request:** receive an appropriate conversational response or safe refusal without invoking irrelevant inference/retrieval steps.
5. **Recover from incomplete or failed operations:** understand what information is missing or which service failed without fabricated fallback results.

## MVP scope

### P0 — required for MVP

- Input validation and safety handling before intent routing.
- The intent categories defined in the problem statement, with deterministic post-classification workflow handling.
- A manual, stateful questionnaire for fields with approved user-facing semantics that reports missing required data and never calls inference prematurely.
- Reproducible loading and deterministic inference for the supplied DCMFNet artifacts, with validated model metadata and structured outputs.
- Scientific document ingestion and semantic retrieval with source provenance and citation metadata.
- LangGraph orchestration that preserves the ownership split among routing, questionnaire validation, inference, retrieval, and explanation.
- An LLM explanation layer constrained to supplied structured model results and retrieved evidence.
- Response validation enforcing non-diagnostic language, uncertainty, research-only limitations, score integrity, and citation integrity.
- FastAPI integration and a Streamlit interface supporting the primary journeys.
- Unit, integration, end-to-end, safety, and negative-path tests for the critical workflow.
- Local setup, architecture, API, model limitation, RAG provenance, and usage documentation.

### P1 — valuable after the core path is stable

- Retrieval reranking and measured retrieval-quality improvements beyond the minimum viable baseline.
- Richer evidence and risk-factor visualizations that do not imply unsupported causality.
- Developer-facing observability for graph transitions, inference latency, retrieval outcomes, and validation failures without logging sensitive questionnaire values.
- Expanded evaluation sets for intent, safety, groundedness, retrieval relevance, and conversational follow-ups.

### Out of scope

- Diagnosis, screening claims, clinical decision support, treatment or medication recommendations, crisis-care replacement, or guarantees about future outcomes.
- Clinical validation, real-patient deployment, regulated-device claims, or use of confidential participant data.
- Training, fine-tuning, recalibrating, or changing DCMFNet unless separately authorized.
- LLM-generated risk computation, score adjustment, model-output substitution, evidence, or citations.
- A general autonomous agent that creates new workflow branches outside the explicit LangGraph design.
- Multi-user production hosting, organization administration, billing, or a production electronic-health-record integration.
- Any reuse of generic PRS/PCA values, prototype out-of-range display mappings, or synthetic-model claims in hospital research mode without a separately approved protocol and validated contract.

## Product acceptance criteria

| ID | Acceptance criterion | Verification owner |
| --- | --- | --- |
| AC-01 | A user can start each supported primary journey through the Streamlit interface and receive a structured, understandable response. | Frontend Engineer / Testing Agent |
| AC-02 | Every input passes safety and validation handling before intent routing; unsupported or unsafe requests cannot reach risk inference accidentally. | AI Engineer / Testing Agent |
| AC-03 | The Intent Router selects what the user wants but does not decide questionnaire completeness or the next workflow step. | AI Engineer / Testing Agent |
| AC-04 | LangGraph uses explicit state and conditional transitions to collect missing data, call tools, and determine when explanation can occur. | AI Engineer / Testing Agent |
| AC-05 | Questionnaire validation identifies required missing/invalid values from the verified inference contract; DCMFNet is not called until the contract is satisfied. | ML Engineer / AI Engineer / Testing Agent |
| AC-06 | The supplied artifacts load reproducibly, incompatible artifacts fail safely, and identical validated input under the same model/runtime produces the same unmodified structured result. | ML Engineer / Testing Agent |
| AC-07 | No LLM code path calculates, changes, formats, or fabricates a risk result. The deterministic presenter converts raw values to approved percentages while preserving the exact immutable raw result. | AI Engineer / Reviewer / Testing Agent |
| AC-08 | Scientific or medical claims produced by the assistant are supported by retrieved sources with traceable citation metadata; absent evidence yields an explicit limitation rather than a fabricated answer. | AI Architect / RAG Engineer / AI Engineer / Testing Agent |
| AC-09 | Explanations clearly distinguish model output from literature context and communicate uncertainty, limitations, synthetic-data provenance, and research-only/non-diagnostic use. | AI Engineer / Frontend Engineer / Testing Agent |
| AC-10 | The assistant does not diagnose, recommend medication, guarantee outcomes, claim certainty, or fabricate citations/model outputs across tested supported and adversarial paths. | Testing Agent / Reviewer |
| AC-11 | FastAPI validates public inputs/outputs, integrates the established contracts, returns actionable structured failures, and exposes readiness sufficient for local use. | Backend Engineer / Testing Agent |
| AC-12 | The UI displays the two server-provided probabilities separately using the validated percentage representation, required explanation, and disclaimer; it provides clear missing-data, loading, no-evidence, and service-failure states. | Frontend Engineer / Testing Agent |
| AC-13 | Automated tests cover unit, contract, integration, end-to-end, failure, and safety-critical paths and can run from documented local commands. | Testing Agent / Reviewer |
| AC-14 | A clean checkout can be installed and run locally using documented prerequisites, configuration, ingestion/setup, application, and test commands. | Documentation Agent / Testing Agent |
| AC-15 | Important architecture and contract decisions, assumptions, limitations, and unresolved risks are discoverable in repository documentation. | Software Architect / Reviewer / Documentation Agent |
| AC-16 | Every prototype result states that the system is a research demonstration, not a patient product, and that the output must not be used for a health or care decision. | AI Engineer / Frontend Engineer / Testing Agent |
| AC-17 | Deployment mode is explicit and fail-closed; prototype-only generic inputs and display behavior cannot execute under any future hospital-research configuration. | Software Architect / Backend Engineer / Testing Agent / Reviewer |

## Milestones and ordered backlog

### M1 — Product and architecture foundation

1. **PM-01 — Confirm MVP and acceptance traceability** (Product Manager): maintain this scope, decision log, and owner/dependency mapping. Depends on the problem statement. Done when the Architect can design without guessing product intent.
2. **ARCH-01 — Establish component and repository architecture** (Software Architect): define boundaries, dependency direction, configuration approach, and contract ownership without assuming model semantics. Depends on PM-01. Done when implementation locations and integration responsibilities are unambiguous.
3. **ARCH-02 — Define safety, state, data-handling, and observability principles** (Software Architect): document input/output safety placement, state lifetime, sensitive-data handling, logs, and failure boundaries. Depends on PM-01. Done when later agents share the same constraints.

### M2 — Deterministic model and evidence foundations

4. **ML-01 — Verify supplied DCMFNet artifacts** (ML Engineer): establish load requirements, feature grouping/order, preprocessing, output semantics, target relationship, versioning, and deterministic behavior. Depends on ARCH-01. Done when no downstream consumer must infer model behavior.
5. **ML-02 — Implement and test the inference contract** (ML Engineer): validate inputs/metadata and return unmodified structured outputs or explicit errors. Depends on ML-01. Done when AC-05 and AC-06 have executable evidence.
6. **AIARCH-01 — Design AI and RAG architecture** (AI Architect): define graph/tool/context architecture, corpus/source policy, ingestion-to-reranking design, provenance/citation flow, provider criteria, safety controls, and measurable AI/RAG quality gates. Depends on ARCH-01 and ML-01; model-dependent decisions remain provisional until ML-02. Done when RAG and AI Engineers can implement without inventing architecture.
7. **RAG-01 — Implement approved scientific retrieval architecture** (RAG Engineer): validate source feasibility, ingest the approved corpus, implement embeddings/index/retrieval/reranking and provenance contracts, and execute retrieval-quality/failure evaluations. Depends on AIARCH-01. Done when AC-08 retrieval prerequisites are demonstrated.

### M3 — Stateful intelligence and service integration

8. **AI-01 — Implement intent and LangGraph workflow** (AI Engineer): build explicit state, routing, questionnaire progression, inference/retrieval tool calls, and failure branches using the approved AI architecture and stable ML/RAG contracts. Depends on AIARCH-01, ML-02, and RAG-01. Done when AC-02 through AC-05 pass focused tests.
9. **AI-02 — Implement grounded explanation and response validation** (AI Engineer): constrain LLM behavior to supplied results/evidence and validate safety, uncertainty, score, and citation integrity. Depends on AI-01. Done when AC-07 through AC-10 pass focused evaluations.
10. **BE-01 — Expose and integrate application APIs** (Backend Engineer): implement FastAPI validation, service wiring, session/state integration, errors, and readiness using established contracts. Depends on AI-02. Done when AC-11 passes integration tests.

### M4 — User experience

11. **FE-01 — Implement core Streamlit journeys** (Frontend Engineer): build questionnaire, conversation, result, evidence, and limitation experiences against the stable API. Depends on BE-01. Done when AC-01 and AC-12 pass with real service integration.
12. **FE-02 — Complete accessible failure and recovery states** (Frontend Engineer): cover missing data, validation errors, no evidence, service failures, and expired/missing assessment state. Depends on FE-01. Done when the UI never substitutes a plausible-looking result for failure.

### M5 — Release confidence and handoff

13. **TEST-01 — Execute cross-system verification** (Testing Agent): complete acceptance traceability, automate critical unit/contract/integration/end-to-end/safety paths, and route failures to component owners. Depends on the functioning core system. Done when AC-01 through AC-14 have results and residual gaps are explicit.
14. **REV-01 — Review release candidate** (Reviewer): assess code, architecture, safety, privacy, provenance, dependencies, technical debt, and test evidence; require owner fixes and recheck them. Depends on TEST-01. Done when blockers are resolved or formally accepted by the appropriate owner.
15. **DOC-01 — Complete reproducible documentation** (Documentation Agent): document only reviewed behavior, contracts, setup, operation, tests, and limitations. Depends on REV-01. Done when AC-14 and AC-15 are independently reproducible.

## Dependency map

`PM scope → software architecture → verified DCMFNet contract → AI Architect design → RAG implementation → AI implementation → backend API → frontend → system testing → review → documentation`

Work may overlap only where contracts are not being guessed. In particular:

- The AI Architect may begin provider-independent RAG/AI design after software architecture, but model-dependent workflow and explanation decisions wait for the verified ML contract.
- RAG implementation follows the approved AI Architect design; AI implementation waits for stable ML and implemented RAG contracts.
- Frontend implementation waits for a stable backend contract; exploratory wireframes may not become an alternative source of application logic.
- Testing begins at every component, while the dedicated cross-system stage follows a functioning integrated path.
- Material fixes return to their owner, then Testing reruns and Reviewer rechecks as specified in the shared workflow.

## Safety and data requirements

- Every user-facing risk result must be labeled as research-only, uncertain, non-diagnostic, and based on a synthetic-data-trained model.
- Every probability presentation must state that users should not act on the probability alone and that it does not replace qualified professional judgment.
- Preserve exact raw model values internally. Percentage conversion, the approved `99.9% at risk` high out-of-range representation, and the `No risk could be seen` below-zero representation are deterministic presentation logic; the LLM never performs them.
- Do not display low/moderate/high bands until scientifically validated thresholds are approved.
- Scientific claims require retrieved evidence; retrieval failure must be visible.
- The model result remains authoritative for the numeric risk output. Explanations and visualizations must not transform its meaning.
- The MVP should minimize collection, persistence, and logging of sensitive questionnaire data. Durable storage is not an assumed requirement; the Architect must document state lifetime and any persistence decision before implementation.
- Logs, fixtures, screenshots, and documentation must not contain real personal mental-health data.
- The application must communicate service/tool failures rather than generating a substitute answer.

## Risks and mitigations

| Risk | Impact | Required mitigation / owner |
| --- | --- | --- |
| Resolved: 105 features across 11 groups represent one anchor, nine fusion modalities, and one independent modality. | Incorrect loading or feature routing could invalidate inference. | Verified against the Thesis implementation and protected by golden/runtime tests; preserve the published ML contract. |
| The portfolio questionnaire cannot measure 16 PRS fields or four batch-by-genetic-PC interaction fields. | Hiding generic inputs could make the result appear more personalized than it is. | Resolved for MVP with `generic_genetic_profile_v1`: use artifact-provided training medians, disclose the generic assumptions in every result, and never derive values from family history or population descriptors. |
| The two symptom probabilities could be combined or confused in presentation. | A combined value would change the model meaning and could mislead users. | Display positive- and negative-symptom probabilities separately, retain their target identity and limitations, and prohibit the LLM/UI from recalculating or combining them. |
| Resolved: model class, preprocessing, safe loader, dependency manifest, and golden tests are now present. | Runtime regressions could invalidate inference. | Testing Agent retains artifact hashes and golden cases as release gates. |
| No scientific corpus or source policy is present. | RAG cannot meet citation and grounding criteria. | AI Architect designs a traceable, legally usable source policy within product constraints; RAG Engineer validates and implements it. |
| LLM or embedding provider is not selected. | Local reproducibility, cost, privacy, and tests remain uncertain. | AI Architect defines provider criteria, abstraction/configuration, and safe local/test fallbacks; Product Manager confirms material cost/privacy constraints. |
| Sensitive questionnaire content may leak through logs, traces, prompts, or persisted state. | Privacy and trust failure even in a prototype. | Architect defines minimization and state/logging policy; Backend, AI, Frontend, Testing, and Reviewer enforce it. |
| Retrieved association evidence may be phrased as individual causation. | Misleading medical communication. | AI prompts/validation and reviewer tests must distinguish population evidence, model association, and individual prediction. |

## Assumptions and open decisions

### Working assumptions for architecture planning

- The MVP is local-first but must be safely hostable for a small set of concurrent invited testers using anonymous, expiring sessions and no assumed durable health-data record.
- Scale is preserved through typed ports, configuration, stateless service design where practical, and replaceable state/provider adapters—not premature microservices.
- India is the first planned regulatory market. The first hospital product is clinician-only silent research validation and is never patient-facing.
- The supplied artifacts remain unchanged and use only synthetic training data as stated in the problem statement.
- Structured internal contracts and deterministic mocks/fakes are acceptable for automated tests involving external LLM, embedding, or literature services.
- Exact AI/RAG technology and provider choices follow AI Architect criteria and responsible-engineer feasibility evidence, constrained by Software Architect boundaries, local reproducibility, and safety.

### Decisions required before implementation can be called complete

1. **Resolved — model feasibility:** Both artifacts load through the verified Thesis-derived runtime and return separate positive- and negative-symptom research risk probabilities for normalized symptom-severity targets.
2. **Resolved for portfolio MVP — input journey:** Use a manual questionnaire for fields with approved user-facing semantics and `generic_genetic_profile_v1` for unavailable PRS and batch-by-PC inputs. Generic values come from the selected artifact's training medians, are disclosed as unmeasured assumptions, and are never derived from family history or a population descriptor. Verified genomic input is deferred.
3. **Resolved — result presentation:** Present separate positive- and negative-symptom percentages, preserve exact raw values internally, show high out-of-range output as `99.9% at risk`, show below-zero output as `No risk could be seen`, require explanation/disclaimer, and use no risk bands.
4. **Scientific source policy:** Which literature sources/corpus and licensing/update rules satisfy traceability and local demonstration needs?
5. **Provider constraints:** Which LLM and embedding configurations balance reproducibility, cost, privacy, and portfolio usability?
6. **State lifetime:** Is assessment state memory-only for the MVP, and what explicit reset/expiry behavior is required?
7. **Safety escalation language:** What approved response should accompany potentially urgent user statements while preserving the prototype's non-clinical role?
8. **Public prototype operations:** What invitation/access control, session TTL, concurrency, hosting, and deletion behavior are required for friends and testers?

## Software Architect handoff

The Architect should receive this plan, the problem statement, the agent workflow, the current repository inventory, and all supplied model artifacts/metadata.

Prioritize architectural work that unblocks ML artifact verification and RAG source-policy definition. Define component boundaries, dependency direction, contract ownership, state and sensitive-data lifecycle, configuration/provider strategy, failure handling, observability, and decision-record conventions. Do not define the questionnaire schema, risk output semantics, model defaults, or combined score until the ML Engineer establishes them from artifact evidence.

The Product Manager stage is complete for initial architecture planning. It must be revisited if model/input feasibility invalidates the questionnaire journey, if scientific-source constraints prevent grounded answers, or if architecture choices materially change local reproducibility, privacy, cost, or MVP scope.
