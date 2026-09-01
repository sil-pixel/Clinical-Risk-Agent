# AI Architecture Product Requirements

Status: Product-owner input in progress

Owner: Product Manager; consumed by AI Architect

Date started: 2026-08-16

Source of truth: [`Problem Statement.md`](../Problem%20Statement.md)

This document records approved product decisions that constrain the AI, RAG, LangGraph, safety, context, LLM, and response-validation architecture. Pending topics remain open and are not permission for implementation agents to guess.

Working design proposal: [`PROPOSED_AI_ARCHITECTURE.md`](PROPOSED_AI_ARCHITECTURE.md). The proposal is non-binding until the pending decisions below are resolved and the AI Architect publishes an approved design.

## 1. Intended users, product stages, and purpose — approved

- The current project is an AI engineering portfolio and research demonstration for invited testers such as friends, developers, evaluators, and researchers.
- Prototype testers are not treated as patients, and the prototype does not participate in diagnosis, treatment, triage, or care.
- Testers must not use DCMFNet outputs for health or care decisions.
- Every probability experience must communicate uncertainty, research-only limitations, synthetic-data provenance, and that the result is not sufficient by itself for health or care decisions.
- India is the first planned regulatory market.
- The first hospital product is clinician-only and supports silent research validation. It is never patient-facing, and its outputs do not influence care during the silent-validation stage.

### Architecture consequences

- Safety and response validation must enforce the research-only and non-diagnostic framing.
- The LLM and UI must not provide instructions that treat a probability as the sole basis for action.
- Prototype language must be understandable without weakening scientific limitations; technical provenance and exact target identity remain inspectable.
- The initial deployment optimizes for a safely hosted, inspectable demonstration while preserving interfaces needed for a later governed hospital research mode.
- `prototype_demo` and future `hospital_silent_research` are explicit, fail-closed deployment modes. Mode identity must be included in state, result provenance, telemetry, and tests.
- Generic genetic defaults and prototype display mappings are permitted only in `prototype_demo`. They are invalid by default in `hospital_silent_research`.
- Scaling comes from typed ports, replaceable providers/state stores, stateless boundaries, and versioned contracts rather than premature service decomposition.

## 2. Assessment input journey — approved for portfolio MVP

- The assessment experience uses a manual questionnaire for fields that have approved user-facing wording, encodings, ranges, and units.
- The system must visibly report completion and validation errors and must not invoke DCMFNet until every required machine input has an approved provenance.
- A family-history question may be collected only if its purpose and storage are approved, but it must not be converted into or used to increase a PRS value. Family history is not one of the exported model's 105 input fields.
- Nationality, country of origin, ethnicity, race, or self-reported descent must not be converted into genetic principal components. The exported fields are batch-by-PC interaction terms (`batch_1_x_PC1`, `batch_2_x_PC1`, `batch_1_x_PC2`, and `batch_2_x_PC2`) that require the compatible genomic preprocessing and batch context.
- Random genetic values must not be presented as measurements belonging to the user or used to produce a personalized probability.

### Approved generic genetic profile

- The portfolio MVP uses a versioned generic genetic profile for inputs that cannot be collected manually.
- Each of the 16 PRS fields uses its exported training median from the active artifact schema.
- Each of the four batch-by-PC interaction fields uses its exported training median; the current verified schemas define all four medians as `0.0`.
- The positive and negative artifact schemas currently contain identical generic values. Runtime code must still read them from the selected artifact rather than duplicate them as handwritten constants.
- The profile identifier is `generic_genetic_profile_v1` and its provenance must be included in the validated assessment context.
- Generic values are deterministic and independent of family history, nationality, country of origin, ethnicity, race, or descent.
- The UI and LLM must disclose that genetic inputs were not measured from the user and that the output is a questionnaire-based simulated research estimate using generic genetic assumptions.
- The generic profile must never be described as the user's PRS, genetic ancestry, genomic result, or personalized genetic risk.

### Deferred research-data mode

A future mode may accept the 16 PRS values and four batch-by-PC interaction values from a compatible, validated upstream genomic pipeline with provenance. It is outside the current portfolio MVP and must not be implied by the manual questionnaire.

