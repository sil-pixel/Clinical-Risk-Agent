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
- The exact out-of-range raw value may exist only in a protected volatile error object for the lifetime of the failed request. It must never be persisted or appear in the UI, public API payload, standard application log, trace, metric label, analytics, crash report, or ordinary observability event; request teardown wipes the object.
- Do not introduce low/moderate/high risk bands until scientifically validated thresholds are approved.
- Every valid result requires an explanation and disclaimer; an internal-system-variance response contains no estimate or generated explanation.

### Required explanation

- Identify whether the value is the positive-symptom or negative-symptom probability and explain that category in plain language.
- Keep the model probability distinct from scientific literature retrieved to contextualize it.
- State the scope plainly: the current system performs prediction, not causal inference. A future validated SHAP tool may report feature importance—which inputs most influenced the model's estimate—but it still will not identify what caused a clinical outcome.
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
- Raw probabilities and questionnaire tokens must never be printed or written to standard application logs, traces, metrics, error payloads, analytics, caches, or any database. For `prototype_demo`, no sensitive audit database is permitted; volatile processing state is wiped on reset, expiry, request failure, or process termination.
- System state and consent handling must natively support data fencing and localization constraints aligned with India's Digital Personal Data Protection (DPDP) Act. Deployment adapters fail closed when the active mode cannot satisfy its configured India processing-location, consent, purpose, access, and zero-retention policy.

## 4. Supported conversational and RAG scope — approved

### Supported through scientific RAG

- General mental-health education and scientific questions.
- Genetics and environmental risk factors, with appropriate limitations and no genetic determinism or causal overstatement.
- Diet, lifestyle, diabetes, and physical-health questions as general evidence-based education.
- Scientific context for an existing positive- or negative-symptom model result.

These answers require approved evidence and citation provenance. A diet, diabetes, lifestyle, or physical-health question never invokes DCMFNet.

### Medication and treatment boundary — refusal for prescriptive requests

- Any drug-specific question, and any request to recommend, select, compare for the user, dose, start, stop, alter, or evaluate a medication or treatment plan, takes the deterministic `PRESCRIPTIVE_REFUSAL` route.
- The fixed refusal directs the user to a registered medical practitioner, psychiatrist, or treating doctor. It does not invoke DCMFNet, RAG, or the LLM.
- Non-personalized questions about treatment research may use scientific RAG only when they are not drug-specific and do not request a choice, dosage, modification, or individualized evaluation. This is a deliberately conservative product boundary, not a claim that Indian telemedicine rules prohibit every form of remote prescribing.

### General medical questions — out of scope

- For unrelated general medical questions, provide at most a one- or two-line high-level response.
- State that the topic is outside this assistant's scope and direct the user to an appropriate doctor or healthcare professional.
- Do not invoke DCMFNet. Do not run the full scientific RAG workflow unless a later safety policy explicitly requires approved informational resources.

### Exclusive DCMFNet invocation policy

DCMFNet may run only from the structured assessment view, and only when all of the following are true:

1. The user has explicitly launched the questionnaire router and submitted the structured assessment form.
2. The questionnaire validator reports a complete, valid model input under the active deployment mode.
3. Input validation and safety allow normal processing.

An assessment request made in chat never authorizes inference. It returns the deterministic assessment redirection defined in Section 9. Discussing psychosis, depression, schizophrenia, symptoms, causes, research, diet, genetics, environment, medication, treatment, or other health topics does not authorize inference. Explaining a stored result uses the immutable prior result plus RAG and does not rerun DCMFNet; a new calculation requires a new structured assessment submission.

### Router and graph consequences

- The Intent Router identifies assessment, explanation, scientific/education, general conversation, and unsupported/unsafe intent; it does not call tools.
- After safety permits normal processing, an English-language gate returns `SUPPORTED_ENGLISH`, `UNSUPPORTED_LANGUAGE`, or `UNCERTAIN_LANGUAGE`. Unsupported or uncertain free text receives the fixed message `Input error: Language unsupported. Please resubmit your query in English.` and cannot reach intent classification, RAG, the LLM, or DCMFNet. Structured questionnaire values bypass language detection but not schema or safety validation.
- Rephrased English questions are handled by a locally hosted Hugging Face sequence-classification encoder fine-tuned on the approved intent labels. The proposed lightweight baseline is `distilbert/distilbert-base-uncased`.
- This component is a bounded encoder classifier, not a generative LLM. It emits logits and a typed `IntentDecision`; application code performs label mapping, confidence calibration, thresholding, and schema validation. It cannot generate prose, select arbitrary tools, or expand the intent enum.
- The base checkpoint is not approved for zero-shot production routing. A project-specific English labeled routing dataset, fine-tuning run, calibration set, pinned model revision/checksum, license review, and release evaluation are required. English DistilBERT is the architecture baseline, not an approval to deploy an unevaluated checkpoint.
- Low-confidence or out-of-distribution non-safety inputs return clarification or the minimal unsupported response. They never authorize DCMFNet. Safety decisions remain the responsibility of the earlier safety interceptor and cannot be weakened by the intent classifier.
- LangGraph enforces the DCMFNet gate and selects the approved RAG, minimal out-of-scope, or safety path.
- Tool authorization is deterministic after validated intent and state. The LLM cannot invoke DCMFNet directly.
- Tests must prove that direct and rephrased English non-assessment prompts—including adversarial diet, diabetes, medication, general-medical, misspelled, indirect, and prompt-injection variants—cannot reach inference. Intent evaluation reports per-class precision/recall/F1, macro-F1, confusion matrices, calibration error, abstention coverage, out-of-distribution behavior, English-usage slices, and CPU latency. Separate language-gate tests cover English medical terminology, short/ambiguous text, and rejection of non-English or code-mixed inputs; rejected languages are not intent-classifier training targets.

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
- Retraction checks run during ingestion and again through an automated bi-weekly (every-two-weeks) scrubbing job using PubMed retraction/correction metadata and/or another approved active retraction index. A newly deprecated or retracted source is immediately deactivated from the active corpus and context window when detected, its vector chunks, lexical/BM25 postings, and cached retrieval results are purged, a new corpus/index version is published, and the action is auditable.
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
- **Automated retraction scrubbing:** The retrieval-index pipeline verifies all active PMIDs/DOIs against PubMed and/or another approved active retraction index every two weeks. On detection, it immediately removes deprecated or retracted vectors and lexical/BM25 postings from active namespaces and the context window, invalidates caches, publishes a new corpus/index version, and retains only a non-retrievable audit tombstone.

