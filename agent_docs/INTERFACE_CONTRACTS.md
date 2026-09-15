# Interface Contract Registry

Status: Architecture baseline with verified ML inference contracts; payloads marked **blocked** must not be implemented by downstream consumers

Owner: Software Architect for boundary consistency; component owners finalize their payloads

Source: [`ARCHITECTURE.md`](ARCHITECTURE.md)

## Contract rules

1. Cross-component contracts are typed, versioned, serialized without framework-specific objects, and stored in the canonical `src/clinical_risk_agent/contracts/` package when implemented.
2. The owner named below is the only role that may finalize semantic fields. Consumers may request changes through an architecture review.
3. Every tool returns either a valid success payload or a typed failure. `null`, prose-only errors, and fabricated fallback values are not contracts.
4. Tool results are immutable after validation. The LLM and UI cannot change numeric outputs or citation identity.
5. Contract fixtures contain synthetic questionnaire/model data and clearly labeled synthetic retrieval records.

## Registry

| Contract | Producer → consumers | Owner | Status / gate |
| --- | --- | --- | --- |
| `SafetyDecision` | Safety → workflow/API | AI Architect (design), AI Engineer (implementation) | **Architecture-approved:** terminal categories, priority, fixed-response and tool-denial semantics defined below |
| `LanguageDecision` | Language gate → workflow/API | AI Architect (design), AI Engineer (implementation) | **Architecture-approved boundary:** English-only supported/unsupported/uncertain result; concrete local detector and thresholds pending evaluation |
| `IntentDecision` | Router → LangGraph | AI Architect (design), AI Engineer (implementation) | **Architecture-approved boundary:** local fine-tuned encoder, fixed enum, initial calibrated `0.85` clarification threshold, abstention, and provenance; release use pending calibration/evaluation approval |
| `DeploymentMode` | Composition root → all workflow/results/telemetry | Software Architect | **Architecture-approved:** `prototype_demo`; `hospital_silent_research` reserved and unavailable until separately gated |
| `ArtifactInspection` | DCMFNet artifact validator → readiness/tests | ML Engineer | **Implemented:** integrity/readiness facts |
| `InferenceInputSchema` | DCMFNet adapter → graph/backend/tools | ML Engineer | **Implemented:** exact machine feature groups/order; not user-facing questionnaire copy |
| `QuestionnaireRequirements` | ML/questionnaire → graph/UI | ML Engineer | **Blocked** on collection feasibility, encodings, ranges, wording, and provenance |
| `QuestionnaireValidationResult` | Questionnaire validator → graph | ML Engineer | **Blocked** on requirements contract |
| `InferenceRequest` | Graph → DCMFNet port | ML Engineer | **Implemented internally:** selected target plus records containing all 105 exact numeric feature keys |
| `InferenceResult` | DCMFNet port → graph/context/API | ML Engineer | **Implemented:** immutable, separate positive- or negative-symptom research risk probability and artifact identity |
| `RetrievalQuery` | Graph → RAG port | AI Architect (design), RAG Engineer (implementation) | Minimum boundary below; AI/RAG architecture and corpus policy required |
| `EvidenceResult` | RAG port → graph/context/API | AI Architect (design), RAG Engineer (implementation) | Approved evidence/citation/source-cap boundary below; concrete adapter pending |
| `EvidenceDisplayRecord` | RAG port → API/UI | AI Architect (design), RAG/Frontend Engineers (implementation) | Retrieval-owned exact-match metadata; never generated as response prose |
| `LocalFeatureImportanceResult` | Validated SHAP port → context/API | ML Engineer (method), AI Architect (use) | **Blocked:** the planned SHAP adapter is not validated or approved |
| `StructuredExplanationContext` | Context builder → LLM port | AI Architect (design), AI Engineer (implementation) | Must compose immutable validated results; finalized after ML/RAG contracts |
| `ValidatedAssistantResponse` | Response validator → API/UI | AI Architect (design), AI Engineer (implementation) | Envelope below; content blocks finalized with Backend/Frontend |
| `AssessmentRedirection` | Conversational router → API/Framer | AI Architect / Frontend Engineer | **Architecture-approved:** fixed text and action; no inference permission |
| `IntentClarification` | Intent adapter → API/Framer | AI Architect / Frontend Engineer | **Architecture-approved:** calibrated `<0.85`/OOD ambiguity route with two fixed actions and no tool permission |
| `OperationalFailureEvent` | Backend components → allowlisted telemetry | Software Architect / Backend Engineer | **Architecture-approved:** non-sensitive codes/buckets/versions only; no `ticket.jsonl` |
| Public session transport | Modal-hosted FastAPI ↔ Framer | Backend Engineer | Architecture baseline below; JSON plus validated SSE |
| `ServiceError` | All components → API/tests | Software Architect / Backend Engineer | Minimum taxonomy approved |