### Scientific and fairness rationale

- A PRS is calculated from genetic variants and has ancestry-dependent validity; family history cannot substitute for the exported PRS vector. See the [National Human Genome Research Institute overview](https://www.genome.gov/Health/Genomics-and-Medicine/Polygenic-risk-scores).
- Genetic principal components are computed from genotype/relationship data and used as population-stratification covariates. See the [PLINK PCA documentation](https://www.cog-genomics.org/plink2/strat).
- Nationality and other social population labels are not interchangeable with genetic ancestry. Population descriptors require explicit scientific justification and transparent use. See the [National Academies guidance](https://nap.nationalacademies.org/resource/26902/interactive/).

## 3. Model-result presentation — approved

- Show the positive-symptom and negative-symptom research risk probabilities separately.
- Present each result as a percentage.
- Retain the exact raw DCMFNet value internally as an immutable value with target and artifact identity.
- Percentage formatting is deterministic application logic, never an LLM calculation.
- Treat any raw probability below `0.0` or above `1.0` as an internal system variance and fail closed. Do not clamp, normalize, convert, or display it as an estimate.
- The UI must display exactly: `Error: Unable to compute estimate due to an internal system variance. Please try again later.`
- The exact out-of-range raw value may be written only to the encrypted, access-controlled audit trail described below. It must never appear in the UI, public API payload, standard application log, trace, metric label, or ordinary observability event.
- Do not introduce low/moderate/high risk bands until scientifically validated thresholds are approved.
- Every valid result requires an explanation and disclaimer; an internal-system-variance response contains no estimate or generated explanation.

### Required explanation

- Identify whether the value is the positive-symptom or negative-symptom probability and explain that category in plain language.
- Keep the model probability distinct from scientific literature retrieved to contextualize it.
- Explain uncertainty and avoid causal claims or unsupported statements about which answers produced the result. The LLM is specifically prohibited from saying or implying `Your risk is X because you answered Yes to question Y.` When users ask how individual answers affected the estimate, use the structured statement: `The model looks at patterns across all 105 inputs collectively; individual answers do not have an isolated linear impact.`
- Disclose use of `generic_genetic_profile_v1` and state that PRS/PCA-related values were not measured from the user.

### Required disclaimer

- Research and portfolio demonstration only.
- Model trained on fully synthetic data and not clinically validated for individual use.
- Not a diagnosis, screening result, medical advice, or replacement for qualified professional judgment.
- The user must not act on the probability alone.
- Generic genetic assumptions mean the result is not a personalized genetic-risk estimate.
- The UI must show a persistent synthetic-data bias indicator stating that models trained on synthetic data may underrepresent real-world clinical comorbidities found in the Indian healthcare ecosystem.

### Presentation architecture consequences

- The inference result remains raw and immutable. A deterministic output gate validates that every probability is finite and inside the inclusive `[0.0, 1.0]` interval before a deterministic result presenter creates any display percentage.
- Structured Context carries both the exact raw value and validated display representation; the LLM may repeat but not derive or change either.
- An out-of-range value triggers a typed, fail-closed internal-system-variance event. Structured Context and the LLM receive no raw value or display estimate for that result; the public response contains only the approved error message.
- Response validation verifies target identity, exact raw-value preservation inside the protected boundary, interval validation, deterministic display mapping for valid values, separate presentation, disclaimer and synthetic-data bias indicator presence, and absence of unapproved risk bands or causal attribution.
- Raw probabilities and questionnaire tokens must never be printed or written to standard application logs, traces, metrics, error payloads, or analytics. They may be written only to an encrypted, access-controlled audit-trail database, associated with a cryptographically random session ID and never with a user identity. Audit access, retention, deletion, and every read/write operation must be policy-controlled and auditable.
- System state, consent capture, audit records, and database schemas must natively support data fencing and localization constraints aligned with India's Digital Personal Data Protection (DPDP) Act. Deployment adapters must fail closed when the active mode cannot satisfy its configured India data-residency, consent, purpose, retention, and access policy.

## 4. Supported conversational and RAG scope — approved

### Supported through scientific RAG

- General mental-health education and scientific questions.
- Genetics and environmental risk factors, with appropriate limitations and no genetic determinism or causal overstatement.
- Diet, lifestyle, diabetes, and physical-health questions as general evidence-based education.
- Scientific context for an existing positive- or negative-symptom model result.

These answers require approved evidence and citation provenance. A diet, diabetes, lifestyle, or physical-health question never invokes DCMFNet.

### Medication and treatment information — narrowly supported

- Only provide a general evidence summary when the question is related to schizophrenia or another mental-health disorder.
- Do not provide individualized treatment selection, prescribing, dosage, medication-start/stop/change instructions, or claims that a treatment is appropriate for the user.
- Tell the user to contact an appropriate qualified professional for details. Medication questions should direct the user to a psychiatrist or other prescribing doctor; psychological-support questions may also direct the user to a psychologist or suitable mental-health professional.

### General medical questions — out of scope

- For unrelated general medical questions, provide at most a one- or two-line high-level response.
- State that the topic is outside this assistant's scope and direct the user to an appropriate doctor or healthcare professional.
- Do not invoke DCMFNet. Do not run the full scientific RAG workflow unless a later safety policy explicitly requires approved informational resources.

### Exclusive DCMFNet invocation policy

DCMFNet may run only when all of the following are true:

1. The approved intent is `risk_assessment`.
2. The user explicitly requests calculation of positive/psychotic-symptom risk or negative/depressive-symptom risk.
3. The questionnaire validator reports a complete, valid model input under the active deployment mode.
4. Input validation and safety allow normal processing.

Discussing psychosis, depression, schizophrenia, symptoms, causes, research, diet, genetics, environment, medication, treatment, or other health topics does not itself authorize inference. Explaining a stored result uses the immutable prior result plus RAG and does not rerun DCMFNet unless the user explicitly requests a new assessment.

### Router and graph consequences

- The Intent Router identifies assessment, explanation, scientific/education, general conversation, and unsupported/unsafe intent; it does not call tools.
- LangGraph enforces the DCMFNet gate and selects the approved RAG, minimal out-of-scope, or safety path.
- Tool authorization is deterministic after validated intent and state. The LLM cannot invoke DCMFNet directly.
- Tests must prove that non-assessment prompts—including adversarial diet, diabetes, medication, and general-medical prompts—cannot reach inference.

## 5. Scientific-source policy — approved

### Eligible sources

A source is eligible only when it was published within the rolling 20-year window measured on the ingestion or live-search date, has a resolvable DOI or PMID, passes the quality and retraction gates below, and belongs to at least one of these classes:

- a peer-reviewed journal article;
- PubMed-indexed literature, excluding disallowed publication types;
- a publication from an explicitly allowlisted authoritative-health domain; or
- a clinical guideline issued or endorsed by a recognized professional or public-health authority.

General websites are prohibited. Authority discovery is restricted to a versioned domain allowlist; the initial allowed patterns are `*.who.int`, `*.cdc.gov`, `*.nih.gov`, `*.nhs.uk`, and approved Indian health-ministry or public-health domains under `*.gov.in`. A matching domain is necessary but not sufficient: the issuing organization must be recognized by configuration, and authority publications and clinical guidelines must still have a DOI or PMID and pass every other eligibility gate. Redirects and canonical URLs must be revalidated against the allowlist. DOI/PMID metadata must be retrieved and reconciled from the source or an approved bibliographic service; it must never be generated or inferred by the LLM.

The following are ineligible: preprints, theses or dissertations, curated local PDFs, general websites, sources older than 20 years, retracted publications, and studies that fail the approved quality appraisal. A local file path, manually uploaded PDF, URL, or organization domain is not evidence of eligibility.

### Quality, retraction, and provenance gates

- Eligibility is a deterministic pre-retrieval and pre-answer gate, not a soft reranking preference.
- The RAG implementation must record source type, peer-review/indexing status, publication date, DOI/PMID, issuing body or journal, study design, quality-appraisal result and rubric version, retraction/correction status, and the timestamps and providers used to verify that metadata.
- Low-quality evidence is excluded using a documented, versioned appraisal appropriate to its study design. A missing or failed required appraisal is ineligible, not silently treated as acceptable.
- Retraction checks run during ingestion and again through an automated bi-weekly (every-two-weeks) scrubbing job using PubMed retraction/correction metadata and/or another approved active retraction index. A newly deprecated or retracted source is immediately deactivated from the active corpus and context window when detected, its vectors/chunks and cached retrieval results are purged, a new corpus version is published, and the action is auditable.
- Evidence whose retraction verification is older than 14 days is not eligible for new answers until it is successfully rechecked. Monitoring failures alert operators and cannot be represented as a clean check.
- A citation may be emitted only for an eligible source actually returned in the current retrieval result. The system must never cite from model memory, a prompt, an unretrieved bibliography, or a rejected candidate.

### Evidence hierarchy and metadata reranking

After hard eligibility filtering and a minimum semantic-relevance gate, metadata reranking applies this hierarchy from highest to lowest:

1. Clinical guidelines.
2. Systematic reviews and meta-analyses.
3. Randomized controlled trials.
4. Observational studies.
5. Expert opinion.

Hierarchy is the primary metadata priority. Within the same evidence tier, prefer more recent publication dates, then stronger quality-appraisal results. Relevance remains mandatory: hierarchy or recency cannot make an irrelevant source eligible. Reranking must retain the hierarchy tier, recency contribution, quality contribution, and final score for audit and evaluation.

When eligible evidence contains a material unresolved conflict, the evidence result is `conflicting_evidence`. The answer must explicitly state the controversy, fairly summarize and cite the evidence on each supported side, describe relevant hierarchy/recency/quality limitations, and not select or imply one disputed conclusion as the answer. Reranking must preserve representative evidence for the conflicting positions rather than allowing one side to disappear solely because of score ordering.

### Corpus lifecycle

- Run incremental ingestion once every two weeks (fortnightly). Discover and process new or changed eligible records, deduplicate by DOI/PMID and version relationships, and publish a versioned ingestion report and corpus/index version.
- Run automated retraction scrubbing every two weeks, including for the complete active corpus, so already-ingested publications can be deactivated when a new retraction or deprecation is detected.
- Preserve tombstone and audit metadata for removed records, but never return deactivated content from the active corpus.

### RAG vector guardrails

- **RAG document disconnecting:** Patient-specific questionnaire tokens, feature vectors, token matrices, inference payloads, and session state must never be embedded, indexed, or stored in the scientific-document vector collection. General mental-health documents use a physically or logically isolated collection/namespace and mandatory metadata such as `data_class=scientific_publication`, `document_scope=general_mental_health`, and `contains_patient_data=false`. Retrieval applies those filters before vector search and fails closed for missing or mismatched metadata.
- Retrieval queries may be derived only from the minimum approved non-sensitive context. They must not contain raw questionnaire tokens, the 105-input matrix, a user identity, or the cryptographic session ID.
- **Automated retraction scrubbing:** The vector-index pipeline verifies all active PMIDs/DOIs against PubMed and/or another approved active retraction index every two weeks. On detection, it immediately removes deprecated or retracted vectors from the active namespace and context window, invalidates caches, publishes a new corpus/index version, and retains only a non-retrievable audit tombstone.

### Architecture consequences

- Live search and local retrieval use the same eligibility, DOI/PMID, quality, date, and retraction gates.
- Retrieval contracts must expose sufficient metadata to enforce and audit source eligibility, evidence hierarchy, recency, quality, conflict state, and citation membership.
- No eligible retrieved evidence produces an explicit limitation; it does not authorize an uncited scientific answer or fallback to general web search.
- System state, consent capture, and database schemas must natively support India-aligned data fencing and localization controls under the DPDP compliance mapping; RAG and audit adapters cannot silently route protected data outside the configured jurisdiction.

## Pending product decisions

6. Evidence and explanation behavior beyond the approved conflict rule
7. Safety and escalation policy
8. Privacy and data lifecycle
9. LLM and deployment constraints
10. Workflow failure behavior
11. Quality targets