### Architecture consequences

- Live search and local retrieval use the same eligibility, DOI/PMID, quality, date, and retraction gates.
- Retrieval contracts must expose sufficient metadata to enforce and audit source eligibility, evidence hierarchy, recency, quality, conflict state, and citation membership.
- No eligible retrieved evidence produces an explicit limitation; it does not authorize an uncited scientific answer or fallback to general web search.
- System state, consent capture, and database schemas must natively support India-aligned data fencing and localization controls under the DPDP compliance mapping; RAG and audit adapters cannot silently route protected data outside the configured jurisdiction.

## 6. Evidence and explanation behavior — approved

### Claim-level citation and grounding

- Every factual medical or scientific claim must contain an explicit inline citation ID mapped to verified metadata for an eligible source returned by the current retrieval operation. Citation coverage is enforced at claim level; a citation attached only to a distant paragraph or bibliography does not cover intervening claims.
- An exact DCMFNet probability is rendered as immutable tool output with model/artifact provenance, not represented as a literature-backed fact. It must not receive a paper citation that implies the source validates the individual's number. Every medical/scientific interpretation surrounding that output still requires claim-level inline citations.
- Speculative, extrapolated, or uncited medical/scientific claims are prohibited. If the current evidence set does not directly support a claim, the claim is removed or the response states that adequate evidence was not retrieved.
- Citation IDs, DOI/PMID, source identity, and matched text come only from the immutable retrieval result. The LLM cannot create, repair, substitute, or cite metadata from memory.
- Each generation cycle receives no more than the configured source cap, which must be an integer from 3 through 5 and defaults to 5. Retrieval may supply fewer sources when fewer eligible, relevant sources exist; it must never pad the context with weak evidence to meet a minimum.
- The context builder selects the highest-relevance eligible evidence after hierarchy, recency, quality, and conflict-preservation reranking. Multiple chunks from one paper count as one source toward the cap and are grouped under one source identity.

### Evidence display

- The response body displays concise claims with inline citation markers, not raw retrieved excerpts.
- Each citation marker opens an interactive, expandable metadata container such as a tooltip or side drawer. That container displays the exact matched text string supplied by retrieval, DOI/PMID, title, authors when available, publication/source, publication date, evidence tier, and retraction-verification state.
- The UI must preserve the exact matched string and citation-to-source mapping; it cannot ask the LLM to regenerate or paraphrase the excerpt. Excerpts remain collapsed by default and are never silently inserted into the prose response body.

### Caching boundary

- Semantic caching of generated medical, scientific, assessment, explanation, or safety responses is prohibited for the MVP. Similar wording does not establish identical intent, safety state, evidence currency, or entitlement to personalized context.
- Versioned static FAQs, fixed refusal/redirection scripts, and other non-generated standard UI content may use exact-key caching by content ID, locale, jurisdiction, and policy version. No raw user text, questionnaire token, probability, identity, or session context may enter a cache key or value.
- Retrieval-result caching, if later implemented, must use only non-sensitive normalized queries and include corpus/index version, eligibility-policy version, and retraction-check freshness in the key. Retraction, correction, corpus, allowlist, or policy changes immediately invalidate affected entries. A cached retrieval result still passes current eligibility and citation validation before use.

### Conflicting evidence

- After metadata reranking, materially opposed eligible evidence produces `conflicting_evidence`. The answer labels the controversy, presents and inline-cites each supported position, describes hierarchy/recency/quality limitations, and does not select or imply a winning conclusion.
- Conflict-preserving selection must represent each materially supported position within the configured 3-to-5-source cap. If fair representation cannot fit or sufficient evidence for one position is unavailable, return an explicit limitation rather than a one-sided synthesis.

### Prediction and future feature importance

- **Current scope:** DCMFNet produces predictions only. The system does not perform causal inference and cannot determine why a clinical outcome occurs.
- **Before SHAP is validated:** The assistant must not rank individual inputs or explain why a probability is high. It returns the deterministic message: `This is a prediction, not a causal explanation. The model evaluates all 105 inputs together; no single answer can be identified as the cause of the result. Validated feature importance is not available for this result.`
- **After SHAP is validated:** A locally executed, approved SHAP adapter may report which inputs had the largest influence on that specific model prediction. This is feature importance, not causal inference. The assistant may say that a feature moved the model estimate up or down relative to the validated baseline; it must not say the feature caused the predicted clinical outcome.
- A feature's clinical relevance may be discussed separately when current retrieved medical literature explicitly supports it and the claim has an inline citation. Clinical relevance must not be inferred from the SHAP value itself.
- The SHAP adapter must bind its result to the exact inference result, target, artifact checksum, feature schema, SHAP background version, method/version, and attribution-run ID. Attention values alone are insufficient. The LLM receives exactly the top three localized SHAP values with stable feature IDs, ranks, signed values, and directions; it cannot alter them.
- Alternative feature-importance methods require separately versioned and approved contracts and must not label their outputs as SHAP.

### Architecture consequences

- Structured generation must separate prose claims, inline citation IDs, evidence-display records, the deterministic prediction-only message, and optional validated feature-importance input.
- Response validation must reject any factual medical/scientific claim without a current inline citation, any citation not mapped to current retrieval metadata, body-level raw excerpts, source-cap violations, invented feature associations, causal claims, or feature-importance statements without the validated runtime object.
- The UI requires an expandable evidence component that renders retrieval-owned exact matched strings and DOI/PMID metadata without passing excerpt rendering through the LLM.
- Evaluation fixtures must cover claim-level citation completeness, citation entailment, source-cap enforcement, excerpt/body separation, conflict representation, association extrapolation, feature-importance gate bypass attempts, top-three JSON integrity, prediction-versus-causation wording, and deterministic prediction-only message presence.

