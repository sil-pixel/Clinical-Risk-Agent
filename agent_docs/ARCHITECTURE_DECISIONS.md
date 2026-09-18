# Architecture Decision Record Index

Status: Accepted architecture decisions for the initial MVP baseline

Owner: Software Architect

## ADR-001 — Use a modular monolith for the hosted MVP

**Decision:** Run one FastAPI-compatible Modal backend containing the application workflow and injected ML/RAG/LLM adapters, plus a separate Framer UI.

**Why:** The portfolio needs a public UI but has no demonstrated scaling or organizational need for independent backend services. A modular monolith minimizes deployment and network failure modes while typed ports preserve future extraction and provider replacement boundaries.

**Consequences:** DCMFNet is a logical inference service boundary, not a separate MVP process. Modules may not bypass ports simply because they share a process. Independent services can be introduced only with an evidenced need and an ADR.

## ADR-002 — Make FastAPI the composition and trust boundary

**Decision:** FastAPI validates transport, creates dependencies/adapters, manages session access, maps typed errors, and invokes application use cases. Framer calls only the public API through typed JSON or validated SSE.

**Why:** This prevents UI-specific logic and alternate inference paths and provides one observable safety boundary.

**Consequences:** Route handlers stay thin; the frontend cannot import workflow, inference, RAG internals, model artifacts, or infrastructure credentials.

## ADR-003 — Use ports and adapters for model, retrieval, embeddings, and LLMs

**Decision:** Framework-neutral typed ports isolate concrete PyTorch, vector-store, embedding, and LLM providers.

**Why:** Provider selection is unresolved, external calls require deterministic test doubles, and model/RAG contracts must stabilize independently of orchestration.

**Consequences:** Provider SDK objects cannot appear in domain contracts. The AI Architect defines AI/RAG provider criteria and boundaries; implementation engineers provide feasibility evidence and adapters. Concrete dependencies are wired only at the composition root.

## ADR-004 — Keep MVP conversational state ephemeral

**Decision:** Use cryptographically random opaque session IDs, an exact 30-minute inactivity expiry, explicit reset, and bounded process-memory-only state. Questionnaire data, conversation content, model inputs/results, and probabilities have no persistent destination, including an encrypted audit database. Multi-instance hosting uses session affinity rather than a durable shared state adapter.

**Why:** Questionnaire content is sensitive, while invited concurrent testers and multiple application instances require consistent ephemeral session state. Durable health-record persistence has no approved prototype requirement.

**Consequences:** Client and server enforce the TTL independently; polling does not renew it. Expiry, reset, restart, and crisis purge cancel work where possible and wipe volatile state. Sensitive HTTP responses are non-cacheable, browser persistent storage is prohibited, and the deployment prevents body capture, core dumps, and plaintext swap/hibernation recovery. Other user/session persistence requires a privacy review, retention policy, threat model, and new ADR.

This does not authorize durable health records.

## ADR-005 — Validate both sides of the LLM boundary

**Decision:** Construct LLM input only from validated structured context and validate its structured output for safety, exact score integrity, and citation membership.

**Why:** Prompts alone cannot enforce that the LLM will never modify risk or invent evidence.

**Consequences:** Invalid generated output is rejected; the validator may retry under a bounded policy or return a deterministic safe response, never silently repair evidence or scores.

## ADR-006 — Require executable verification before downstream model schemas

**Decision:** ML-owned questionnaire and inference payloads remain blocked until the supplied artifacts are loaded and their semantics verified.

**Why:** Metadata contains 11 feature groups/105 features despite `num_modalities: 9`, includes non-questionnaire-looking PRS and batch/PC inputs, and supplies positive/negative targets without a documented user-facing relationship.

**Verification update (2026-09-17):** The user-designated Thesis implementation and report established the model construction, preprocessing, targets, and golden outputs. `InferenceInputSchema` and `InferenceResult` are implemented. The product owner defines the outputs as separate positive- and negative-symptom research risk probabilities, approved `generic_genetic_profile_v1`, and approved the 85-visible/20-derived questionnaire contract. `QuestionnaireRequirements` is ready to implement; public inference remains blocked until ML verifies the approved mappings against the authoritative training codebook.

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

