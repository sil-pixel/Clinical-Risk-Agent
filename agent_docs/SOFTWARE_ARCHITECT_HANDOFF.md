# Software Architect Handoff

Status: ML Engineer handoff completed; ready for AI Architect

Architecture scope: ARCH-01 and ARCH-02 initial baseline

## Artifacts produced

- [`ARCHITECTURE.md`](ARCHITECTURE.md): system shape, repository layout, boundaries, dependency direction, runtime flows, state/privacy policy, safety layers, dependencies, errors, observability, and testing seams.
- [`INTERFACE_CONTRACTS.md`](INTERFACE_CONTRACTS.md): contract ownership/status, approved intent values, public session API baseline, minimum retrieval/error boundaries, and blocked ML contracts.
- [`ARCHITECTURE_DECISIONS.md`](ARCHITECTURE_DECISIONS.md): accepted decision index and deferred selections.
- [`PRODUCT_PLAN.md`](PRODUCT_PLAN.md): updated to record product-owner approval.

## Decisions implementation agents must preserve

- Modular monolith: Framer presentation layer plus a Modal-hosted FastAPI-compatible backend. Framer is API-only and contains no model code or credentials.
- Explicit LangGraph workflow with injected ML, RAG, and LLM ports.
- AI Architect design ownership for the detailed LLM/LangGraph and RAG architecture; RAG and AI Engineers retain implementation ownership.
- One canonical shared contract package; no private duplicate score/citation/questionnaire schemas.
- Conversational RAG uses validated SSE blocks, never raw unvalidated model tokens. Conversational risk-calculation intent redirects to the structured questionnaire; chat cannot invoke DCMFNet.
- Offline mode is display/reset only and must state that no calculation was performed.
- Modal user-bearing transport uses only a currently documented no-payload-storage Server/Endpoint path with Mumbai compute/routing, server-side secrets, and no ordinary function/async payloads, sensitive logs/snapshots, or persistent user-data stores.
- Framer requires every approved manual assessment field before enabling submit; the backend independently assembles and validates the complete 105-variable matrix after applying only the approved generic profile.
- Intent confidence below the initial calibrated `0.85` threshold, OOD input, or unresolved incompatible intents returns a deterministic two-action clarification with no tool permissions; this threshold remains subject to evaluation.
- Invalid model values and schema/artifact failures are never retried. Only an allowlisted transient pre-result execution failure may retry once with immutable inputs and idempotency.
- No-evidence, retrieval, generation, and inference failures remain distinct. Citation failure rejects its whole factual claim block. `ticket.jsonl`, raw exception/query/payload logging, and sensitive incident records are prohibited.
- Quality gates distinguish per-request confidence from dataset accuracy: intent accuracy and macro-F1 each `>0.85`; zero observed misses on finite critical-safety fixtures; dense cosine `>0.85` only for the pinned embedding; first-pass citation matching `>85%` and unsupported claims `<=5%`; displayed citation/claim integrity `100%`; exact raw-result equality; and a controlled terminal UI state within 60 seconds.
- Retrieval evaluation reports Precision@k, Recall@k, MRR, nDCG, zero-result rate, and conflict coverage. Generation evaluation reports groundedness, answer relevance, citation completeness/provenance/entailment, unsupported claims, conflict fidelity, probability integrity, and policy compliance using versioned non-user fixtures.
- Dense/vector zero-match or failure invokes one deterministic keyword/BM25 fallback through an independently available lexical index of the same approved corpus. It retains every eligibility/privacy/citation gate, records retrieval-mode provenance, and never logs query terms.
- In-memory-only, bounded MVP session state with exact 30-minute inactivity expiry and explicit reset; raw text, questionnaire data, model inputs/results, probabilities, personalized responses, and history have no persistent destination or external-provider route.
- Structured validation before and after the LLM; immutable model and evidence results.
- New agent-generated documentation under `agent_docs/`.

## ML Engineer input