## 7. Safety policy and interception architecture — approved

### Pre-generation enforcement and route priority

- Every free-text input passes through a local, low-latency safety interceptor before intent routing, RAG, DCMFNet, prompt construction, or LLM generation. Exact rules and a separately evaluated local safety classifier may contribute to detection; regex alone is not treated as sufficient coverage.
- A positive or safety-critical uncertain match fails closed. If generation has already started because of a concurrent event, the orchestrator cancels it and discards all unvalidated output.
- Route priority is deterministic: `EMERGENCY_REDIRECTION` or `CRITICAL_SAFETY_REDIRECTION` → `ACUTE_DISTRESS_REDIRECTION` → `STATE_INELIGIBLE_MINOR` → `THIRD_PARTY_REFUSAL` → `DIAGNOSTIC_REFUSAL` → `PRESCRIPTIVE_REFUSAL` → normal routing. A lower-priority route cannot weaken a higher-priority safety action.
- Intercepted responses are versioned local UI content. The LLM cannot compose, paraphrase, translate, or append to them. Safety routes never invoke DCMFNet. Crisis, emergency, acute-distress, minor, and prescriptive routes also never invoke RAG.
- Safety events may exist only in volatile operational memory and contain the minimum category, policy version, coarse time bucket, and outcome needed to execute the route, but no raw text, questionnaire token, probability, identity, or persistent session identifier. Standard logs receive only non-sensitive status codes. Session context is cleared after a crisis hard interception. If crisis counts are retained for product analytics, they are aggregated and unlinkable under Section 8 before persistence; no event-level safety record is retained.

### Possible self-harm or crisis statements

- `CRITICAL_SAFETY_REDIRECTION` is an immediate hard interception with zero LLM generation. It cancels active generation, clears operational conversation context, and emits minimal critical-safety telemetry.
- The prominent modal is accessible, selectable, copyable, and provides click-to-call controls; safety contact information must not be made deliberately difficult to copy.
- Approved India copy:

  > If you or someone you know is in crisis, help is available. You are not alone. Please reach out now to **Tele-MANAS** at **14416** or **1800-89-14416** (free, 24/7), or the **Vandrevala Foundation** at **+91 9999 666 555** (24/7). If there is immediate danger, call **112** or go to the nearest hospital emergency department.

- Helpline names, numbers, availability, jurisdiction, verification source, verification time, and configuration expiry are versioned configuration—not prompt text. Readiness fails closed if required India resources are absent or past their verification expiry. Operators must reverify the configuration on a scheduled basis and may update it without changing prompts.

### Hallucinations, psychosis, or acute distress

- Active delusional framing, severe panic, or acute ungrounded sensory distress routes to `ACUTE_DISTRESS_REDIRECTION`. The response does not validate, invalidate, analyze, interpret, or argue about the reported experience.
- The system renders only this stored script:

  > It sounds like you are experiencing a deeply overwhelming and stressful moment. Because this is an automated research demonstration, I cannot provide the clinical grounding or support you need right now. Please connect with a trusted friend, family member, or a qualified mental health professional immediately.

- Any indication of immediate danger or self-harm takes the higher-priority emergency or crisis route instead.

### Requests for diagnosis

- `DIAGNOSTIC_REFUSAL` prevents diagnostic labels, diagnostic classification, or confirmation about the user or another person, including in structured output fields.
- The response starts with: `I am an AI research prototype and cannot diagnose any medical or psychiatric condition.` If the user also asks for general education and no higher-priority route applies, a separate scientific-RAG response may follow. That response is population-level, does not receive questionnaire, inference, or user-specific context, and is returned only when claim-level citation validation succeeds.

### Medication or treatment recommendations

- `PRESCRIPTIVE_REFUSAL` blocks any drug-specific question, plus recommendations, selection, suitability judgments, dosing, and instructions to start, stop, or modify a medication or treatment plan. It is an intentionally conservative product-safety policy; it must not be described as proof that Indian law prohibits all telemedicine prescribing.
- The system renders only this stored script:

  > I cannot recommend, select, dose, evaluate, start, stop, or change medication or treatment plans. Please consult a registered medical practitioner, psychiatrist, or treating doctor before making any changes.

### Requests to interpret another person's data

- `THIRD_PARTY_REFUSAL` blocks inference or interpretation of another person's questionnaire, symptoms, health information, or model result. Relational wording is not stripped to disguise third-party data, and the data is not processed through `prototype_demo`.
- The system renders only this stored script:

  > I cannot assess or interpret another person's health information. I can provide general, non-personalized education, or that person may choose to use the adult research demonstration themselves.

- General education, when separately requested and otherwise safe, receives no third-party facts, questionnaire state, or inference context.

### Minors

- The product imposes an adults-only use policy. If validated runtime age is below 18, the deterministic age gate transitions to `STATE_INELIGIBLE_MINOR` and blocks DCMFNet, RAG personalization, prompt construction, and LLM generation.
- The system renders only this stored script:

  > Access denied. This research prototype is approved for adults aged 18 and over. No risk calculation has been performed.

- The UI and documentation must not claim that DCMFNet was trained exclusively on adults unless artifact-backed evidence is added and verified. The gate is a product eligibility decision and also avoids introducing a child-data consent flow into this prototype.

### Emergency situations