## Approved intent values

The router output uses the roles already named in the problem statement:

- `risk_assessment`
- `explain_my_risk`
- `scientific_question`
- `mental_health_education`
- `general_conversation`
- `unsupported_or_unsafe`

The exact spelling is the canonical machine representation. Adding an intent requires Product Manager approval and an architecture/workflow/test update. Questionnaire completeness is never an intent.

`IntentDecision` contains the enum value, calibrated confidence, `requires_clarification`, non-sensitive rationale code, classifier model ID, pinned source revision/checksum, fine-tuning dataset/version, calibration version, and router version. It contains no generated prose, raw logits in public payloads, tool choice, questionnaire completeness decision, or new label. The local classifier adapter maps model logits to this contract. A maximum calibrated confidence below `0.85`, an out-of-distribution result, or unresolved incompatible intents sets `requires_clarification=true` and denies all tools. Safety uncertainty is resolved before this threshold and cannot be downgraded to clarification.

The proposed baseline is a project-fine-tuned `distilbert/distilbert-base-uncased`. The base checkpoint is not approved for zero-shot routing. The selected artifact must be pinned and integrity checked, operate locally, and pass the approved English routing, calibration, adversarial, memory, and CPU-latency gates.

`LanguageDecision` is evaluated after `SafetyDecision=ALLOW_NORMAL_PROCESSING` and before `IntentDecision`. It contains `SUPPORTED_ENGLISH`, `UNSUPPORTED_LANGUAGE`, or `UNCERTAIN_LANGUAGE`, plus detector/version and a non-sensitive rationale code. Unsupported and uncertain outcomes return `Input error: Language unsupported. Please resubmit your query in English.` with all tool permissions false. The concrete local detector and thresholds require separate evaluation; the intent classifier must not be reused as an implicit language detector.

`risk_assessment` in a conversational message produces `ASSESSMENT_REDIRECTION` and never authorizes inference. Only a complete valid submission from the separately initialized structured assessment view, with safety and route authorization, may invoke DCMFNet. Scientific or educational discussion of symptoms routes to RAG without inference. `explain_my_risk` consumes a stored immutable result and does not rerun the model; a new calculation requires another structured assessment submission.

`AssessmentRedirection` contains `response_kind=ASSESSMENT_REDIRECTION`, fixed-content ID/version, the exact approved redirection text, `action_id=launch_research_questionnaire_router`, an internal Framer route target, and `allow_inference=false`, `allow_rag=false`, `allow_llm=false`. Activating the action initializes volatile questionnaire state but does not call DCMFNet.

`IntentClarification` contains `response_kind=INTENT_CLARIFICATION_REQUIRED`, fixed text `I didn't quite catch that. Please select what you would like to do:`, actions `submit_risk_assessment_questionnaire` and `ask_about_schizophrenia_and_clinical_associations`, classifier/calibration/router versions, and `allow_inference=false`, `allow_rag=false`, `allow_llm=false`. The first action launches a blank volatile assessment form; the second requests a new English question. Neither action treats the ambiguous input as authorized content.