**Consequences:** DOI or PMID, publication date, source class, quality state, evidence tier, and retraction verification no older than 14 days are mandatory eligibility metadata. Relevant evidence is metadata-reranked as clinical guidelines, systematic reviews/meta-analyses, RCTs, observational studies, then expert opinion, with recency and quality applied within tiers. Material conflicts produce a controversy response representing both sides without selecting a conclusion. Bi-weekly scrubbing immediately deactivates newly detected deprecated/retracted sources, purges affected vector chunks, lexical/BM25 postings, and caches, versions every retrieval index, and records a non-retrievable tombstone. Scientific retrieval namespaces are metadata-isolated from questionnaire tokens, patient matrices, inference state, session IDs, and identities. Citations can refer only to eligible evidence retrieved for the current answer.

## ADR-013 — Fail closed on invalid probabilities without retaining sensitive values

**Decision:** Any DCMFNet probability outside inclusive `[0.0, 1.0]` is an internal system variance. The raw value remains only in a protected volatile error object until request teardown, no estimate reaches the LLM or UI, and the application returns the fixed safe error message. Raw probabilities and questionnaire tokens are prohibited from all persistence and standard observability.

**Why:** Clamping or friendly display mappings would conceal invalid model behavior, while standard logging would unnecessarily expose sensitive assessment data. India-first deployment also requires state, consent, and storage contracts capable of enforcing jurisdictional data fences and localization policy.

**Consequences:** Result views require an Indian-ecosystem synthetic-data bias indicator. The system reports predictions, not causes; without validated feature importance, it inserts the approved deterministic prediction-only message. State and consent flows carry jurisdiction, data-fence, purpose, and policy-version metadata in memory; non-compliant processing or routing fails closed.

## ADR-014 — Require claim-level citations and gate feature importance

**Decision:** Every factual medical/scientific claim requires an inline citation mapped to current verified retrieval metadata. Each generation cycle receives at most a configured 3-to-5 distinct sources, defaulting to 5. Response prose never displays raw excerpts; expandable UI evidence records show retrieval-owned exact matched text with DOI/PMID. The current system performs prediction only; locally validated feature importance may be added later, but causal inference is out of scope.

**Why:** Claim-level citations make grounding auditable, while bounded evidence reduces attention dilution and cross-source contamination. Prediction estimates an output; feature importance explains which inputs influenced that estimate; causal inference asks what produced a real-world outcome. This product implements only the first now and may add the second after validation.

**Consequences:** Conflict-aware retrieval represents each supported position within the cap or returns a limitation. Until SHAP is validated, feature-impact answers receive the deterministic prediction-only message. Later, the LLM may describe validated top-three SHAP values as feature importance for the prediction. It must not call them causes. A feature's clinical relevance may be discussed separately when supported by inline-cited medical evidence.

## ADR-015 — Intercept safety-critical and clinically prohibited requests before generation

**Decision:** Run a local safety interceptor before intent routing, RAG, inference, prompt construction, or LLM generation. Terminal decisions follow this priority: emergency/self-harm, acute distress, minor, third-party data, diagnosis, medication/treatment prescription, then normal processing. They render immutable, versioned local content and explicitly deny tools. Crisis interception cancels active generation, clears operational chat context, and emits redacted telemetry only.

**Why:** Safety behavior must not depend on generative compliance or allow a lower-priority educational route to reach assessment. Third-party processing without the data principal's participation creates consent and privacy risk. Emergency contacts and clinical boundary statements also require verified configuration rather than model memory.

**Consequences:** India resource configuration carries jurisdiction, source, verification time, and expiry; missing or stale required resources fail readiness. Tele-MANAS replaces KIRAN in current primary crisis copy because official government communications state that KIRAN was merged into Tele-MANAS. The adult-only gate is a product eligibility rule and cannot be described as an artifact training fact without evidence. Prescriptive refusal is a conservative product rule, not a claim that all telemedicine prescribing is unlawful. Safety UI remains accessible and permits copying and click-to-call. Tests must prove route precedence, streaming cancellation, context clearing, telemetry redaction, and non-reachability of prohibited tools.

## ADR-016 — Do not semantic-cache generated clinical content in the MVP

**Decision:** Do not semantic-cache generated medical, scientific, assessment, explanation, or safety responses. Exact caching is permitted only for versioned static content such as FAQs and fixed intercept scripts. A future retrieval cache may contain only non-sensitive results and must be keyed by corpus/index, eligibility-policy, and retraction-verification versions.

