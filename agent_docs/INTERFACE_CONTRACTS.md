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
| `SafetyDecision` | Safety → workflow/API | AI Architect (design), AI Engineer (implementation) | Architecture-defined categories; wording/escalation policy remains open |
| `IntentDecision` | Router → LangGraph | AI Architect (design), AI Engineer (implementation) | Approved intent enum; confidence/fallback details finalized in AI architecture |
| `DeploymentMode` | Composition root → all workflow/results/telemetry | Software Architect | **Architecture-approved:** `prototype_demo`; `hospital_silent_research` reserved and unavailable until separately gated |
| `ArtifactInspection` | DCMFNet artifact validator → readiness/tests | ML Engineer | **Implemented:** integrity/readiness facts |
| `InferenceInputSchema` | DCMFNet adapter → graph/backend/tools | ML Engineer | **Implemented:** exact machine feature groups/order; not user-facing questionnaire copy |
| `QuestionnaireRequirements` | ML/questionnaire → graph/UI | ML Engineer | **Blocked** on collection feasibility, encodings, ranges, wording, and provenance |
| `QuestionnaireValidationResult` | Questionnaire validator → graph | ML Engineer | **Blocked** on requirements contract |
| `InferenceRequest` | Graph → DCMFNet port | ML Engineer | **Implemented internally:** selected target plus records containing all 105 exact numeric feature keys |
| `InferenceResult` | DCMFNet port → graph/context/API | ML Engineer | **Implemented:** immutable, separate positive- or negative-symptom research risk probability and artifact identity |
| `RetrievalQuery` | Graph → RAG port | AI Architect (design), RAG Engineer (implementation) | Minimum boundary below; AI/RAG architecture and corpus policy required |
| `EvidenceResult` | RAG port → graph/context/API | AI Architect (design), RAG Engineer (implementation) | Minimum provenance boundary below; final fields pending corpus selection |
| `StructuredExplanationContext` | Context builder → LLM port | AI Architect (design), AI Engineer (implementation) | Must compose immutable validated results; finalized after ML/RAG contracts |
| `ValidatedAssistantResponse` | Response validator → API/UI | AI Architect (design), AI Engineer (implementation) | Envelope below; content blocks finalized with Backend/Frontend |
| Public session transport | FastAPI ↔ Streamlit | Backend Engineer | Architecture baseline below; finalized only after workflow contracts stabilize |
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

`risk_assessment` alone does not authorize inference. The graph may invoke DCMFNet only when the user explicitly requests positive/psychotic-symptom or negative/depressive-symptom risk calculation, safety permits processing, and deterministic questionnaire validation reports complete valid input. Scientific or educational discussion of those symptoms routes to RAG without inference. `explain_my_risk` consumes a stored immutable result and does not rerun the model unless a new assessment is explicitly requested.

General mental health, genetics/environmental factors, diet/lifestyle/diabetes/physical health, and mental-health-related general medication/treatment education may use RAG under the approved source policy. Unrelated general medical questions use the minimal out-of-scope response contract and do not invoke full RAG or DCMFNet.

## Minimum safety decision

`SafetyDecision` must include:

- a stable policy category suitable for deterministic graph routing
- whether normal processing may continue
- a safe user-facing response when processing must stop
- policy/ruleset version
- limitations or escalation configuration status

It must not contain a diagnosis. The AI Architect specifies the policy categories and the AI Engineer implements/tests them; neither may allow a probabilistic model to be the sole gate for deterministic validation.

## ML-owned contracts

The canonical contracts are implemented under `src/clinical_risk_agent/contracts/` and the runtime under `src/clinical_risk_agent/inference/`. The implementation is based on the user-designated Thesis source at revision `2f6d96db481873fce8a3ba35f29d6e4ee5359dd9` and is covered by cross-runtime golden fixtures.

Each target-specific call requires all 105 unique feature keys in the exact exported schema. Unknown or missing keys, non-numeric values, and infinite values fail closed. NaN values are replaced with exported training medians; values are then standardized with exported training means and scales. CPU inference is the only verified device mode.

The result contains the exact artifact target—`SCZ18_Pos_Norm` or `SCZ18_Neg_Norm`—and raw predictions named `normalized_symptom_severity`, plus artifact version, checkpoint SHA-256, and fixed limitations. The product definition identifies the positive target as risk probability for positive schizophrenia symptoms, including psychotic and manic symptoms, and the negative target as risk probability for negative schizophrenia symptoms, including depressive symptoms. These research probabilities are not clinically validated, diagnoses, screening results, causal effects, thresholds, or a combined score. Consumers must preserve numeric and identity fields exactly and keep the two probabilities separate.

