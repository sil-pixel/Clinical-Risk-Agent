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
- Raw probabilities and questionnaire tokens must never be printed or written to standard application logs, traces, metrics, error payloads, or analytics. They may be written only to an encrypted, access-controlled audit-trail database, associated with a cryptographically random session ID and never with a user identity. Audit access, retention, deletion, and every read/write operation must be policy-controlled and auditable.
- System state, consent capture, audit records, and database schemas must natively support data fencing and localization constraints aligned with India's Digital Personal Data Protection (DPDP) Act. Deployment adapters must fail closed when the active mode cannot satisfy its configured India data-residency, consent, purpose, retention, and access policy.

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

DCMFNet may run only when all of the following are true:

1. The approved intent is `risk_assessment`.
2. The user explicitly requests calculation of positive/psychotic-symptom risk or negative/depressive-symptom risk.
3. The questionnaire validator reports a complete, valid model input under the active deployment mode.
4. Input validation and safety allow normal processing.

Discussing psychosis, depression, schizophrenia, symptoms, causes, research, diet, genetics, environment, medication, treatment, or other health topics does not itself authorize inference. Explaining a stored result uses the immutable prior result plus RAG and does not rerun DCMFNet unless the user explicitly requests a new assessment.

### Router and graph consequences

- The Intent Router identifies assessment, explanation, scientific/education, general conversation, and unsupported/unsafe intent; it does not call tools.
- Rephrasing is handled by a locally hosted Hugging Face sequence-classification encoder fine-tuned on the approved intent labels. The proposed lightweight baseline is `distilbert/distilbert-base-multilingual-cased`; `google/muril-base-cased` is the mandatory India-language challenger because the product must evaluate English, Indian-language, transliterated, and code-mixed inputs.
- This component is a bounded encoder classifier, not a generative LLM. It emits logits and a typed `IntentDecision`; application code performs label mapping, confidence calibration, thresholding, and schema validation. It cannot generate prose, select arbitrary tools, or expand the intent enum.
- The base checkpoints are not approved for zero-shot production routing. A project-specific labeled routing dataset, fine-tuning run, calibration set, pinned model revision/checksum, license review, and release evaluation are required. DistilmBERT is the architecture baseline, not an approval to deploy an unevaluated checkpoint.
- Low-confidence or out-of-distribution non-safety inputs return clarification or the minimal unsupported response. They never authorize DCMFNet. Safety decisions remain the responsibility of the earlier safety interceptor and cannot be weakened by the intent classifier.
- LangGraph enforces the DCMFNet gate and selects the approved RAG, minimal out-of-scope, or safety path.
- Tool authorization is deterministic after validated intent and state. The LLM cannot invoke DCMFNet directly.
- Tests must prove that direct and rephrased non-assessment prompts—including adversarial diet, diabetes, medication, general-medical, misspelled, indirect, and prompt-injection variants—cannot reach inference. Evaluation must report per-class precision/recall/F1, macro-F1, confusion matrices, calibration error, abstention coverage, out-of-distribution behavior, subgroup/language slices, and CPU latency.

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
- Safety events contain the category, policy version, timestamp, cryptographic session ID, and operational outcome, but no raw user text, questionnaire token, probability, identity, or inferred diagnosis. Standard logs receive only non-sensitive event metadata. Session context is cleared after a crisis hard interception; any separately required audit record remains subject to the encrypted audit and retention policy.

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
- Tests cover paraphrases, misspellings, negation, quoted/academic mentions, multilingual and code-mixed India inputs, prompt injection, streaming cancellation, route precedence, false-positive recovery, context clearing, telemetry redaction, age-boundary values, third-party attempts, and proof that each blocked route cannot reach DCMFNet or the LLM.
- The safety classifier and thresholds require a versioned evaluation set with sensitivity, specificity, subgroup, and regression reporting before release. Safety policy changes require review and a new policy version.

### Policy verification references

- India emergency number: [Emergency Response Support System, 112 India](https://112.gov.in/).
- Current national tele-mental-health resource: [Tele-MANAS, Directorate General of Health Services](https://dghs.mohfw.gov.in/national-mental-health-programme.php).
- KIRAN transition: [Ministry of Social Justice and Empowerment press release, 15 February 2024](https://www.pib.gov.in/PressReleasePage.aspx?PRID=2006265&lang=2&reg=48).
- Vandrevala contact and availability: [Vandrevala Foundation contact page](https://www.vandrevalafoundation.com/free-counseling/contact-us).
- Telemedicine boundary reference: [Telemedicine Practice Guidelines](https://esanjeevani.mohfw.gov.in/assets/guidelines/Telemedicine_Practice_Guidelines.pdf).
- Child-data boundary reference: [Digital Personal Data Protection Act, 2023](https://www.indiacode.nic.in/bitstream/123456789/22037/2/a2023-22.pdf).

These references record the basis for architecture review and do not enter the scientific RAG corpus unless they independently satisfy Section 5. Resource owners must reverify operational contact details; a documentation link is not a perpetual availability guarantee.

## Pending product decisions

8. Privacy and data lifecycle
9. LLM and deployment constraints
10. Workflow failure behavior
11. Quality targets