**Why:** Semantically similar questions may have different safety intent, personalized context, or evidence requirements. Reusing a generated answer could bypass the current safety interceptor, citation membership checks, conflict handling, or retraction state.

**Consequences:** Every input is safety-classified on every request. Static-cache keys include content ID, locale, jurisdiction, and policy version and contain no user or model data. Any later retrieval cache is invalidated on retraction, correction, corpus, allowlist, or policy changes and its entries pass current eligibility and citation validation on read.

## ADR-017 — Use an English-only gate and local fine-tuned encoder for intent classification

**Decision:** After deterministic safety interception, apply a local English-language gate. Unsupported or uncertain language terminates with the fixed English-only response and no tool authorization. Classify admitted English free text with a project-fine-tuned `distilbert/distilbert-base-uncased` Hugging Face sequence-classification encoder. This component is an encoder classifier, not a generative LLM.

**Why:** Exact keyword rules do not reliably recognize paraphrased scope and intent, while a general generative router adds unnecessary output freedom and provider dependence. The MVP supports English only, so an English DistilBERT avoids multilingual model cost and evaluation scope that the product does not need.

**Consequences:** Safety remains upstream of language rejection. A distinct typed `LanguageDecision` prevents unsupported/uncertain free text from reaching the classifier or tools and returns `Input error: Language unsupported. Please resubmit your query in English.` Its local implementation and thresholds require evaluation. The classifier emits logits only, while deterministic code owns the fixed label mapping, confidence calibration, out-of-distribution/abstention rules, and typed `IntentDecision`. Low-confidence English input clarifies or takes the minimal unsupported path and never authorizes DCMFNet. The base checkpoint is not used zero-shot. Intent evaluation covers English paraphrases, misspellings, indirect/multi-intent prompts, out-of-scope cases, and prompt injection; non-English and code-mixed samples are language-gate rejection fixtures, not intent training targets. Model downloads require license review, immutable revision/checksum pinning, integrity verification, and a reproducible local artifact process.

## ADR-018 — Enforce zero persistent user-data retention in the portfolio MVP

**Decision:** User text, questionnaire and slider state, tokens/vectors, inference inputs/results, probabilities, personalized prompts/responses, and conversation history exist only in volatile client/backend memory and are destroyed after exactly 30 minutes of inactivity, explicit reset, relevant failure/crisis purge, or process restart. They never enter a database, filesystem, browser persistent store/cache, backup, crash dump, analytics event, model cache, or external provider. This supersedes ADR-004/ADR-013's earlier encrypted sensitive-audit-store allowance.

**Why:** The portfolio demonstration does not need a health record or sensitive debugging archive. Eliminating retention and public-provider payload transmission reduces privacy, consent, breach, and India data-fence exposure.

**Consequences:** Client and server enforce independent non-renewable-by-polling TTLs. Reset clears the UI synchronously and invokes an idempotent backend purge. Models run inside the approved backend; public inference and live-user tracing APIs are forbidden. The Modal deployment uses only documented no-payload-storage Server/Endpoint transport and prohibits ordinary function calls, async/spawn payloads, user-bearing logs/snapshots, and persistent Modal stores. Observability is allowlist-based. Only pre-aggregated unlinkable product counters may persist, with no session/event rows and thresholded crisis counts. Upload schemas/routes do not exist and multipart payloads are rejected. Release testing inspects browser storage, logs/traces, provider transport, network egress, crash dumps, expiry, reset, and upload rejection. Modal's edge processing and non-sensitive platform-metadata location remain explicit compliance constraints, so the product cannot claim absolute provider invisibility or guaranteed DPDP compliance.

## ADR-019 — Deploy Framer over a Modal-hosted backend with validated streaming

**Decision:** Host the presentation layer in Framer and the provider-neutral Python modular monolith on Modal. Use a Modal Server or another currently documented zero-payload-storage endpoint, pin compute and routing to `ap-south`, inject secrets with `modal.Secret`, and stream conversational RAG through SSE. Emit only validated content blocks, never raw unvalidated model tokens. Chat risk-calculation intent returns a fixed assessment redirect; only the structured questionnaire route can invoke DCMFNet. Offline mode is display/reset only and performs no calculation.

**Why:** Framer provides the public portfolio surface and Modal provides scale-to-zero Python execution without coupling domain contracts to the host. Validated streaming improves perceived responsiveness while preserving citation and safety validation. A client-side simulated estimate would be unverifiable and could mislead users.