General mental health, genetics/environmental factors, diet/lifestyle/diabetes/physical health, and non-drug-specific, non-personalized treatment research may use RAG under the approved source policy. Any drug-specific question, medication selection, suitability, dosing, start/stop/change, or individualized treatment evaluation takes `PRESCRIPTIVE_REFUSAL` without RAG or DCMFNet. Unrelated general medical questions use the minimal out-of-scope response contract and do not invoke full RAG or DCMFNet.

## Minimum safety decision

`SafetyDecision` must include:

- one stable category: `EMERGENCY_REDIRECTION`, `CRITICAL_SAFETY_REDIRECTION`, `ACUTE_DISTRESS_REDIRECTION`, `STATE_INELIGIBLE_MINOR`, `THIRD_PARTY_REFUSAL`, `DIAGNOSTIC_REFUSAL`, `PRESCRIPTIVE_REFUSAL`, or `ALLOW_NORMAL_PROCESSING`
- whether normal processing may continue
- the immutable fixed-content ID and version when processing must stop
- explicit `allow_llm`, `allow_rag`, and `allow_inference` booleans, defaulting to `false`
- policy/ruleset version
- jurisdiction/resource-bundle version and verification status when escalation resources are shown
- a non-sensitive rationale code and classifier/rule version; never the raw triggering text

Priority is the category order shown above; `ALLOW_NORMAL_PROCESSING` is last. It must not contain a diagnosis, raw questionnaire data, raw user text, probability, identity, or relationship token. Crisis interception also commands generation cancellation and operational-context clearing. A probabilistic model is never the sole gate for deterministic age validation or explicit high-risk rules.

## ML-owned contracts

The canonical contracts are implemented under `src/clinical_risk_agent/contracts/` and the runtime under `src/clinical_risk_agent/inference/`. The implementation is based on the user-designated Thesis source at revision `2f6d96db481873fce8a3ba35f29d6e4ee5359dd9` and is covered by cross-runtime golden fixtures.

Each target-specific call requires all 105 unique feature keys in the exact exported schema. Unknown or missing keys, non-numeric values, and infinite values fail closed. NaN values are replaced with exported training medians; values are then standardized with exported training means and scales. CPU inference is the only verified device mode.

The result contains the exact artifact target—`SCZ18_Pos_Norm` or `SCZ18_Neg_Norm`—and raw predictions named `normalized_symptom_severity`, plus artifact version, checkpoint SHA-256, and fixed limitations. The product definition identifies the positive target as risk probability for positive schizophrenia symptoms, including psychotic and manic symptoms, and the negative target as risk probability for negative schizophrenia symptoms, including depressive symptoms. These research probabilities are not clinically validated, diagnoses, screening results, causal effects, thresholds, or a combined score. Consumers must preserve numeric and identity fields exactly and keep the two probabilities separate.

A deterministic output gate—not the LLM—requires every raw probability to be finite and within inclusive `[0.0, 1.0]` before producing a validated percentage representation. A value below `0.0` or above `1.0` triggers a typed internal-system-variance error and fails closed; it must not be clamped or exposed as an estimate. The public/UI message is exactly `Error: Unable to compute estimate due to an internal system variance. Please try again later.` The exact failing value exists only in the protected volatile failure object until request teardown and is absent from persistence, logs, the public error, and Structured Context. No qualitative risk band is permitted. Downstream components must consume the validated representation or typed failure rather than implement private formatting rules.

The current explanation contract is prediction-only and does not perform causal inference. Without validated feature importance, the assistant cannot rank inputs or explain why a result is high and must use the deterministic message defined below. Every valid result response also requires the approved synthetic-data indicator.

`QuestionnaireRequirements` and `QuestionnaireValidationResult` remain blocked only on approved user-facing wording, units, categorical encodings, and valid ranges for manually collected fields. The portfolio MVP resolves unavailable genetic inputs through `generic_genetic_profile_v1`: read the selected artifact's exported medians for all PRS and batch-by-PC fields, attach the generic-profile provenance, and disclose that these are unmeasured assumptions. This exception applies only to those named genetic groups. No consumer may derive them from family history or population descriptors, present them as the user's genomic values, or invent defaults for any other field.