A deterministic presenter—not the LLM—produces a validated percentage representation. High out-of-range raw values are not rejected and display as `99.9% at risk`; raw values below `0.0` display as `No risk could be seen`. Exact raw values remain unchanged internally. No qualitative risk band is permitted. Downstream components must consume the validated representation rather than implement private formatting rules.

`QuestionnaireRequirements` and `QuestionnaireValidationResult` remain blocked only on approved user-facing wording, units, categorical encodings, and valid ranges for manually collected fields. The portfolio MVP resolves unavailable genetic inputs through `generic_genetic_profile_v1`: read the selected artifact's exported medians for all PRS and batch-by-PC fields, attach the generic-profile provenance, and disclose that these are unmeasured assumptions. This exception applies only to those named genetic groups. No consumer may derive them from family history or population descriptors, present them as the user's genomic values, or invent defaults for any other field.

See [`ML_ARTIFACT_AUDIT.md`](ML_ARTIFACT_AUDIT.md) and [`ML_ENGINEER_HANDOFF.md`](ML_ENGINEER_HANDOFF.md) for evidence, hashes, golden values, and the required product decisions.

## Minimum retrieval boundary

`RetrievalQuery` contains normalized user information needed for semantic search, requested result limit, and optional filters supported by the approved corpus. It must not include the full questionnaire or model feature vector. The AI Architect designs semantic fields and the RAG Engineer validates and implements them.

Each evidence result must distinguish:

- successful retrieval with zero or more evidence items
- no sufficiently relevant evidence
- unavailable/failed retrieval

Each evidence item must preserve a stable internal source/document ID, title, source authorship when available, publication/source name, publication date when available, stable locator such as DOI/PMID/approved URL when available, the retrieved excerpt/chunk, and retrieval/reranking scores whose semantics are documented. Corpus and index versions are required at result level.

Missing bibliographic fields remain explicitly absent; they are never generated. Citation display is derived only from returned source metadata.

## Structured explanation context

The context builder may pass only validated fields relevant to the current response:

- intent and allowed response purpose
- exact immutable inference result, if present
- exact evidence result, if present
- approved model/corpus limitations
- allowed citation identifiers
- safety and response-policy requirements

It does not pass a formula for calculating risk, ask the LLM to infer missing values, or treat model input features as causal explanations. Feature attribution requires a separately verified deterministic model tool and product approval; it is not assumed by the current artifacts.

## Public API baseline

The MVP API is versioned and session-oriented:

| Operation | Method and path | Purpose |
| --- | --- | --- |
| Create session | `POST /v1/sessions` | Return an opaque session ID and state/API version |
| Submit turn | `POST /v1/sessions/{session_id}/messages` | Validate one user message/structured answer update and advance the workflow once |
| Reset session | `DELETE /v1/sessions/{session_id}` | Remove in-memory state and acknowledge completion idempotently |
| Liveness | `GET /health/live` | Confirm the API process is running |
| Readiness | `GET /health/ready` | Report required artifact/index/configuration readiness without secrets |

The submit-turn request must be a discriminated union separating free text from structured questionnaire-answer updates. Exact questionnaire answer fields remain blocked on the ML contract. One request cannot silently mix an arbitrary free-text answer with unvalidated feature keys.

The response envelope must include:

- API/schema version and correlation ID
- deployment mode
- session ID
- workflow status/response kind
- safe assistant message or structured display blocks
- missing-questionnaire information only when supplied by the questionnaire contract
- inference result only when supplied by the inference port
- evidence/citations only when supplied by the retrieval port
- limitations and safe typed error, if any

The Backend Engineer may refine transport names during implementation but must preserve these semantics and record any public-contract change. HTTP status mapping must distinguish invalid transport, missing/expired session, policy rejection, internal dependency failure, and successful workflow responses that request more information.

## Error contract

Every `ServiceError` has:

- stable non-sensitive error code
- safe message
- originating component
- retryable flag
- correlation ID
- optional non-sensitive details from an approved allowlist

Minimum error families are defined in the architecture: validation/safety, session, questionnaire, artifact/configuration, inference, retrieval, LLM, and response-validation errors. Internal exceptions, stack traces, questionnaire values, prompts, and secrets never cross the public boundary.

## Contract change process

1. Owner records the evidence and proposed semantic change under `agent_docs/`.
2. Software Architect checks ownership and downstream compatibility.
3. Consumers update adapters rather than creating private duplicate schemas.
4. Testing Agent updates contract fixtures/tests and runs affected integration paths.
5. Reviewer rechecks safety or public changes; Documentation Agent updates reviewed behavior.