**Consequences:** The Framer bundle contains no infrastructure/model credentials and calls only the backend. Public transport uses narrow CORS, signed ephemeral sessions, rate/concurrency/request-size controls, and `Cache-Control: no-store`. SSE has typed `status`, `validated_content`, `evidence`, `done`, and `error` events; disconnects cancel work and no persistent replay exists. Zero idle compute and sub-second warm validation/first-status latency are objectives, not absolute zero-cost or full-RAG latency guarantees. Modal-specific code stays in the deployment adapter. Provider-documented payload retention, data residency, and endpoint behavior are reverified before release; an incompatible India data fence fails readiness. Offline UI states exactly that no calculation was performed.

## ADR-020 — Fail explicitly without sensitive incident files or uncited fallbacks

**Decision:** Apply dual client/server questionnaire completeness, use `0.85` as the initial calibrated intent-abstention threshold, and return a deterministic two-action clarification below it. Never retry invalid/non-finite model outputs, schema errors, or artifact/configuration failures; allow one identical idempotent retry only for a transient execution interruption before a result exists. Keep no-evidence, retrieval outage, generation outage, and inference outage as distinct states. Reject an entire factual claim block when its citation fails. Prohibit `ticket.jsonl` and user-bearing failure telemetry.

**Why:** A disabled incomplete form improves the UI but cannot secure the backend. Repeating a deterministic invalid output cannot repair it. A universal risk-summary fallback could imply that inference occurred during a standalone evidence request, while removing only a bad citation would expose an unsupported medical claim. Raw queries, stacks, metrics, and vectors in a serverless JSONL file conflict with the approved zero-retention boundary.

**Consequences:** Backend validation alone authorizes the exact 105-variable matrix after approved generic-profile assembly. `0.85` is a versioned initial product threshold—not an accuracy or safety guarantee—and remains subject to calibration and per-class release evaluation. Existing valid results may survive an explanation outage with a target-aware limitation, but outages cannot create results. A failed claim block is returned only if the remaining response stays coherent, complete, and fully cited; otherwise one bounded regeneration precedes the fixed failure response. Operational failure events contain only allowlisted codes, coarse buckets, retry count, deployment mode, and component/version fields.

## ADR-021 — Separate statistical quality targets from hard runtime integrity

**Decision:** Require `>85%` intent accuracy and `>0.85` macro-F1 on the frozen evaluation set while keeping `0.85` as a distinct calibrated per-request clarification threshold. Require zero observed false negatives on the finite critical-safety release suite. Treat first-pass citation matching `>85%` and unsupported claims `<=5%` as generator diagnostics; displayed citations and medical/scientific claims still require `100%` provenance/support. Apply dense cosine `>0.85` only to the selected normalized embedding configuration. Require exact raw-result preservation and a terminal success-or-safe-failure UI state within 60 seconds in controlled tests.

**Why:** Accuracy, confidence, cosine similarity, and citation validity have different denominators and meanings. Aggregate model targets cannot authorize a known bad citation, unsupported claim, altered probability, or unsafe route. Embedding scores are not portable across models, and zero observed errors on a finite suite is not proof of zero production error.

**Consequences:** Reports include dataset/component versions, class distribution, per-class metrics, calibration, abstention, retrieval metrics, cold/warm latency percentiles, denominators, and confidence intervals where meaningful. Changing the embedding requires similarity recalibration. Raw model values remain immutable while the presenter deterministically formats percentages. Evaluation evidence comes from synthetic or approved non-user fixtures and aggregate CI artifacts, never `ticket.jsonl` or retained production conversations.

## ADR-022 — Fall back from vector retrieval to independent lexical search

**Decision:** If dense/vector retrieval fails or returns no eligible match, execute one deterministic BM25/keyword search against a separately available lexical index built from the same approved scientific corpus. Successful fallback evidence enters the normal reranking/context/validation path with `retrieval_mode=keyword_fallback`. Return `NO_ELIGIBLE_EVIDENCE` only after both paths complete with zero eligible evidence and `RETRIEVAL_UNAVAILABLE` only when no approved retrieval path completes.

**Why:** Lexical retrieval can recover exact terminology, acronyms, PMID/DOI strings, and service availability without allowing the LLM to answer from memory. An independent availability boundary is necessary; a sparse index hosted only inside the failed vector service would not be a real outage fallback.