See [`ML_ARTIFACT_AUDIT.md`](ML_ARTIFACT_AUDIT.md) and [`ML_ENGINEER_HANDOFF.md`](ML_ENGINEER_HANDOFF.md) for evidence, hashes, golden values, and the required product decisions.

## Minimum retrieval boundary

`RetrievalQuery` contains normalized user information needed for semantic search, requested result limit, and optional filters supported by the approved corpus. It must not include the full questionnaire or model feature vector. The AI Architect designs semantic fields and the RAG Engineer validates and implements them.

`RetrievalQuery` must also exclude questionnaire tokens/token matrices, cryptographic session ID, and user identity. The retrieval adapter targets only the isolated scientific-publication namespace and requires metadata filters equivalent to `data_class=scientific_publication`, `document_scope=general_mental_health`, and `contains_patient_data=false`; missing or mismatched isolation metadata fails closed.

Each evidence result must distinguish:

- successful retrieval with zero or more evidence items
- no sufficiently relevant evidence
- unavailable/failed retrieval

Each evidence item must preserve a stable internal source/document ID, title, source authorship when available, publication/source name, required DOI or PMID, publication date, the retrieval-owned exact matched text string, source type, study design/evidence-hierarchy tier, peer-review/indexing status, issuing authority when applicable, quality-appraisal result and rubric version, retraction/correction state and verification time, and retrieval/reranking scores whose relevance, hierarchy, recency, and quality semantics are documented. Corpus and index versions are required at result level.

Missing optional bibliographic fields remain explicitly absent; they are never generated. Missing DOI/PMID, publication date, eligibility, quality, or current retraction-verification metadata makes an item ineligible for return. Citation display is derived only from eligible source metadata in the current retrieval result.

The result status must additionally distinguish `conflicting_evidence` when materially opposed eligible evidence is retrieved. In that state, results retain representative evidence for each supported position and expose the metadata needed to state the controversy without selecting a conclusion.

Active evidence must have a retraction check no older than 14 days. The adapter must not return a deprecated/retracted or stale-unverified record, including from a cache or already-built context window.

The retrieval result declares its configured distinct-source cap, which must be from 3 through 5 and defaults to 5. A generation cycle cannot receive more distinct source IDs than that cap; multiple matched chunks sharing one publication identity count once. Fewer sources are valid when fewer eligible relevant sources exist. A conflicting-evidence result must represent every materially supported position within the cap or return an explicit insufficient-conflict-coverage limitation.

Every generated factual medical/scientific claim carries one or more inline citation IDs mapped to these current evidence items. Raw matched text is prohibited from the response prose. The API exposes it only in separate evidence-display records so the UI can render collapsed interactive metadata containers with the exact string, DOI/PMID, and bibliographic/quality metadata without LLM regeneration.

The exact inference probability remains a separately typed immutable tool-output block with artifact provenance. It is not assigned a literature citation, because no retrieved paper validates that individual's number. Any medical/scientific interpretation in adjacent prose is a claim and requires current inline evidence.

## Structured explanation context

The context builder may pass only validated fields relevant to the current response:

- intent and allowed response purpose
- exact immutable inference result, if present
- exact evidence result, if present
- optional validated local feature-importance result, if present
- approved model/corpus limitations
- allowed citation identifiers
- safety and response-policy requirements

It does not pass a formula for calculating risk or ask the LLM to infer missing values. Retrieved literature may support inline-cited clinical context, but it does not explain what caused an individual's prediction.

## Prediction and feature-importance boundary

The current system returns predictions only and does not perform causal inference. No feature-importance tool is currently approved. The application therefore inserts: `This is a prediction, not a causal explanation. The model evaluates all 105 inputs together; no single answer can be identified as the cause of the result. Validated feature importance is not available for this result.`

