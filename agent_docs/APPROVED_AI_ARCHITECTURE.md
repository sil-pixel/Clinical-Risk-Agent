# Approved AI Architecture

Status: Architecture approved for implementation; model artifacts remain subject to the release benchmarks defined in [`AI_MODEL_BENCHMARK_REPORT.md`](AI_MODEL_BENCHMARK_REPORT.md)

Owner: AI Architect

Date approved: 2026-09-17

Sources: [`Problem Statement.md`](../Problem%20Statement.md), [`AI_ARCHITECTURE_REQUIREMENTS.md`](AI_ARCHITECTURE_REQUIREMENTS.md), [`ARCHITECTURE.md`](ARCHITECTURE.md), and [`INTERFACE_CONTRACTS.md`](INTERFACE_CONTRACTS.md)

## Approved objective

Build a portfolio-grade, research-only AI system that can be safely hosted for invited prototype testers and demonstrates hybrid routing, explicit LangGraph orchestration, adaptive scientific RAG, local and live literature search, structured generation, deterministic validation, and measurable evaluation. Preserve replaceable boundaries for a future India-first, clinician-only hospital silent-validation product. The system remains a bounded workflow rather than an autonomous multi-agent swarm.

This architecture preserves the approved runtime sequence and responsibility boundaries. It incorporates the approved conversational scope, scientific-source, safety, questionnaire, portfolio privacy, deployment, operations, and workflow-failure policies. Component families and resource envelopes are approved here; exact model revisions, quantized artifacts, and calibrated thresholds are release-controlled selections that become deployable only after the measured gates in the benchmark report pass.

## Product-mode boundary

The architecture defines two non-interchangeable modes:

- `prototype_demo`: current scope; invited non-patient testers, manual questionnaire, synthetic-data-trained model, `generic_genetic_profile_v1`, prototype result presentation, explicit non-clinical disclaimer, and no health-decision use.
- `hospital_silent_research`: future scope; India-first, authenticated clinicians/researchers, ethics/governance-approved hospital data, validated provenance, no patient-facing UI, no effect on care, and no generic genetic or prototype display behavior unless independently justified and approved.

Every volatile request, graph state, and inference result, plus every non-user corpus/artifact audit record and synthetic evaluation fixture, carries its deployment mode. Composition fails closed when a mode requests an unapproved adapter, profile, presenter, prompt, source, or persistence policy. The hospital mode is an interface constraint for now, not an implemented or regulated product claim.

## Approved topology

![Clinical Risk AI Agent query flow](images/clinical-risk-ai-query-flow.png)

```text
User in Framer
  ↓
Modal Server / eligible no-payload-storage endpoint
  ↓
Deterministic transport validation and safety policy
  ├── terminal safety/refusal result → fixed local UI content → User
  └── ALLOW_NORMAL_PROCESSING
  ↓
English-language gate
  ├── UNSUPPORTED/UNCERTAIN_LANGUAGE → fixed English-only response → User
  └── SUPPORTED_ENGLISH
  ↓
Hybrid Intent Router
  ├── deterministic rules for explicit structured/content cases
  └── local fine-tuned encoder classification for ambiguous cases
  ├── conversational risk intent → fixed questionnaire redirection → User
  ↓
LangGraph Supervisor
  ├── Assessment subgraph
  ├── Risk-explanation subgraph
  ├── Scientific RAG subgraph
  ├── Education/conversation subgraph
  └── Unsupported-content subgraph
  ↓
Structured Context Builder
  ↓
Locally hosted, provider-neutral LLM adapter with structured output
  ↓
Deterministic response validator
  ↓
validated JSON/SSE → Framer → User
```

LangGraph `StateGraph` is approved for typed state, explicit conditional routing, resumable questionnaire interactions, bounded retries, and inspectable transitions. The graph is a deterministic workflow around bounded model-assisted nodes, not an autonomous agent loop.

## Decision-control model

| Category | Examples |
| --- | --- |
| Deterministic | Request validation, urgent-policy overrides, questionnaire completeness, generic-profile application, DCMFNet invocation eligibility, `[0.0, 1.0]` output gating, percentage presentation, citation identity checks, disclaimer/bias-indicator checks, retry limits, graph transitions after typed results |
| Model-assisted and bounded | Local fine-tuned encoder intent classification, scientific query rewriting, evidence relevance grading, cited explanation generation |
| Prohibited | LLM risk calculation or formatting, LLM-selected arbitrary graph branches, invented questionnaire values, combined probabilities, unapproved risk bands, fabricated citations, diagnosis, unsupported causal attribution, uncontrolled search loops |

## Final graph state, nodes, and routes

### Typed state

`ClinicalRiskGraphState` contains only these categories:

- request metadata: deployment mode, request kind, monotonic deadline, policy/config versions, and volatile request ID;
- authorization: signed-session validity, route origin, assessment-view authorization, allowed tool set, and remaining quota class;
- safety/language/intent: one typed decision from each completed gate plus classifier/calibration provenance;
- questionnaire: requirements availability/version, volatile answer map only when a compatible contract exists, validation result, missing/invalid field IDs, and generic-profile provenance;
- inference: immutable positive and negative `InferenceResult` objects or one typed inference failure; never a mutable combined score;
- retrieval: minimal normalized `RetrievalQuery`, attempt statuses, immutable `EvidenceResult`, and corpus/index versions;
- context: `StructuredExplanationContext` assembled only from validated fields;
- generation: one unvalidated structured draft, validation error codes, and retry count `0|1`;
- terminal: one validated response, fixed deterministic response, or typed safe error;
- lifecycle: created/activity/expiry monotonic times, cancellation flag, and purge-required flag.

