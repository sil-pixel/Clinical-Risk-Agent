# Interface Contract Registry

Status: Architecture baseline; payloads marked **blocked** must not be implemented by downstream consumers

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
| `QuestionnaireRequirements` | ML/questionnaire → graph/UI | ML Engineer | **Blocked** on artifact/input feasibility |
| `QuestionnaireValidationResult` | Questionnaire validator → graph | ML Engineer | **Blocked** on requirements contract |
| `InferenceRequest` | Graph → DCMFNet port | ML Engineer | **Blocked** on model loader and feature semantics |
| `InferenceResult` | DCMFNet port → graph/context/API | ML Engineer | **Blocked** on positive/negative output semantics |
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

## Minimum safety decision

`SafetyDecision` must include:

- a stable policy category suitable for deterministic graph routing
- whether normal processing may continue
- a safe user-facing response when processing must stop
- policy/ruleset version
- limitations or escalation configuration status

It must not contain a diagnosis. The AI Architect specifies the policy categories and the AI Engineer implements/tests them; neither may allow a probabilistic model to be the sole gate for deterministic validation.

## ML-owned contracts — blocked

Before publishing `QuestionnaireRequirements`, `InferenceRequest`, or `InferenceResult`, the ML Engineer must establish from executable evidence:

- safe loading procedure and required DCMFNet code/runtime
- artifact identity/checksum and metadata compatibility
- feature identifiers, order, grouping, types, valid values, preprocessing, missing-value rules, and which values are genuinely user-collectible
- the meaning and relationship of `SCZ18_Pos_Norm` and `SCZ18_Neg_Norm`
- output transform, range, units/meaning, calibration limitations, and whether “probability” is technically supported
- deterministic runtime settings and error conditions

Downstream agents may depend on a generic inference port returning an opaque validated result, but they must not create concrete questionnaire fields, defaults, target labels, combined scores, thresholds, risk bands, factor attribution, or explanations until this contract is unblocked.

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