A future SHAP adapter must pass ML validation and architecture/test/review approval. Its result is bound to the exact inference result and contains required provenance plus exactly three ranked localized SHAP entries: stable feature ID, rank, signed value, and direction. The LLM may accurately state which features moved the model estimate relative to its validated baseline.

SHAP reports feature importance for the model prediction; it does not identify what caused a clinical outcome. Clinical relevance may be discussed separately only when supported by current inline-cited medical evidence. Alternative feature-importance methods require separately versioned contracts.

## Public API baseline

The MVP API is versioned and session-oriented:

| Operation | Method and path | Purpose |
| --- | --- | --- |
| Create session | `POST /v1/session` | Return one opaque signed ephemeral session credential, state/API version, and fixed 30-minute inactivity expiry |
| Submit turn | `POST /v1/messages` | Authenticate from the in-memory bearer credential, validate one user message, and advance the workflow once |
| Stream turn | `POST /v1/messages:stream` | Authenticate from the in-memory bearer credential and return typed SSE progress/validated response events |
| Submit assessment | `POST /v1/assessments` | Authenticate, validate a structured assessment submission, and invoke DCMFNet only when authorized and complete |
| Reset session | `DELETE /v1/session` | Authenticate, cancel active work, remove all in-memory state, and acknowledge completion idempotently |
| Liveness | `GET /health/live` | Confirm the API process is running |
| Readiness | `GET /health/ready` | Report required artifact/index/configuration readiness without secrets |

The submit-turn request must be a discriminated union separating free text from structured questionnaire-answer updates. Exact questionnaire answer fields remain blocked on the ML contract. One request cannot silently mix an arbitrary free-text answer with unvalidated feature keys.

The response envelope must include:

- API/schema version
- deployment mode
- session state version and expiry metadata; the session credential is returned only by session creation and is never echoed in later bodies
- workflow status/response kind
- safe assistant message or structured display blocks with claim-level inline citation IDs
- missing-questionnaire information only when supplied by the questionnaire contract
- inference result only when supplied by the inference port
- evidence/citations and collapsed evidence-display metadata only when supplied by the retrieval port
- local attribution only when supplied by the validated attribution port for the current inference result
- limitations and safe typed error, if any

Valid terminal response kinds include `INTENT_CLARIFICATION_REQUIRED`, `ASSESSMENT_REDIRECTION`, `NO_ELIGIBLE_EVIDENCE`, `RETRIEVAL_UNAVAILABLE`, `GENERATION_UNAVAILABLE`, `INFERENCE_UNAVAILABLE`, and `INTERNAL_SYSTEM_VARIANCE`, in addition to successful and safety/refusal kinds. These states are not interchangeable.

The Backend Engineer may refine transport names during implementation but must preserve these semantics and record any public-contract change. HTTP status mapping must distinguish invalid transport, missing/expired session, policy rejection, internal dependency failure, and successful workflow responses that request more information.

The Framer client calls only these Modal-hosted backend routes. It sends the opaque credential in the `Authorization` header from volatile memory, never in a URL, cookie, browser store, response replay, or log. The backend requires narrow CORS/origin configuration, request-size and rate limits, and short-lived signed session credentials; an `Origin` header is not an authentication mechanism. Infrastructure or model credentials never cross this contract.

### Streaming envelope

The SSE endpoint emits only these event types:

- `status`: non-sensitive phase/progress code; never user text or model output;
- `validated_content`: a response block that has passed safety, citation, score-integrity, and causal-language validation;
- `evidence`: retrieval-owned expandable metadata records for citations already referenced by validated content;
- `done`: terminal response metadata and policy/model/corpus versions; or
- `error`: a safe typed `ServiceError` with no partial unvalidated generation.

Raw LLM tokens are not a public event type. Event sequence numbers are scoped to volatile memory and are not a persistent replay log. `Cache-Control: no-store` is mandatory, heartbeats do not renew the inactivity TTL, disconnects cancel pending work where possible, and a reconnect creates a new request rather than replaying sensitive content.