Raw HTTP headers, network addresses, credentials, model logits, complete feature vectors, and standard-log payloads are not graph state. Sensitive state is memory-only, expires after exactly 30 minutes of explicit-user inactivity, and is purged on reset, crisis interception, terminal failure requiring purge, or process exit.

### Nodes

1. `validate_transport_and_session` validates request union, size, origin, signed anonymous session, quota class, deadline, and deployment mode. It has no model or scientific tools.
2. `intercept_safety` applies deterministic rules, then the bounded local safety classifier when required. A terminal or uncertain critical result routes to fixed content and denies every tool.
3. `detect_language` handles free text only and returns supported, unsupported, or uncertain English. It has no other tool permission.
4. `classify_intent` applies deterministic structured-route rules and the calibrated local intent classifier. It cannot inspect questionnaire completeness or call tools.
5. `select_route` is deterministic and maps typed decisions plus request kind to one subgraph.
6. `load_questionnaire_requirements` loads a versioned ML-approved contract or returns `questionnaire_contract_unavailable`. The current product copy includes aligned ranges and source-derived UI descriptions, but is not yet an inference contract because the missing column codebook prevents verification of exact integer mappings and transformations.
7. `validate_questionnaire` validates all visible values only after a compatible contract exists; it cannot impute, infer, or transform answers without an explicit source-codebook mapping.
8. `apply_generic_profile` reads only the selected artifacts' approved medians for the 20 hidden fields and produces the exact 105-field machine input.
9. `invoke_dcmfnet` calls only the positive and negative predictors after all assessment authorization invariants pass.
10. `validate_and_present_results` checks finite inclusive `[0,1]` values and creates deterministic display percentages or the fixed internal-variance failure.
11. `build_retrieval_query` creates minimal scientific search terms without the questionnaire, feature vector, identity, session ID, or raw probability.
12. `retrieve_evidence` executes local hybrid retrieval, independent lexical fallback, and at most one live PubMed escalation according to typed outcomes.
13. `build_structured_context` combines only validated purpose, immutable result blocks, eligible evidence, provenance, and required limitations.
14. `generate_structured_draft` invokes the selected local LLM once and emits the structured claim schema; it has no direct tool bindings.
15. `validate_response` performs deterministic score, citation, claim, safety, disclosure, and leakage checks and may authorize one bounded regeneration.
16. `render_terminal_response` emits fixed JSON or validated SSE blocks only. Raw model tokens are never emitted.
17. `purge_volatile_state` cancels work and wipes the sensitive state categories required by expiry, reset, crisis, disconnect, or failure policy.

### Routes

- Any terminal safety result routes directly to `render_terminal_response`, then `purge_volatile_state` when required.
- Unsupported or uncertain language routes to the fixed language response with no tools.
- Conversational `risk_assessment` routes to fixed assessment redirection; it never enters questionnaire validation or inference.
- Structured questionnaire update routes to requirements and validation only. A complete authorized submission continues through generic-profile assembly and both DCMFNet calls.
- `explain_my_risk` requires an unexpired immutable prior result, then retrieval, context, generation, and validation. Missing result routes to assessment redirection.
- `scientific_question` and `mental_health_education` route to retrieval, context, generation, and validation without DCMFNet.
- General conversation may route to constrained generation without scientific claims; unsupported medical scope uses fixed minimal content.
- Prescriptive, diagnostic, third-party, minor, emergency, crisis, and acute-distress decisions never enter ordinary intent, RAG, generation, or inference routes except the separately approved diagnosis-to-general-education handoff with all personal context removed.
- Any expired deadline, quota, capacity, budget, provider, or validation terminal condition routes to its typed safe error and starts no new downstream work.

### Tool permissions

- Safety, language, intent, validation, rendering, and purge nodes have no arbitrary tool access.
- `invoke_dcmfnet` may call exactly two pinned local predictors and only from the authorized assessment route.
- `retrieve_evidence` may call the local Qdrant corpus, independent BM25 index, PubMed E-utilities, and bibliographic/retraction verification adapters. It cannot access arbitrary web pages or user stores.
- `generate_structured_draft` may call only the pinned local generator adapter. It cannot call DCMFNet, retrieval, network, filesystem, or session tools.
- No LLM output can add a permission, route, intent, questionnaire value, citation, source, or tool invocation.

## Hybrid intent routing

Use a pre-intercepted, English-only intent router:

1. The separate safety interceptor has already produced `ALLOW_NORMAL_PROCESSING`; terminal safety and clinical-refusal categories never reach this router.
2. A local language gate accepts supported English or returns a fixed English-only response for unsupported/uncertain free text. It cannot authorize tools. Structured questionnaire payloads bypass language detection but remain schema- and safety-gated.
3. Deterministic rules recognize structured questionnaire submissions, explicit assessment commands, and clearly unsupported transport/content cases.
4. A locally hosted Hugging Face sequence-classification encoder classifies remaining English free text into the approved intent enum.