Completion update (2026-09-18): the user supplied the sibling Thesis repository as authoritative evidence. The ML Engineer verified and ported model construction and preprocessing, published inference contracts, and added golden tests. Product questionnaire copy, group-level numeric ranges, and the visible/derived split are approved. Assessment inference remains blocked by missing authoritative code labels and field semantics documented in [`ML_QUESTIONNAIRE_COMPATIBILITY_AUDIT.md`](ML_QUESTIONNAIRE_COMPATIBILITY_AUDIT.md).

Current update (2026-09-24): the product owner accepted the present option order as a prototype mapping despite the unresolved historical source-codebook and equivalence evidence. The private versioned questionnaire adapter and paired model call are implemented and tested. Public submission remains disabled pending the protected workflow and release tests; see [`ML_ENGINEER_HANDOFF.md`](ML_ENGINEER_HANDOFF.md).

Inspect both repository-supplied `.pt` files and their metadata. Treat serialized artifacts as untrusted and do not use an unsafe loading mode merely to discover content. Obtain or identify the actual DCMFNet implementation/runtime before constructing the models.

The ML Engineer owns publication of:

1. artifact identities/checksums and compatible runtime/dependencies
2. model construction/loading procedure and readiness validation
3. exact feature identifiers/order/groups/types/ranges/preprocessing/missing-value behavior
4. classification of inputs as user-collectible, derived from approved information, externally supplied, or unavailable
5. deterministic inference settings and golden test cases
6. exact output semantics and relationship between `SCZ18_Pos_Norm` and `SCZ18_Neg_Norm`
7. typed questionnaire requirements, inference request/result, and model error contracts

## Evidence observed; semantics not inferred

- Each metadata file lists 105 features across 11 named groups and matching mean/median/scale arrays.
- Each `model_config.feature_sizes` also has 11 entries, while `model_config.num_modalities` is 9.
- The positive artifact uses a nine-element `num_layers` list; the negative artifact uses scalar `num_layers: 2`.
- Feature groups include PRS and batch/PC values that may not be obtainable through an end-user questionnaire.
- The `.pt` files are PyTorch ZIP-format serialized artifacts, but the repository contains no DCMFNet model class or loader.
- Target names are `SCZ18_Pos_Norm` and `SCZ18_Neg_Norm`; their user-facing meaning and any combined result are undocumented.

The historical artifact observations above no longer block direct machine inference with exact 105-field fixtures. The accepted prototype mapping is explicitly documented and implemented; its match to the historical training column codebook remains unverified. The protected application boundary must still authorize any end-user questionnaire submission.

## Verification expected from ML Engineer

- Metadata-to-model compatibility checks fail safely and explain mismatches.
- Repository-supplied artifacts load through a documented safe procedure in a clean locked environment.
- Identical validated input produces identical finite output for each supported artifact.
- Feature order/preprocessing is tested, including missing, extra, malformed, non-finite, and wrong-shape inputs.
- Model evaluation/no-gradient settings and supported device/dtype behavior are explicit.
- Standard logs, traces, metrics, public errors, browser stores, caches, backups, and crash artifacts contain no raw probabilities, feature vectors, questionnaire tokens/values, conversation content, or personalized responses. No sensitive audit database exists in `prototype_demo`; models execute inside the approved Modal backend using the restricted endpoint and Mumbai routing/compute controls.
- Model limitations clearly state synthetic-data provenance and prohibit diagnostic interpretation.

## Blockers and feedback path

If the model implementation, training-time transforms, input provenance, or output semantics cannot be recovered, stop and document the exact missing evidence. Return model/input feasibility to the Product Manager and artifact/runtime design to the Software Architect. AI, Backend, and Frontend work must not bind to ML payloads until the registry marks them unblocked.

After ML publishes verified contracts or a precise blocker, hand off to the AI Architect to design the LLM/LangGraph and RAG architecture. The RAG Engineer then implements the approved retrieval design, followed by AI Engineer implementation. Shared system/API changes return here for review.