**Consequences:** Deterministic English tokenization and a versioned scientific synonym/abbreviation map create fallback terms. The same DOI/PMID, allowlist, date, quality, retraction, scientific/non-patient isolation, relevance, evidence hierarchy, conflict, and source-cap rules apply. Query terms remain volatile and unlogged. Evaluation segments primary, fallback-only, and combined results and reports activation, recovery, dual-zero-result, and added latency. Keyword search does not authorize general-web retrieval or bypass the 60-second terminal deadline.

## ADR-023 — Approve the CPU-only public operating envelope

**Decision:** Permit anonymous public access through signed ephemeral sessions with no invitation code or individual account. Support at most 50 active testers, approximately 1,000 daily visitors, 50 simultaneous HTTP requests, and initially eight concurrent CPU-heavy model jobs. GPU execution is prohibited. Modal has a `$0` out-of-pocket spend limit and a usage budget no greater than available monthly credits; zero idle containers are required.

**Why:** The portfolio should be publicly inspectable without collecting identity data, while the owner has not approved GPU spend or paid overage. Separating HTTP concurrency from CPU-heavy concurrency prevents a 50-user burst from multiplying LLM memory and cost beyond the free-credit envelope.

**Consequences:** Apply signed-session, per-session, transient network-key, global daily, concurrency, and request-size controls. Load shed before the 60-second deadline rather than queue indefinitely. Budget or quota exhaustion returns the fixed usage-limit response and performs no calculation. Free operation is a target under light use, not an availability guarantee for every request from 1,000 daily visitors.

## ADR-024 — Approve corpus scope, model candidates, and evaluation policy

**Decision:** Scope scientific retrieval to substance use, schizophrenia, depression, psychosis, mental/emotional/sexual/physical abuse, bullying, ADHD, ASD, and scientifically supported associations among those topics. Index PubMed abstracts and eligible full text only when machine-readable licensing permits it; paywalled or unclear-license full text is not ingested. One live PubMed retrieval escalation is allowed after local and lexical retrieval cannot supply eligible evidence. Use MedCPT encoders and cross-encoder as primary biomedical retrieval candidates, Qwen2.5 1.5B Instruct GGUF Q4_K_M as the primary CPU generator candidate, fastText language identification as the primary language candidate, and project-fine-tuned DistilBERT artifacts for intent and safety. Exact revisions are release-approved only after measured comparison.

**Why:** These candidates fit the CPU-only envelope and match PubMed retrieval better than an unqualified general-purpose stack, while preserving evidence-based selection. Licensing and live-search gates prevent corpus convenience from overriding source eligibility.

**Consequences:** The benchmark report controls final artifact approval. The dense cosine `>0.85` rule is a hypothesis to calibrate for the selected embedding, not a portable release threshold. BERTScore is offline secondary evidence only, uses human-reviewed references, and has no assumed `0.85` gate or runtime authority.

## ADR-025 — Approve public operations and emergency-resource maintenance

**Decision:** Apply 10 model-backed turns per hour and 25 per day per signed session, three assessment submissions per day per session, five session creations per hour per transient network key, and an initial global ceiling of 1,000 model-backed operations per day. Reverify emergency-resource content manually every 30 days and run automated link/configuration checks daily.

**Why:** These limits bound anonymous abuse and free-credit exposure while leaving normal portfolio evaluation usable. Emergency information is operational safety content and needs a much shorter verification cycle than ordinary documentation.

**Consequences:** Rate-limit keys are one-way, short-lived, non-telemetry values. Stale optional helplines are suppressed until reverified; the separately verified national emergency route remains available. Capacity, budget, and quota failures are typed availability states and never expose partial model output.

## Deferred implementation decisions

- Exact Python, PyTorch, LangGraph, FastAPI, Modal SDK, Framer integration, and benchmark-winning model revisions/checksums.
- Concrete retrieval adapter and quality-appraisal instruments; the scientific source/corpus eligibility policy is approved in ADR-012.
- Training-codebook compatibility evidence for the approved questionnaire encodings.
- Exact request/state size bounds. The inactivity TTL is approved at 30 minutes.

Deferred items remain owned by the roles and gates identified in the product plan and interface registry; deferral is not permission for downstream agents to guess.