The approved architecture baseline is [`distilbert/distilbert-base-uncased`](https://huggingface.co/distilbert/distilbert-base-uncased), fine-tuned separately for the fixed project intent labels and safety labels. A base checkpoint, zero-shot classifier, or uncalibrated artifact is not approved for release.

The encoder returns logits only. A deterministic adapter maps logits to the fixed enum, applies calibration and the initial `0.85` maximum-confidence threshold, and returns intent, calibrated confidence, clarification requirement, policy-compatible rationale code, model ID, pinned revision/checksum, fine-tuning dataset/version, calibration version, and router version. It does not determine questionnaire completeness, emit user prose, or select tools. Confidence below `0.85`, out-of-distribution input, or unresolved incompatible intent returns the deterministic two-action `INTENT_CLARIFICATION_REQUIRED` component without RAG, LLM, or inference. Safety uncertainty remains governed by the earlier fail-closed safety interceptor.

The evaluation compares deterministic rules with fine-tuned English DistilBERT on one versioned English dataset containing standard and Indian English usage, paraphrases, misspellings, indirect requests, multi-intent cases, out-of-scope medical questions, and adversarial prompt injection. Report per-class precision/recall/F1, macro-F1, confusion matrices, expected calibration error, abstention coverage, out-of-distribution behavior, English-usage slices, memory use, and CPU latency. The language gate has a separate dataset for supported English, English medical terms, short/ambiguous text, and unsupported non-English/code-mixed rejection. Production use of the initial `0.85` intent threshold requires measurable calibration and per-class quality evidence; the concrete local language-identification implementation and its thresholds remain pending evaluation.

## LangGraph composition

### Assessment subgraph

```text
initialize assessment
→ load questionnaire requirements
→ collect and validate manual answers
→ apply generic_genetic_profile_v1
→ confirm machine-input completeness
→ invoke positive and negative DCMFNet predictors
→ build deterministic display results
→ optionally retrieve explanatory evidence
→ build structured context
→ generate and validate response
```

`generic_genetic_profile_v1` reads artifact-provided training medians for the 16 PRS and four batch-by-PC fields. Its generic/unmeasured provenance travels through state, context, UI, and response validation. It is never adjusted from family history or population descriptors.

Framer marks every approved manual field required and disables submission until those visible fields are locally valid, while presenting missing/invalid-field feedback. The backend ignores client completion claims, independently validates the manual values, adds the approved generic profile, and confirms the complete exact 105-variable matrix before inference. Users do not manually fill generic-profile variables.

Conversational `risk_assessment` intent does not enter this subgraph. It returns deterministic `ASSESSMENT_REDIRECTION` with the fixed approved copy and `Launch Research Questionnaire Router` action. Only that action can initialize the structured assessment state, and only a later complete form submission can reach the subgraph's inference node.

The two raw model values remain immutable inside the protected volatile inference boundary. Before presentation or LLM context construction, a deterministic gate requires each value to be finite and within inclusive `[0.0, 1.0]`. A value below `0.0` or above `1.0` triggers a typed fail-closed internal-system-variance event; it is not clamped or displayed as an estimate. The UI displays exactly `Error: Unable to compute estimate due to an internal system variance. Please try again later.` The raw failing value exists only in the protected request object until teardown and never reaches persistence, standard logs, or the public response.

Every valid result view includes the required synthetic-data indicator. The system performs prediction, not causal inference. Until validated feature importance exists, the application inserts: `This is a prediction, not a causal explanation. The model evaluates all 105 inputs together; no single answer can be identified as the cause of the result. Validated feature importance is not available for this result.`

### Risk-explanation subgraph

```text
load immutable assessment result
→ construct a literature query from approved non-sensitive context
→ run scientific RAG
→ build context separating model output from evidence
→ generate explanation
→ validate probability, claims, citations, and disclaimer
```

No feature importance is reported unless the separately validated SHAP contract is approved later.

### Scientific RAG subgraph

```text
classify query scope and recency need
→ normalize/expand scientific query
→ retrieve local dense/hybrid candidates
   ├── eligible candidates → continue
   └── zero match or vector failure → deterministic BM25/keyword fallback over independent lexical index
→ fuse and rerank
→ grade evidence
   ├── sufficient → context builder
   ├── weak → one bounded rewrite and retrieval attempt
   ├── live search allowed → scientific search adapters
   └── unavailable → explicit no-evidence result
```

### Education/conversation subgraph

General mental health, genetics/environmental risk factors, and diet/lifestyle/diabetes/physical-health education use approved scientific RAG. Diet, diabetes, lifestyle, and physical-health questions never invoke DCMFNet.

Medication or treatment questions use RAG only for a general summary related to schizophrenia or another mental-health disorder. Responses never give individualized selection, prescribing, dosage, or medication-change instructions and direct the user to a psychiatrist, appropriate doctor, psychologist, or other qualified mental-health professional according to the question.

Unrelated general medical questions take a minimal out-of-scope path: at most one or two high-level lines plus direction to an appropriate healthcare professional. They do not invoke DCMFNet or the full RAG workflow. Non-medical conversation may use direct generation under the response policy.

### DCMFNet authorization gate

Only the structured-assessment route in the LangGraph assessment subgraph can invoke DCMFNet, and only after the user launches the questionnaire, submits a complete valid form, and passes route, session, safety, and questionnaire validation. Chat intent alone never authorizes inference; the conversational graph has no DCMFNet tool binding. Educational discussion does not authorize inference. Risk explanation uses the stored immutable result and RAG without rerunning the model; a new calculation requires another structured submission.

### Unsupported or urgent-content subgraph

The safety interceptor runs before the intent router and returns a typed terminal result for `EMERGENCY_REDIRECTION`, `CRITICAL_SAFETY_REDIRECTION`, `ACUTE_DISTRESS_REDIRECTION`, `STATE_INELIGIBLE_MINOR`, `THIRD_PARTY_REFUSAL`, `DIAGNOSTIC_REFUSAL`, or `PRESCRIPTIVE_REFUSAL`. Priority follows that order. Exact rules plus a separately evaluated local classifier may detect safety cases; a critical or uncertain positive fails closed.

Emergency, crisis, acute-distress, minor, and prescriptive routes return versioned local scripts without invoking RAG, DCMFNet, or the LLM. Diagnostic refusal may hand off only a separately requested population-level question to the isolated scientific-RAG path. Third-party health data is rejected rather than anonymized by deleting relational wording. Any educational handoff receives no questionnaire, probability, attribution, third-party, or personalized conversation context.

Self-harm interception cancels any active generation, discards unvalidated output, clears operational chat context, and emits `CRITICAL_SAFETY_REDIRECTION` with no raw message or identity. Emergency and crisis UI uses configuration-backed India resources with source and last-verification metadata. Stale or missing required resource configuration fails readiness. Fixed content, including Tele-MANAS (`14416` or `1800-89-14416`), Vandrevala Foundation (`+91 9999 666 555`), and emergency number `112`, is never fabricated or altered by the LLM.

## Approved adaptive RAG architecture

### Ingestion

```text
approved bibliographic discovery adapter
→ 20-year, source-class, DOI/PMID, and license eligibility check
→ parse and normalize
→ DOI/PMID and metadata reconciliation
→ exclude preprints, theses, local PDFs, general websites, and failed quality appraisals
→ deduplicate and verify version/correction/retraction state
→ section-aware parent/child chunking
→ dense and sparse representation
→ versioned Qdrant index
→ ingestion audit report
```

Eligible material is limited to peer-reviewed journal articles, PubMed-indexed literature, DOI/PMID-bearing publications discovered through the configured authority allowlist, and DOI/PMID-bearing clinical guidelines. Every source must fall inside the rolling 20-year window and have a resolvable DOI or PMID. Preprints, theses/dissertations, curated local PDFs, general websites, retracted material, and studies that fail the versioned design-appropriate quality appraisal are hard-excluded before indexing. Authority domain or a locally available file is not an eligibility signal.

Incremental ingestion runs every two weeks and publishes new corpus, vector-index, and lexical-index versions plus an audit report for additions, changes, exclusions, and deduplication decisions. An automated bi-weekly (every-two-weeks) retraction-scrubbing job checks the entire active DOI/PMID set through PubMed retraction/correction metadata and/or another approved active retraction index. On detection it immediately deactivates deprecated or retracted records, purges their chunks/vectors and lexical/BM25 postings from active retrieval and the context window, invalidates related caches, publishes new index versions, and retains a non-retrievable audit tombstone. Records with retraction verification older than 14 days become ineligible for new answers until rechecked; job failures alert operators rather than recording a successful check.

Use child passages for precise retrieval and larger parent sections for generation context. Prefer scientific section boundaries—abstract, methods, results, discussion, limitations, and recommendations—over blind fixed-character chunks.

Every chunk retains document ID, chunk ID, parent ID, title, authors, required DOI/PMID, source/journal, publication date, section, stable locator, source type, study design/evidence tier, peer-review or indexing status, issuing authority when applicable, quality result and rubric version, retraction/correction state and last-check time, corpus version, and ingestion version. Missing required eligibility metadata makes the record ineligible and is never inferred by the LLM.

### Retrieval

Run dense semantic and sparse lexical retrieval in parallel, merge candidates using Reciprocal Rank Fusion, and rerank the fused candidates with a biomedical cross-encoder or late-interaction model. Apply source eligibility and minimum semantic relevance as hard gates before returning evidence.

Metadata reranking prioritizes relevant candidates in this order: clinical guidelines; systematic reviews/meta-analyses; randomized controlled trials; observational studies; expert opinion. Within a tier, newer evidence ranks ahead of older evidence and stronger quality-appraisal results break remaining ties. The result records hierarchy, recency, quality, model relevance, and final reranking contributions. Hierarchy and recency never rescue an irrelevant or otherwise ineligible source.

#### RAG vector guardrails

The scientific corpus is disconnected from patient-specific state. Questionnaire tokens, the 105-input token matrix, feature vectors, inference payloads, session identifiers, and user identity are never embedded or stored in the document vector index. General mental-health publications occupy an isolated collection or namespace. Before vector search, mandatory metadata filtering requires `data_class=scientific_publication`, `document_scope=general_mental_health`, and `contains_patient_data=false`; absent or mismatched metadata fails closed. Retrieval queries use only the minimum approved non-sensitive context.

The index lifecycle includes automated retraction scrubbing every two weeks. It verifies every active PMID/DOI through PubMed and/or another approved active retraction index, immediately purges a newly deprecated or retracted record from active vector and lexical/BM25 namespaces and the context window when detected, invalidates caches, versions both indexes, and preserves only a non-retrievable audit tombstone.

Qdrant is the approved dense/sparse search engine because it supports named dense and sparse vectors, metadata filtering, hybrid fusion, and reranking-oriented retrieval. The portfolio deployment uses a versioned non-user corpus snapshot baked into the backend image or mounted read-only; questionnaire, session, query, and inference state are never written to Qdrant. A separately available versioned BM25 index remains the outage fallback rather than sharing Qdrant's failure boundary.

Resilience requires a lexical path that does not share the vector service's availability boundary. A versioned BM25/keyword index is built from the same eligible corpus and exposed through the retrieval port. When dense/vector retrieval fails or returns no eligible match, deterministic English tokenization plus an approved synonym/abbreviation map queries this independent lexical index once. The fallback repeats all scientific/non-patient metadata, DOI/PMID, date, quality, retraction, authority, relevance, conflict, and source-cap gates. Raw or derived query terms remain volatile and are not logged.

A successful fallback returns normal `EvidenceResult` items with `retrieval_mode=keyword_fallback`, lexical scores, corpus/index versions, and full citation provenance. Only dual success-with-zero-results becomes `NO_ELIGIBLE_EVIDENCE`; failure of both approved paths becomes `RETRIEVAL_UNAVAILABLE`. Keyword matching is a retrieval mechanism, not permission to use general websites, bypass eligibility, cite model memory, or generate without evidence.

Embedding and reranking models are not selected yet. The RAG Engineer should benchmark at least two biomedical embedding candidates and two reranking configurations against a labeled project dataset instead of selecting by popularity.

### Federated scientific search

Proposed adapters:

- Local approved Qdrant corpus for reproducible, low-latency retrieval.
- PubMed through NCBI E-utilities for live scientific discovery and recent literature.
- Crossref for DOI and bibliographic metadata reconciliation.
- PMC or another approved open-access path for eligible DOI/PMID-bearing full text; locally curated PDFs are prohibited.
- Versioned authority-domain discovery limited initially to `*.who.int`, `*.cdc.gov`, `*.nih.gov`, `*.nhs.uk`, and configured Indian health-ministry/public-health domains under `*.gov.in`.

NCBI documents the supported PubMed E-utilities interface in its [E-utilities guide](https://www.ncbi.nlm.nih.gov/books/NBK25497/). Crossref exposes publication, DOI, licensing, correction, and other scholarly metadata through its [REST API](https://www.crossref.org/documentation/retrieve-metadata/rest-api/).

The search policy returns one of `local_only`, `local_then_live`, `live_required`, or `unsupported`. It must be deterministic after typed scope/recency facts. Live results pass the same source-class, 20-year, DOI/PMID, quality, and retraction gates as the local corpus. General web search is prohibited. Authority URLs must match the versioned allowlist after redirects and canonicalization; domain match alone never bypasses DOI/PMID or quality requirements.

### Evidence gate

An evidence result distinguishes:

- sufficient eligible evidence
- no sufficiently relevant evidence
- conflicting evidence
- unsupported scope
- retrieval/search unavailable
- invalid or incomplete source metadata

One controlled query rewrite and one live PubMed escalation are the approved maximums per request. Failure never produces fabricated evidence or a substitute citation.

For `conflicting evidence`, preserve representative eligible sources for each materially supported position. The generated answer must label the controversy, summarize and cite both sides, state relevant hierarchy/recency/quality limitations, and must not choose or imply a winning conclusion. For every status, citation IDs may be created only from evidence returned by that retrieval operation.

After eligibility and metadata reranking, the context builder injects at most the configured number of distinct sources per generation cycle. The cap is an integer from 3 through 5 and defaults to 5; fewer sources are permitted when the evidence gate returns fewer eligible high-relevance results. Multiple chunks from one publication count as one source. Conflict-aware selection must represent each materially supported side within the cap or return a limitation instead of a one-sided answer.

## Structured Context

Pass only validated information needed for the current response:

- approved response purpose and intent
- exact raw DCMFNet result when applicable
- validated display representation
- target/artifact identity
- `generic_genetic_profile_v1` disclosure
- eligible evidence excerpts and immutable citation IDs
- evidence-display metadata containing retrieval-owned exact matched strings and DOI/PMID
- optional validated local feature-importance JSON containing exactly the top three SHAP values
- model, corpus, and research limitations
- safety and response requirements

Exclude the full questionnaire, raw feature vectors, unrelated conversation history, internal prompts, and disallowed source text. The LLM receives no formula or authority to recalculate probabilities.

By default, the LLM receives no individual feature-importance data and cannot rank inputs or explain why a result is high.

A future SHAP adapter remains disabled until locally validated and approved for DCMFNet. For the exact inference result, it may pass only validated JSON containing the top three localized SHAP values and required provenance. The LLM may describe how those inputs influenced the model estimate relative to its baseline. It cannot describe them as causes of a clinical outcome. Clinical relevance requires separate inline-cited medical evidence. Alternative feature-importance methods require their own versioned contracts.

### Prompt and structured-output contract

The system prompt contains behavior, tool-denial, scope, citation, and output-schema instructions only. The developer/context message carries typed immutable blocks. Retrieved text is delimited as untrusted evidence content and cannot override instructions. User text is never concatenated into system or developer instructions.

The generator returns one object with:

- `response_kind` from the approved response enum;
- `claims`, each containing a stable draft-local claim ID, plain-language text, claim type, and one or more current evidence IDs for every medical/scientific claim;
- optional `result_explanations`, separately keyed by exact positive or negative target identity and referring only to the supplied display value;
- `limitations` selected from approved limitation IDs;
- `disclaimer_ids` and `bias_indicator_id`;
- `follow_up_actions` from an allowlisted action enum.

The generator cannot emit bibliographic metadata, raw probabilities, new evidence IDs, HTML, executable content, tool calls, questionnaire values, or free-form policy fields. Citation display records come from retrieval, and percentage display blocks come from deterministic presentation code. Schema failure is a validation failure, not an invitation to parse prose heuristically.

## LLM and prompt architecture

Use a provider-neutral gateway around an English-capable model hosted inside the approved backend, with explicit capabilities for structured output, bounded tool calling, timeouts, retry classification, and model/version metadata. Deterministic fakes are test fixtures only; offline user mode never generates an answer or estimate.

Prompts contain behavior and formatting instructions, not hidden scientific facts. Structured response fields include prose claims with explicit inline citation IDs, positive-probability explanation, negative-probability explanation, limitations, deterministic causal block when required, disclaimer, and safe follow-up options. Evidence-display records remain retrieval-owned UI data and are not generated into the response prose.

Every factual medical or scientific claim requires an inline citation mapped to current verified retrieval metadata. The LLM may discuss a feature association only when the exact retrieved text for the current query explicitly supports it; it cannot synthesize uncited correlations, pathways, mechanisms, epidemiological links, or other extrapolations. Model attribution and literature association remain separate concepts.

The immutable DCMFNet number is a typed tool-result display with artifact provenance, not a literature-backed claim. It receives no paper citation that could imply individual validation; all medical/scientific interpretation around it remains subject to claim-level citation enforcement.

Use low-variance generation settings for clinical-research explanations. One bounded regeneration is allowed only after a typed validation failure; the retry receives non-sensitive failure codes and the same immutable context without permission to change model values or citation identity.

## Response validation

Before returning an answer, deterministic validation checks:

- exact raw-value and target preservation
- approved deterministic display mapping
- separate positive/negative presentation and no combined score
- no unapproved risk bands
- generic-genetic-profile disclosure
- required research-only disclaimer
- every citation ID exists in the current evidence result
- every factual medical/scientific claim has an unambiguous inline citation to current evidence
- no new bibliographic metadata appears
- scientific claims are entailed by allowed matched text rather than speculative extrapolation
- distinct injected sources do not exceed the configured cap of 3 through 5
- raw matched excerpts are absent from response prose and present only in evidence-display records
- conflicting-evidence responses represent each materially supported position without selecting one
- no diagnosis, treatment directive, certainty claim, causal claim, or unsupported feature-importance statement
- no feature-importance explanation without a successfully validated SHAP object bound to the current result
- any attribution object contains exactly the top three unmodified localized SHAP values and required provenance
- the deterministic prediction-only text is present whenever validated feature importance is absent
- no questionnaire or feature-vector leakage

Subjective evidence-support checking may use a bounded secondary model-assisted grader, but it cannot override deterministic failures. A citation failure rejects its entire factual claim block, never just the citation marker. The block may be omitted only if the remaining validated response is complete, coherent, and fully cited; otherwise the whole generation is rejected. A second invalid generation returns the typed generation-unavailable response.

## Deterministic workflow failure behavior

- `INTENT_CLARIFICATION_REQUIRED` renders `I didn't quite catch that. Please select what you would like to do:` plus `Submit Risk Assessment Questionnaire` and `Ask About Schizophrenia & Clinical Associations`. The first launches but does not submit the questionnaire; the second requests a new English scientific question. Neither reuses the ambiguous text or authorizes a tool.
- Out-of-range/non-finite predictions, input/schema errors, and artifact/configuration failures are never retried. The invalid-probability path immediately returns the existing internal-system-variance message. Only an allowlisted transient worker/execution failure before a result exists may retry once with the same volatile validated vector, target, artifact, and idempotency key.
- After two transient execution failures, return `System Note: The model failed to compute your specific risk estimation at this time. You may attempt to re-submit your parameters if you wish.` with no estimate or generated explanation.
- Dense/vector zero-match or failure first invokes the independent deterministic keyword/BM25 fallback. `NO_ELIGIBLE_EVIDENCE` follows only when both paths complete with no eligible evidence; `RETRIEVAL_UNAVAILABLE` follows only when no approved retrieval path can complete. These and `GENERATION_UNAVAILABLE` remain separate terminal states and never authorize pretrained-knowledge synthesis.
- If a valid result already exists when RAG or generation fails, the UI may retain the deterministic result and show the target-aware assessment fallback. A standalone scientific question never receives a risk-result fallback.
- `ticket.jsonl` and other user-bearing failure files are prohibited. Only sanitized `OperationalFailureEvent` fields—coarse time/latency buckets, component/operation/error codes, retry count, deployment mode, and version identifiers—may reach standard operational telemetry. Raw stacks, locals, query strings, questionnaire/target metrics, probabilities, evidence, and session/user/network identifiers remain excluded.

## State, privacy, and observability

Use cryptographically random opaque session IDs behind a memory-only state port. The inactivity TTL is exactly 30 minutes and is independently enforced by client and server; background polling and keep-alives do not renew it. Expiry, explicit reset, process restart, and crisis context clearing invalidate the ID, cancel active work where possible, wipe all volatile questionnaire/conversation/result state, clear the short-lived application session credential, and return the UI to `/`. The UI clears synchronously and sends an idempotent backend purge without waiting to reset its view. Multi-instance hosting may use session affinity but cannot add a persistent shared session store.

Raw text, questionnaire/token/vector data, model inputs/results, probabilities, personalized prompts/responses, and session history exist only in volatile client/backend memory. They never enter databases, files, browser storage/cache, URLs, cookies, backups, crash dumps, APM, logs, traces, analytics, or caches. Sensitive HTTP responses use `Cache-Control: no-store`; deployment disables body capture and core dumps and prevents plaintext swap/hibernation recovery.

Runtime observability uses allowlisted non-sensitive status/version fields, latency/coarse-time buckets, and aggregate counters only. No sensitive audit database exists in `prototype_demo`. Product analytics, if enabled, persist only pre-aggregated unlinkable counters and duration buckets; no session-level event row is retained, and crisis counts use minimum aggregation/disclosure thresholds.

### Required runtime monitoring

The production dashboard and alerts must monitor these aggregate, non-user-bearing metrics:

- accepted requests, successful terminal responses, and safe terminal errors;
- end-to-end latency and each major stage—queue wait, cold start/model load, transport/questionnaire validation, generic-profile assembly, positive-model inference, negative-model inference, retrieval, generation, response validation, and SSE delivery—reported as p50, p95, p99, and maximum with cold and warm runs separated;
- timeout count/rate, requests approaching the 60-second deadline, disconnect/cancellation count, and work cancelled after disconnect;
- HTTP `429` rate-limit count/rate, session-quota exhaustion, global daily-quota exhaustion, capacity/load-shedding rejection, budget-exhaustion rejection, and Modal `503` cold-start/unavailable responses as separate categories;
- questionnaire validation failures, artifact-load failures, inference exceptions, retry count/rate, non-finite or out-of-range model outputs, RAG no-evidence results, retrieval outages, generation failures, and response-validation failures by stable error code;
- current and peak HTTP concurrency, CPU-heavy-job concurrency, container count, cold-start frequency, CPU utilization, memory high-water mark, and process/container restart count;
- model, artifact, corpus, index, prompt, policy, and deployment versions attached only as bounded dimensions.

Initial operational objectives are: every accepted controlled request reaches `done` or safe `error` within 60 seconds; warm DCMFNet inference for both targets has p95 below 500 ms; warm questionnaire-to-deterministic-result latency without RAG has p95 below 2 seconds; timeout rate remains below 1%; internal inference failure rate remains below 0.5%; and non-finite/out-of-range output count remains zero. These values are initial alert/release objectives and must be revised from measured deployment evidence rather than hidden tuning.

Rate-limit, quota, capacity, and budget rejections are monitored availability events, not model-inference failures. Dashboards must show their denominators and counts separately so load shedding cannot make inference reliability appear better or worse.

Per-request raw values may be timed and validated in volatile memory, but raw predictions, questionnaire values, interval endpoints, session IDs, network identifiers, and per-user event rows are never persisted. A user-level `95%` uncertainty display would be a calibrated prediction interval, not a monitoring confidence interval. It remains disabled until a held-out calibration dataset and approved interval method—preferably conformal prediction—demonstrate coverage for each target. The runtime must not derive an interval from arbitrary constants, cross-user production data, MC dropout alone, or `±1.96` without a validated error model.

Raw runtime payloads never go to public LLM, embedding, moderation, tracing, or analytics APIs. Models run in the approved Modal backend. User-bearing requests use only a Modal Server or another endpoint type whose current documentation states that payloads are not stored; ordinary Modal Function invocation, `.remote`/`.spawn`/`.map` user payloads, request-body logs, user-state snapshots, and Modal Dict/Queue/Volume persistence are prohibited. Compute and routing are pinned to `ap-south`, payloads stay below the provider's regional-routing limit, and provider behavior is reverified before release. Modal edge processing and non-sensitive platform-log/metadata residency remain explicit limitations; incompatible India data-fencing fails readiness. Bibliographic APIs receive only system-generated non-sensitive search terms, never raw user queries. LangSmith and external analytics are permitted only for synthetic/offline evaluation fixtures, never live user runtime data.

The public schema has no attachment/file-upload variant and backend routes reject multipart payloads. Scientific corpus ingestion remains an operator-only offline process.

## Framer and Modal deployment behavior

Framer owns presentation only. It calls the Modal-hosted FastAPI contract using typed JSON and validated SSE, holds questionnaire/session state only in volatile memory, and never contains model/provider credentials. The backend applies narrow CORS/origin policy, short-lived signed session credentials, request-size/rate/concurrency controls, and server-side secrets through `modal.Secret`. Modal-specific code remains in a deployment adapter so changing hosts does not change domain contracts or the Framer payload schema.

For conversational RAG, SSE emits `status`, `validated_content`, `evidence`, `done`, and `error`. Raw LLM tokens never cross the public boundary: complete output or claim-sized blocks pass response validation before emission. Fixed safety, language, and questionnaire-redirection results need no model generation and may return typed JSON or a terminal SSE event. Responses use `Cache-Control: no-store`; heartbeats do not renew the 30-minute TTL, disconnects cancel work where possible, and sensitive replay storage is prohibited.

The Modal deployment is CPU-only, sets zero minimum containers, and uses a measured short scale-down window. The workspace spend limit is `$0` out of pocket and the usage budget is limited to available monthly credits; hitting either limit disables model-backed operations until the next budget window. This can operate within Modal's current Starter credits at light portfolio traffic, but it is not a guarantee that 1,000 daily users can all receive model-backed answers for free. Warm deterministic validation and the first progress event target sub-second latency. Cold starts and full retrieval/generation are independently benchmarked and are not described as sub-second guarantees.

The service admits at most 50 active anonymous sessions and at most 50 simultaneous HTTP requests. CPU-heavy generation is separately load-shed at eight concurrent jobs across the deployment until benchmarks justify a higher value. Requests that cannot start and finish inside the 60-second deadline receive a typed capacity response; they do not wait in an unbounded queue.

Approved anonymous limits are 10 model-backed turns per hour and 25 per day per signed session, three assessment submissions per day per signed session, five session creations per hour per transient network-rate-limit key, and a configurable global daily model-backed-operation ceiling initially set to 1,000. Fixed safety, language, reset, health, and static-content responses do not consume model-operation quota. Rate-limit keys are keyed one-way digests held only for the minimum rolling-window lifetime and never enter telemetry or durable storage.

When budget or global daily capacity is exhausted, Framer displays exactly: `This research demo has reached its current usage limit. Assessments and evidence-based answers are temporarily unavailable. Please try again after the displayed reset time. No calculation has been performed.` Existing validated results may remain visible until normal session expiry, but no new inference, retrieval, or generation begins.

When offline or when the backend is unreachable, Framer permits static viewing, volatile form preservation, navigation, and reset only. It blocks RAG, LLM, assessment submission, and DCMFNet and displays `You're offline. Research estimates and evidence-based answers require a connection. No calculation has been performed.` No generic-profile, cached, approximate, or browser-side estimate is permitted.

## Evaluation architecture

Maintain versioned datasets for routing, graph trajectories, retrieval, grounded answers, citations, score preservation, safety/adversarial inputs, and dependency failures.

Compare these retrieval configurations using the same corpus and queries:

| Variant | Portfolio purpose |
| --- | --- |
| Sparse/BM25 only | Lexical baseline |
| Dense only | Semantic baseline |
| Hybrid with RRF | Recall comparison |
| Hybrid plus reranker | Precision comparison |
| Adaptive hybrid plus bounded live search | Proposed deployed architecture |

Measure Recall@k, Precision@k, MRR, nDCG, citation precision/recall, answer groundedness, unsupported-claim rate, router accuracy/macro-F1/per-class metrics, calibration, abstention, graph-path accuracy, latency, token usage, and dependency-failure behavior. Retrieval metrics are reported for primary retrieval, keyword-only fallback cases, and the combined cascade, together with fallback activation, recovery, dual-zero-result, and added-latency rates. On frozen versioned fixtures, intent accuracy and macro-F1 must each exceed `0.85`; every critical safety fixture must take its required route with zero observed false negatives. The dense candidate gate is cosine similarity strictly above `0.85` for the selected normalized embedding artifact, but this model-specific score never substitutes for relevance-labeled evaluation and must be recalibrated when the embedding changes.

Unvalidated first-pass citation-context matching must exceed `85%`, and its unsupported-claim rate must be at most `5%`. Public output remains stricter: citation provenance precision, citation membership, displayed medical/scientific claim support, probability identity, and prohibited-branch checks require a perfect pass rate. One failure is blocked regardless of aggregate model quality. Human review and optional LLM-as-judge are limited to subjective clarity, relevance, and groundedness.

The DCMFNet raw numeric result must preserve exact equality through the backend/public result contract; the separate deterministic percentage presenter may scale and round only for display. End-to-end controlled runs must reach a terminal `done` or safe `error` UI state within `60 seconds`, with cold/warm p50, p95, p99, and maximum reported separately. A timeout is a safe failure, not a successful answer.

Runtime operational reports additionally include timeout, `429`, quota, capacity/load-shedding, budget-exhaustion, `503`, disconnect/cancellation, artifact, inference, invalid-output, retrieval, generation, and response-validation rates with explicit denominators. They report stage-level p50/p95/p99/maximum latency, resource saturation, container restarts, and version dimensions without retaining user-bearing events.

Evaluation runs use synthetic or approved non-user fixtures and publish versioned aggregate CI reports with metric definitions, denominators, environment, and component versions. They never read `ticket.jsonl` or retained production content.

Current evaluation guidance supports separating correctness, relevance, groundedness, and retrieval relevance rather than relying on one aggregate score: [LangSmith RAG evaluation guide](https://docs.langchain.com/langsmith/evaluate-rag-tutorial).

## Approved technology baseline

| Concern | Proposal |
| --- | --- |
| Workflow orchestration | LangGraph `StateGraph` |
| Public API | FastAPI-compatible ASGI app on Modal Server/eligible no-payload-storage endpoint |
| Portfolio UI | Framer code components |
| Streaming | Validated SSE blocks; no raw-token streaming |
| Deployment region | Modal compute and routing pinned to `ap-south` (Mumbai) |
| Secrets | `modal.Secret` or equivalent server-side secret manager |
| Local vector/search engine | Qdrant local/server mode with read-only versioned corpus snapshot; no user data |
| Sparse retrieval | BM25-compatible sparse vectors |
| Failure-resilient lexical fallback | Independently available BM25/keyword index built from the same approved corpus |
| Dense retrieval | MedCPT query/article encoder pair as primary release candidate; PubMedBERT embedding baseline |
| Fusion | Reciprocal Rank Fusion |
| Reranking | `ncbi/MedCPT-Cross-Encoder` primary release candidate; no-reranker baseline required |
| Live scientific search | PubMed E-utilities |
| Bibliographic reconciliation | Crossref |
| Generation | `Qwen/Qwen2.5-1.5B-Instruct` GGUF Q4_K_M primary CPU candidate behind a provider-neutral structured-output adapter |
| Language gate | Meta fastText language identification primary candidate with calibrated English/uncertain thresholds |
| Intent/scope classification | Project-fine-tuned `distilbert-base-uncased`; local Hugging Face sequence-classification adapter |
| Safety classification | Project-fine-tuned DistilBERT classifier plus deterministic critical rules; model can only escalate or abstain |
| Session state | Expiring in-memory LangGraph checkpointer |
| Evaluation | Local deterministic suite plus optional experiment platform |
| Observability | Allowlisted local status/latency/version telemetry; LangSmith only for synthetic offline fixtures |

## Deliberately deferred

- Multi-agent swarm or unconstrained ReAct loop
- Knowledge-graph RAG
- Long-term personal memory
- Autonomous arbitrary-web browsing
- Automated diagnosis, treatment, or medication guidance
- Model-generated questionnaire values or unvalidated/LLM-generated DCMFNet feature importance; the planned local SHAP port remains blocked pending validation and approval
- Clinical decision support, regulated-device claims, or EHR integration; clinician-only hospital silent research remains a separately gated future mode
- Semantic caching of generated medical, scientific, assessment, explanation, or safety responses. The MVP may exact-cache only versioned static content; any future retrieval cache must be non-sensitive, corpus/policy/retraction-versioned, and revalidated on read.

These can be reconsidered only with evidence that they improve an approved requirement enough to justify their complexity and risk.

## Approval and release boundary

The product and architecture decisions in this document are approved. Public release still requires measured evidence, not preference-based substitution:

1. Pin exact model revisions, checksums, runtime versions, and quantized artifacts after the benchmark matrix passes.
2. Resolve the questionnaire machine-mapping gap documented in [`ML_QUESTIONNAIRE_COMPATIBILITY_AUDIT.md`](ML_QUESTIONNAIRE_COMPATIBILITY_AUDIT.md) by supplying the authoritative column codebook or retraining/revalidating the model. Group-level ranges and source-derived UI descriptions are documented, but questionnaire validation returns `questionnaire_contract_unavailable` before DCMFNet until integer direction, recoding, transformations, and missing-value behavior are verified.
3. Calibrate language, intent, safety, retrieval, and BERTScore thresholds on versioned project datasets.
4. Demonstrate the 60-second terminal-state requirement, CPU-only resource ceiling, cold-start behavior, and `$0` spend-limit degradation path under the approved load profile.
5. Reverify emergency-resource content manually every 30 days and automatically test configured links daily. Optional stale helplines are suppressed; the India emergency number and instruction to seek immediate local emergency help remain available from a separately verified fixed bundle.

See [`AI_MODEL_BENCHMARK_REPORT.md`](AI_MODEL_BENCHMARK_REPORT.md) and [`AI_IMPLEMENTATION_HANDOFFS.md`](AI_IMPLEMENTATION_HANDOFFS.md) for the evidence gates and role-specific implementation handoffs.