Fixed safety/refusal responses, the English-language error, and `ASSESSMENT_REDIRECTION` may return typed JSON or a terminal SSE result because they use zero LLM generation.

### Offline client state

Offline is not an API execution mode. When disconnected, Framer blocks message/assessment submission and renders `You're offline. Research estimates and evidence-based answers require a connection. No calculation has been performed.` No cached, generic-profile, simulated, or client-side `InferenceResult` is valid under this contract.

## Error contract

Every `ServiceError` has:

- stable non-sensitive error code
- safe message
- originating component
- retryable flag
- optional non-sensitive details from an approved allowlist

Minimum error families are defined in the architecture: validation/safety, session, questionnaire, artifact/configuration, inference, internal-system variance, retrieval, LLM, and response-validation errors. Internal exceptions, stack traces, raw probabilities, questionnaire values, prompts, and secrets never cross the public boundary. Internal-system variance returns no estimate and maps to the exact approved safe message above.

Retryability is explicit rather than inferred from an HTTP status. Questionnaire/schema, artifact/configuration, non-finite/out-of-range output, safety/policy, no-evidence, and response-integrity errors are non-retryable by the orchestrator. A transient inference execution interruption before any result may retry once with the same idempotency key and immutable in-memory request. Retrieval or generation availability errors do not silently switch providers or use pretrained knowledge.

`OperationalFailureEvent` contains only a coarse time bucket, component/operation/error codes, retry count, latency bucket, deployment mode, and artifact/corpus/model/policy versions. It expressly excludes raw stacks and locals, user/query text, questionnaire/feature/target metrics, probabilities/results, evidence text, session/correlation IDs, identity/network fields, headers, and credentials. `ticket.jsonl` is not a permitted sink.

Generated response content is a sequence of independently validated blocks. A citation/provenance failure invalidates its whole factual claim block; removing only the citation marker is prohibited. Remaining blocks may be returned only if they still form a coherent, complete, fully cited response with all mandatory limitations. Otherwise all generated blocks are discarded, one bounded regeneration may run, and a second failure returns `GENERATION_UNAVAILABLE` or the more specific dependency state.

## Zero-retention and India data-fence boundary

Raw text, questionnaire values/tokens, vectors, prompts containing user data, inference inputs/results, probabilities, personalized responses, and session history are prohibited from every persistent store, browser store/cache, standard log, trace, metric event, analytics event, public error, backup, and crash dump. `prototype_demo` has no sensitive audit port or database. Exact invalid values may exist only in a protected volatile failure object until request teardown.

The session contract expires after exactly 30 minutes of explicit-user inactivity. Polling does not renew it. Expiry and reset invalidate the session, cancel active work where possible, and wipe client/server memory. Sensitive responses carry `Cache-Control: no-store`; the frontend receives no provider credential and stores payload state only in memory.

The submit-turn union contains no upload/attachment variant and multipart/file payloads are rejected. Runtime model and telemetry adapters cannot transmit user/session payloads to public inference or telemetry APIs. Modal transport must use a currently documented no-payload-storage Server/Endpoint path, pinned Mumbai compute/routing, and no ordinary function/async invocation, user-bearing logs/snapshots, or persistent Modal stores. Portfolio state/consent objects enforce the India processing fence in memory and fail closed on an unauthorized route. Provider edge processing and non-sensitive platform-metadata residency remain disclosed constraints. Only pre-aggregated unlinkable product counters may persist, never session-level event records.

## Contract change process

1. Owner records the evidence and proposed semantic change under `agent_docs/`.
2. Software Architect checks ownership and downstream compatibility.
3. Consumers update adapters rather than creating private duplicate schemas.
4. Testing Agent updates contract fixtures/tests and runs affected integration paths.
5. Reviewer rechecks safety or public changes; Documentation Agent updates reviewed behavior.