- Emergency indicators such as overdose, acute attack, immediate danger, or an explicit emergency route to `EMERGENCY_REDIRECTION`. The UI displays a persistent, accessible emergency overlay that remains visible until the session is reset, without trapping keyboard focus or blocking click-to-call/copy actions.
- The system renders only this stored script:

  > 🚨 **EMERGENCY DETECTED:** This tool is not a triage or emergency response service. If you are experiencing a medical or psychological emergency, call **112** (India's national emergency number) or go immediately to the nearest hospital emergency department.

### Educational RAG summarization router

- Requests for definitions, mechanisms, or population-level explanations concerning schizophrenia, hallucinations, or associations between schizophrenia and substance use route independently of questionnaire state and model-result context.
- The context builder supplies only current retrieved scientific evidence. It does not supply questionnaire tokens, model probabilities, feature-importance data, third-party details, or prior personalized conversation content.
- Every medical/scientific assertion requires an inline citation mapped to current verified corpus metadata. Raw matched text remains in expandable evidence metadata with DOI/PMID; uncited pretrained knowledge and speculative pathways are prohibited.

### Validation and testing consequences

- Response schemas make intercepted content mutually exclusive with generated answers and model results. Validation rejects mixed safety/assessment payloads, modified fixed scripts, missing resource configuration, or prohibited tool calls.
- Safety tests cover English paraphrases, misspellings, negation, quoted/academic mentions, language-agnostic emergency numbers/signals handled before language rejection, prompt injection, streaming cancellation, route precedence, false-positive recovery, context clearing, telemetry redaction, age-boundary values, third-party attempts, and proof that each blocked route cannot reach DCMFNet or the LLM.
- The safety classifier and thresholds require a versioned evaluation set with sensitivity, specificity, subgroup, and regression reporting before release. Safety policy changes require review and a new policy version.

### Policy verification references

- India emergency number: [Emergency Response Support System, 112 India](https://112.gov.in/).
- Current national tele-mental-health resource: [Tele-MANAS, Directorate General of Health Services](https://dghs.mohfw.gov.in/national-mental-health-programme.php).
- KIRAN transition: [Ministry of Social Justice and Empowerment press release, 15 February 2024](https://www.pib.gov.in/PressReleasePage.aspx?PRID=2006265&lang=2&reg=48).
- Vandrevala contact and availability: [Vandrevala Foundation contact page](https://www.vandrevalafoundation.com/free-counseling/contact-us).
- Telemedicine boundary reference: [Telemedicine Practice Guidelines](https://esanjeevani.mohfw.gov.in/assets/guidelines/Telemedicine_Practice_Guidelines.pdf).
- Child-data boundary reference: [Digital Personal Data Protection Act, 2023](https://www.indiacode.nic.in/bitstream/123456789/22037/2/a2023-22.pdf).

These references record the basis for architecture review and do not enter the scientific RAG corpus unless they independently satisfy Section 5. Resource owners must reverify operational contact details; a documentation link is not a perpetual availability guarantee.

## 8. Privacy and data lifecycle — approved for portfolio MVP

### Zero-persistence questionnaire and result boundary

- `prototype_demo` uses zero persistent application storage for raw conversational text, questionnaire fields, intermediate slider arrays, questionnaire tokens, the 105-input matrix, target objects, model inputs, raw or displayed probabilities, generated personalized responses, and session history. Encryption does not make persistence of these values permissible.
- These values may exist only in volatile client memory and the minimum volatile backend request/session memory needed for validation and inference. They must never enter a relational or NoSQL database, Redis persistence, filesystem, browser `localStorage` or `sessionStorage`, IndexedDB, service-worker/application cache, URL/query string, cookie payload, backup, crash dump, analytics event, or model/retrieval cache.
- Sensitive request and response paths set `Cache-Control: no-store`; browser autofill and form restoration are disabled where supported. Deployment disables request-body/APM capture and core dumps and must prevent plaintext swap or hibernation from creating a recoverable copy. A deployment unable to meet these controls fails readiness.
- The previous portfolio requirement for an encrypted sensitive audit database is superseded. Corpus provenance, model-artifact audit reports, aggregate operational metrics, and retraction tombstones may persist only because they contain no user/session content.

### Session lifetime and automatic teardown

- The inactivity TTL is exactly 30 minutes for the portfolio MVP and is enforced independently by client and server. Only an explicit user interaction accepted by the application resets activity; background polling, health checks, streaming keep-alives, and analytics do not extend the TTL.
- Expiry atomically invalidates the cryptographically random ephemeral session ID, cancels active generation/inference where possible, wipes frontend and backend volatile state, drops model/explanation context, clears any short-lived application session credential, and returns the UI to `/`. The frontend must never hold an LLM, embedding, or infrastructure-provider credential.
- Expired, reset, missing, or restarted sessions cannot be resumed. Multi-instance hosting may use session affinity but cannot introduce a persistent shared session store for the MVP.

### User-driven reset

- A prominent `Reset Session` control is available throughout assessment and conversation views. Its synchronous client handler immediately replaces all local state with the uninitialized landing state and navigates to `/`.
- The client also sends an idempotent backend reset request that purges the server's volatile session state and cancels active work. UI clearing does not wait for the network response; the 30-minute server TTL remains the backstop if delivery fails. Repeated reset calls reveal no prior state.

### External processing boundary

- Raw user text, questionnaire data, model inputs/results, prompts containing user content, session identifiers, and personalized context must not be transmitted to externally operated LLM, embedding, moderation, tracing, or analytics APIs. OpenAI, Anthropic, and comparable public inference APIs are prohibited for this MVP even when they advertise provider-side zero retention.
- The approved portfolio-hosting exception is the Modal backend defined in Section 9. The intent classifier, safety classifier, embedding model, reranker, orchestration LLM, and DCMFNet execute inside that controlled backend; no public third-party model API receives runtime user data.
- Modal integration must use a Modal Server or another Modal endpoint type whose current documentation states that request and response payloads are not stored. Ordinary Modal Function calls and user-bearing `.remote`, `.spawn`, or `.map` payloads are prohibited because provider documentation permits temporary input/output retention for those invocation paths. Request-body logging, container/app logs containing payloads, memory or filesystem snapshots of live user state, Dicts, Queues, Volumes, and other persistent Modal storage are prohibited for runtime user data.
- Compute and request routing are pinned to `ap-south` (Mumbai), request payloads remain below the provider's regional-routing size threshold, and only synchronous endpoint transport is permitted for user-bearing calls. A deployment review must verify these controls against current provider behavior and contract terms before every release.
- Modal may retain non-sensitive platform metadata or logs outside India, and TLS terminates at its edge. Therefore this MVP may claim zero persistent **application payload** storage only after verification; it must not claim absolute provider invisibility, absolute zero retention, or guaranteed DPDP compliance. If the active India data-fence policy prohibits the provider's documented metadata/log location or edge processing, Modal fails readiness and the backend must move to a compliant deployment adapter.
- Bibliographic adapters may send only system-generated, non-sensitive scientific search terms to approved authority APIs such as PubMed. They must never forward the raw user question, session/context fields, questionnaire-derived terms, probabilities, or feature data.

### Logging, tracing, and telemetry

- Middleware uses allowlist-based event schemas rather than attempting best-effort redaction after logging. Request/response bodies, prompts, headers containing credentials, raw text, questionnaire values, model vectors, probabilities, session IDs, IP addresses, user agents, referrers, and stack-local sensitive variables are excluded from standard logs, traces, metrics, and error reports.
- Permitted operational fields are coarse timestamps, component/route identifiers, latency buckets, non-sensitive status/error codes, model/corpus/policy versions, and aggregate counters. Datadog, Loggly, Vercel logs, LangSmith, and similar third-party telemetry integrations may not receive user- or session-level runtime events.
- Debugging an invalid probability uses only the protected volatile request object. The exact raw value is not logged or retained and disappears on request teardown.

### Product analytics

- The MVP does not use Google Analytics, Mixpanel, Vercel Analytics, or another client/session analytics service. If analytics are enabled later without a new policy decision, collection is limited to local counters for `clicked_start_assessment`, `clicked_reset_session`, coarse duration buckets, and `triggered_crisis_modal`.
- Before persistence, permitted metrics are aggregated across sessions and stripped of event timestamps, IP/network data, user agent, locale fingerprint, session/correlation ID, route sequence, text, answers, probabilities, and other linkable attributes. No event-level row is retained. Crisis counts require a configured minimum aggregation window and disclosure threshold so a count cannot be associated with a particular session.
- Analytics failure never blocks safety/reset behavior and cannot extend a session. Analytics code cannot read the questionnaire or conversation stores.

### Upload boundary

- Research-record, medical-history, clinical-PDF, image, audio, and genomic CSV/VCF upload features are omitted from `prototype_demo`. Public contracts contain no upload or attachment union, and backend routes reject multipart/file payloads.
- The only assessment inputs are approved manual form fields plus `generic_genetic_profile_v1`. Scientific-corpus ingestion is an operator-only offline process and is not a user upload surface.

### Verification consequences

- Tests prove absence of sensitive database/filesystem/browser-cache writes; `no-store` response headers; exact 30-minute expiry; polling-resistant TTL; reset idempotency; cancellation and memory deletion; restart invalidation; absence of provider credentials in the client; external-provider egress denial; logging/trace schema allowlists; aggregate-only analytics; and rejection of upload payloads.
- Release review includes browser-storage inspection, log/trace capture inspection, network-egress tests, crash/core-dump configuration, swap/hibernation review, and a data-flow inventory. “Zero retention” is not claimed merely because application tables are absent.

## 9. LLM and deployment constraints — approved for portfolio MVP

### Deployment topology and provider portability

- The public presentation layer is a Framer site. Questionnaires, sliders, disclaimers, fixed safety content, evidence drawers, and assessment-redirection controls render in Framer code components.
- A Modal-hosted Python backend exposes the FastAPI-compatible public contract and contains deterministic gates, LangGraph orchestration, RAG, locally hosted English classifiers and generation model, and DCMFNet. The browser calls this backend only; it never calls an LLM, embedding provider, vector store, bibliographic service, or DCMFNet directly.
- Domain and application code remain provider-neutral behind typed ports. Modal-specific decorators, secrets, lifecycle settings, and routing configuration stay in the deployment adapter/composition root. Moving providers may require endpoint, DNS, CORS, secret, and infrastructure configuration changes, but must not require a Framer UI contract change.
- Public endpoints enforce an explicit Framer-origin allowlist, narrow CORS policy, request-size and rate limits, short-lived signed application-session credentials, schema validation, and abuse controls. Browser `Origin` checks supplement rather than replace authentication and authorization.

### Streaming contract

- Conversational scientific-RAG responses use Server-Sent Events (SSE) or an equivalent chunked HTTP transport. The canonical SSE events are `status`, `validated_content`, `evidence`, `done`, and `error`; every stream is bound to the ephemeral cryptographic session ID without exposing that ID in URLs or logs.
- The system does not stream raw model tokens directly to the UI. Generated content is buffered and validated, or validated claim-by-claim, before a `validated_content` event is emitted. This preserves citation, safety, score-integrity, and causal-language enforcement and prevents invalid text from becoming visible before validation.
- Fixed safety responses, language errors, assessment redirects, and other zero-generation terminal results may use a normal typed response or a terminal SSE event. A higher-priority safety event cancels the upstream task and discards all unvalidated buffered content.
- Sensitive streaming responses set `Cache-Control: no-store`; intermediaries must not buffer or transform the stream. Heartbeats do not renew the session TTL. Disconnects cancel pending work where possible, and reconnects do not replay sensitive content from persistent storage.
- Streaming is required for responsive progress reporting, but it is not represented as a guarantee against every browser, proxy, or platform timeout.

### Secrets and model ownership

- Infrastructure credentials, corpus credentials, and model-access tokens are injected only into the backend through `modal.Secret` or an equivalent server-side secret manager. Testers never provide keys, and no secret is embedded in the Framer bundle, page source, browser storage, API response, or log.
- The orchestration LLM and embedding/reranking models are self-hosted inside the approved backend boundary. “Provider-neutral LLM adapter” means the implementation can replace the hosted model without changing domain contracts; it does not permit sending runtime user data to a public model API.

### Cost, scaling, and latency objectives

- Configure zero minimum containers and a measured short scale-down window so idle **compute** scales to zero. This is a cost objective, not a promise of an absolute `$0/month`: active compute, Framer plans, region multipliers, egress, persistent non-user corpus storage, and other provider charges may remain.
- Apply rate limits, concurrency caps, usage alerts, and a monthly spending limit where supported. Exhausting a cost limit fails closed with a non-clinical availability error and never triggers a local fabricated estimate.
- Warm input-validation overhead and the first progress event target sub-second latency. Full RAG retrieval and generation, and cold-start latency, are measured separately and are not given a sub-second guarantee. Release quality targets require benchmarked percentile thresholds under Section 11.

### Network and offline behavior

- Online connectivity is required for RAG answers, language/intent classification, and every DCMFNet calculation. The Framer browser sends user-bearing traffic only to the approved backend; the backend performs corpus access and local model execution.
- When `navigator.onLine === false` or the backend is unreachable, the UI suppresses assessment submission, RAG, LLM, and inference requests. It may keep the current form values in volatile memory, render static disclosures, navigate, and reset the session.
- Offline mode must never run a simulated, approximate, cached, or client-side risk calculation and must never present `generic_genetic_profile_v1` as an offline model substitute. It displays exactly: `You're offline. Research estimates and evidence-based answers require a connection. No calculation has been performed.`
- Reconnection requires a fresh backend safety/schema validation before processing. Sensitive responses, model outputs, and evidence are not placed in a service-worker cache for offline replay.

### English-only input gate

- Safety-critical deterministic indicators that do not depend on language run first. All other conversational free text then passes through the local English-language gate before intent classification, RAG, LLM generation, or inference authorization.
- The gate combines bounded language identification with script/character checks. Non-ASCII characters alone are not sufficient for rejection because valid English names, punctuation, DOI strings, and scientific notation may contain them. Unsupported or uncertain input fails closed with exactly: `Input error: Language unsupported. Please resubmit your query in English.`
- The Framer UI, questionnaire copy, corpus text used for generation, and generated summaries are English only. The project-fine-tuned English DistilBERT intent classifier receives only inputs accepted by the language gate; Hinglish and multilingual classification are out of scope.

### Conversational risk-calculation redirection

- After safety and language gating, deterministic phrases plus the bounded English DistilBERT router detect direct, indirect, misspelled, and rephrased requests to calculate, run, estimate, or interpret an individual risk probability. The classifier emits intent only; it cannot invoke DCMFNet.
- A `risk_assessment` intent in the conversational route terminates generation and returns `ASSESSMENT_REDIRECTION`. The chat route has no DCMFNet tool binding and cannot calculate, guess, interpret, or fabricate a probability.
- The UI renders this fixed text:

  > I cannot calculate clinical probabilities or interpret metric values directly inside this chat window. To compute a simulated research risk estimate for psychotic or manic patterns based on generic genetic baselines, please click the link below to launch the assessment questionnaire.

- The same response includes a high-visibility `Launch Research Questionnaire Router` action. Activating it navigates to the structured assessment view and initializes a new volatile assessment state; it does not itself run inference.
- Only a complete, valid form submission from that structured view may reach the DCMFNet authorization gate. Tests prove that conversational prompts, prompt injection, forged client route fields, and direct endpoint calls cannot bypass this separation.

### Deployment verification references

- [Modal streaming endpoints](https://modal.com/docs/guide/streaming-endpoints)
- [Modal security and payload-retention behavior](https://modal.com/docs/guide/security)
- [Modal data residency](https://modal.com/docs/guide/data-residency)
- [Modal region selection](https://modal.com/docs/guide/region-selection)
- [Modal secrets](https://modal.com/docs/guide/secrets)
- [Modal cold-start configuration](https://modal.com/docs/guide/cold-start)
- [Framer Fetch security guidance](https://www.framer.com/help/articles/how-to-use-fetch/)

## 10. Workflow and failure behavior — approved for portfolio MVP

### Questionnaire completeness gate

- Every approved user-facing questionnaire control is required and has a deterministic type, range, unit, and encoding. Framer keeps the assessment submit action disabled until every manually collected field is locally valid and displays a missing/invalid-field summary that does not rely on the disabled control alone.
- The user does not manually enter all 105 model variables. After submission, the backend independently validates the manual fields, adds only the approved `generic_genetic_profile_v1` values, constructs the exact 105-variable target matrix, and validates completeness again. Client validation is usability support and can never authorize inference.
- Missing, extra, malformed, non-finite, incorrectly encoded, or unapproved values return a typed questionnaire validation result. They never invoke DCMFNet, and forged client completion flags are ignored.

### Ambiguous conversational intent

- The bounded intent classifier uses calibrated probabilities. When the highest permitted non-safety intent confidence is below `0.85`, when the out-of-distribution detector fires, or when two incompatible intents remain unresolved, the system suppresses generation, RAG, and inference and returns `INTENT_CLARIFICATION_REQUIRED`.
- Safety-critical or clinically prohibited uncertainty is handled by the earlier fail-closed safety policy; the `0.85` clarification rule cannot downgrade a safety route.
- Framer renders exactly: `I didn't quite catch that. Please select what you would like to do:` with two actions: `Submit Risk Assessment Questionnaire` and `Ask About Schizophrenia & Clinical Associations`.
- The first action only launches a new volatile structured questionnaire state; despite its label, it does not submit data or invoke DCMFNet. The second opens the bounded scientific-question experience and asks the user for a new English question; it does not reuse the ambiguous text as an authorized medical query.
- `0.85` is the initial product threshold, not proof of adequate classifier quality. Calibration and per-class evaluation under Section 11 remain release gates; a later threshold change requires a versioned policy decision and regression evidence.

### DCMFNet failures and retry policy

- A non-finite or out-of-range model output is a deterministic validation failure, not a transient outage. It is never retried, because rerunning the same deterministic model and vector cannot make the value valid. It immediately uses the Section 3 internal-system-variance response and destroys the protected raw value at request teardown.
- Input/schema errors, incomplete matrices, artifact checksum/configuration failures, and policy denials are also non-retryable and fail closed through their typed errors.
- Only an explicitly classified transient execution failure—such as a temporary worker interruption before a result exists—may be retried once. The retry uses the same already-validated vector held in volatile memory, the same artifact/target, and the same idempotency key; it never reconstructs inputs, changes values, or writes them to telemetry.
- If that single retry also fails, the UI renders exactly: `System Note: The model failed to compute your specific risk estimation at this time. You may attempt to re-submit your parameters if you wish.` No estimate, RAG explanation, or LLM output accompanies it.

### RAG and generation fallbacks

- Retrieval distinguishes `NO_ELIGIBLE_EVIDENCE` from `RETRIEVAL_UNAVAILABLE`. Before returning either state, a dense/vector zero-match or eligible vector-search failure triggers one deterministic keyword/BM25 fallback over the same approved scientific corpus.
- The keyword fallback uses a separately available lexical index so it can operate when the vector index is unavailable. It applies the identical source allowlist, 20-year window, DOI/PMID, quality, retraction-freshness, scientific/non-patient metadata isolation, relevance, evidence-hierarchy reranking, conflict-coverage, and 3-to-5-source cap. Keyword match alone never makes a document eligible.
- Query terms are produced by deterministic English tokenization and a versioned approved scientific synonym/abbreviation map. The LLM cannot invent fallback terms. The raw query and derived terms remain volatile and are never logged, cached, or persisted.
- When the lexical fallback returns eligible evidence, the result records `retrieval_mode=keyword_fallback`, retains lexical scores and provenance, and proceeds through the normal context and response validators. Citations do not distinguish or weaken requirements based on retrieval mode.
- `NO_ELIGIBLE_EVIDENCE` is returned only when both the primary retrieval path and keyword fallback complete successfully with no eligible relevant evidence. `RETRIEVAL_UNAVAILABLE` is returned when neither an approved primary path nor the independent lexical fallback can complete. Neither state permits the LLM to answer from pretrained knowledge.
- For `NO_ELIGIBLE_EVIDENCE`, the UI renders: `I couldn't find eligible, current scientific evidence in the approved corpus for this question. I won't generate a medical or scientific answer without verified sources. You may search PubMed directly or ask a broader question.`
- For vector-store failure, the user sees no outage message if keyword fallback returns sufficient eligible evidence. If the independent lexical fallback also cannot complete, the UI renders: `Scientific evidence is temporarily unavailable, so I can't provide an evidence-based answer right now. Please try again later or search PubMed directly.`
- For locally hosted orchestrator-LLM timeout, capacity exhaustion, or invalid output after the bounded response-validation retry, the UI renders: `I couldn't generate a validated evidence-based response at this time. Please try again later.` The architecture has no external LLM-provider fallback and does not characterize this path as a public-provider `429`.
- A previously validated DCMFNet result remains displayable when only RAG or the LLM fails. In that case Framer may also render a deterministic, target-aware assessment fallback: `Result Summary: The simulated research estimate for {validated_target_label} is shown above. An evidence-grounded explanation is temporarily unavailable. ⚠️ CAUTION: This metric is strictly intended for portfolio research and engineering demonstration purposes only and is not validated for individual care decisions. You may search PubMed directly for scientific literature.` The target label and displayed estimate come only from the existing validated result contract.
- The target-aware assessment fallback is never shown for a standalone scientific question, before successful inference, after an invalid probability, or for an expired/reset session. It cannot turn a RAG or LLM failure into a new prediction. The universal psychotic/manic fallback proposed for all outage types is therefore not adopted.

### Response-validation failures

- Every response is represented as structured claim/content blocks and validated before any `validated_content` SSE event reaches Framer.
- When a citation fails provenance or entailment validation, the system rejects the entire associated factual claim block. It must not remove only the citation marker and expose the now-uncited medical claim.
- A rejected claim block may be omitted only if the remaining response is coherent, answers the request, retains every required limitation/disclaimer, and contains no uncited medical or scientific claim. Otherwise the entire generation is rejected.
- One bounded regeneration may receive only non-sensitive validation error codes and the same immutable result/evidence context. If it fails, the output is purged and the appropriate no-evidence, dependency-unavailable, or generation-unavailable message above is returned. A generic risk-summary block cannot substitute for a failed educational answer.

### Privacy-safe operational failure telemetry

- `ticket.jsonl` is prohibited in `prototype_demo`. A local serverless file is not a durable incident system and would violate the zero-persistent-user-data and no-filesystem requirements if it contained raw stacks, queries, target metrics, vectors, or probabilities.
- Failures emit only the allowlisted `OperationalFailureEvent`: coarse time bucket, component and operation codes, stable error category, retry count, latency bucket, deployment mode, and artifact/corpus/model/policy versions. It contains no raw exception stack, exception locals, user query/token string, questionnaire data, target payload metrics, probability, evidence text, session/correlation ID, identity, IP address, or credential.
- Emission is non-blocking and cannot delay safety, reset, or the public failure response. Provider logs may receive this sanitized event only under the Section 8 retention/residency disclosure; any durable incident tracker requires a separate privacy review and must remain non-sensitive.
- The full exception may exist only in protected volatile process memory while the request is being handled, with local-variable capture and body capture disabled. It is destroyed at teardown. Operators diagnose recurring failures from aggregate codes, versions, controlled synthetic reproductions, and non-sensitive deployment telemetry.

### Failure-path verification

- Tests cover client and server questionnaire enforcement, all 105-variable server completeness after generic-profile assembly, forged completion flags, the calibrated `0.85` boundary, clarification actions, safety precedence, and proof that clarification cannot reach tools.
- Inference tests prove zero retries for invalid/non-finite outputs and schema/artifact failures, at most one retry for allowlisted transient failures, immutable retry inputs, idempotency, exact public messages, and absence of sensitive telemetry.
- RAG/LLM tests distinguish primary success, vector zero-match, vector failure with keyword success, keyword zero-match, dual-index outage, generation outage, valid-result preservation, and standalone-query behavior. They verify independent lexical availability, deterministic term derivation, identical metadata/quality/retraction filtering, `retrieval_mode`, lexical provenance, source caps, and no query logging. Response tests prove claim-level rejection, no orphaned claims after citation failure, bounded regeneration, pre-stream validation, and no universal risk fallback.
- Privacy tests fail if `ticket.jsonl` or another runtime failure file is created, if raw exception stacks or queries reach logs, or if any failure event contains a session/user/model-input/result value.

## 11. Quality targets — approved for portfolio MVP

### Measurement rules

- Quality gates are evaluated on versioned, frozen, labeled test sets using synthetic or explicitly approved non-user fixtures. Dataset version, class distribution, sample count, model/artifact/corpus versions, threshold configuration, random seed where relevant, environment, and evaluation code revision are recorded with each report.
- Per-request classifier confidence, dataset-level classifier accuracy, retrieval similarity, citation validity, and clinical/model probabilities are different measurements and must never be labeled interchangeably.
- A finite test result establishes performance on that evaluation set; it does not prove that production will have zero errors. Production readiness requires the hard runtime interceptors in addition to evaluation targets.

### Intent routing and safety

- On the frozen intent-routing evaluation set, the fine-tuned English classifier must achieve strictly greater than `85%` overall accuracy and strictly greater than `0.85` macro-F1. Per-class precision, recall, F1, support, confusion matrix, calibration error, and abstention coverage must also be reported so class imbalance cannot hide a weak intent.
- The separate per-request routing rule remains: a maximum calibrated intent confidence below `0.85`, an out-of-distribution result, or unresolved incompatible intents produces clarification. The `0.85` confidence threshold does not mean the classifier has `85%` accuracy.
- Safety routing is evaluated separately from ordinary intent routing. Every versioned release-blocking critical fixture for explicit self-harm, immediate danger, overdose/emergency, minor age, and prohibited clinical requests must take its required deterministic route, with zero observed false negatives in that finite suite. Any miss blocks release.
- The system must not claim that “zero false negatives” is guaranteed in production, and production telemetry alone cannot measure missed events that were never labeled. Safety monitoring uses privacy-safe aggregate route counts, controlled red-team/regression testing, and reviewed incident reports containing no user payload.

### Citation correctness and unsupported claims

- At least `85%` of citation references produced by the **unvalidated first-pass generator** on the evaluation set must map to eligible evidence in that request's active RAG context. This is a model-quality diagnostic only; it does not authorize display.
- The public response validator requires `100%` citation-key provenance precision: every displayed citation key must map to an eligible, active, non-retracted DOI/PMID evidence item actually retrieved for that generation cycle. One missing or fabricated identifier rejects its entire factual claim block under Section 10.
- The unvalidated first-pass generator's unsupported medical/scientific claim rate must be at most `5%`, measured at claim level, with the sentence-level rate also reported for traceability. The displayed-response target is `0%`: every medical/scientific claim must be supported and cited, and any unsupported claim is blocked regardless of aggregate rate.
- If claim/citation validation cannot yield a coherent, complete response after the single bounded regeneration, use the specific Section 10 no-evidence or generation-unavailable response. Never use a generic risk summary to replace a failed educational answer.

### Retrieval relevance

- The initial dense-retrieval candidate gate is strict cosine similarity `>0.85` for the selected, normalized embedding configuration. A score equal to `0.85` does not pass. Sparse/hybrid candidates must satisfy their separately calibrated relevance gate before context inclusion.
- Cosine values are embedding-model- and normalization-specific. The `0.85` threshold cannot be transferred to a new embedding model or treated as an `85%` probability; changing the embedding artifact requires recalibration, a new threshold/version, and retrieval regression testing.
- Threshold compliance alone is insufficient. The frozen relevance-labeled evaluation must report Precision@k, Recall@k, MRR, nDCG, zero-result rate, conflict-position coverage, and performance by query category. Exact release thresholds for those additional metrics require the selected embedding/retrieval benchmark; no model may ship merely because its returned chunks exceed `0.85` cosine similarity.
- Report the same ranking metrics separately for primary retrieval, keyword-fallback-only cases, and the combined cascade. Also report fallback activation rate, fallback recovery rate, dual-zero-result rate, and added latency so keyword search cannot mask a weak vector configuration or violate the 60-second deadline.

### Probability integrity

- The exact validated DCMFNet numeric output and target/artifact identity must survive inference-port return, backend state/context construction, and public result serialization with `100%` equality to the canonical inference result. The LLM never receives authority to derive, round, scale, weight, or modify it.
- The raw value is not printed as an unrestricted debug field. Framer displays the separately contracted deterministic percentage representation derived from the validated raw value. Percentage scaling and rounding are permitted only in that presenter; they do not overwrite the immutable raw field.
- Contract and end-to-end fixtures require exact equality for the raw value and exact expected formatting for the display value. Any mismatch blocks the response rather than repairing it.

### Latency budget

- The application enforces a maximum `60-second` client-visible deadline from accepted Framer submission to a terminal `done` or safe `error` state. The interval includes Modal cold start, backend validation, retrieval, generation, validation, and delivery of the terminal event.
- If successful completion cannot occur within the deadline, the client cancels the request and renders the appropriate typed availability response; no partial unvalidated generation is exposed. The 60-second requirement is therefore a bounded user outcome, not a guarantee that every request succeeds within a minute or that an unreachable network can deliver a server response.
- Evaluation reports end-to-end p50, p95, p99, and maximum latency; cold and warm runs are separated. A release test run fails if any controlled end-to-end case lacks a terminal UI state by 60 seconds. The existing sub-second warm validation/first-status objective is measured separately and does not satisfy the completion gate.

### Monitoring and release evidence

- Quality compliance is computed by dedicated evaluation jobs and stored as versioned aggregate reports/CI artifacts containing only approved synthetic or non-user fixtures. Reports include metric definitions, denominators, confidence intervals where meaningful, failures, and pass/fail outcomes.
- `ticket.jsonl` is not a quality-monitoring source and remains prohibited. Runtime user queries, questionnaire data, predictions, raw exceptions, and session identifiers cannot be copied into evaluation artifacts.
- Production telemetry may contribute only the sanitized aggregate counters and `OperationalFailureEvent` fields approved in Sections 8 and 10. Production content quality is assessed through approved synthetic probes and controlled review, not retained user conversations.

## Pending product decisions

No numbered product-policy section remains pending. Concrete model selection, questionnaire semantics, access-control details, and metric-specific benchmark thresholds identified elsewhere remain implementation or release gates rather than permission to weaken Sections 1–11.
