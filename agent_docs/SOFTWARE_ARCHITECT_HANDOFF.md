# Software Architect Handoff

Status: ML Engineer handoff completed; ready for AI Architect

Architecture scope: ARCH-01 and ARCH-02 initial baseline

## Artifacts produced

- [`ARCHITECTURE.md`](ARCHITECTURE.md): system shape, repository layout, boundaries, dependency direction, runtime flows, state/privacy policy, safety layers, dependencies, errors, observability, and testing seams.
- [`INTERFACE_CONTRACTS.md`](INTERFACE_CONTRACTS.md): contract ownership/status, approved intent values, public session API baseline, minimum retrieval/error boundaries, and blocked ML contracts.
- [`ARCHITECTURE_DECISIONS.md`](ARCHITECTURE_DECISIONS.md): ten accepted decisions and deferred selections.
- [`PRODUCT_PLAN.md`](PRODUCT_PLAN.md): updated to record product-owner approval.

## Decisions implementation agents must preserve

- Modular monolith: FastAPI backend plus API-only Streamlit frontend.
- Explicit LangGraph workflow with injected ML, RAG, and LLM ports.
- AI Architect design ownership for the detailed LLM/LangGraph and RAG architecture; RAG and AI Engineers retain implementation ownership.
- One canonical shared contract package; no private duplicate score/citation/questionnaire schemas.
- In-memory, bounded, expiring MVP operational session state; raw probabilities and questionnaire tokens persist only in a separate encrypted, access-controlled audit store tied to a cryptographically random session ID and never identity.
- Structured validation before and after the LLM; immutable model and evidence results.
- New agent-generated documentation under `agent_docs/`.

## ML Engineer input

Completion update (2026-08-16): the user supplied the sibling Thesis repository as authoritative evidence. The ML Engineer verified and ported model construction and preprocessing, published inference contracts, and added golden tests. See [`ML_ENGINEER_HANDOFF.md`](ML_ENGINEER_HANDOFF.md). The questionnaire feasibility and user-facing output terminology items remain open Product Manager decisions.

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

These are blockers to concrete inference and questionnaire contracts, not permission to invent defaults or interpretations.

## Verification expected from ML Engineer

- Metadata-to-model compatibility checks fail safely and explain mismatches.
- Repository-supplied artifacts load through a documented safe procedure in a clean locked environment.
- Identical validated input produces identical finite output for each supported artifact.
- Feature order/preprocessing is tested, including missing, extra, malformed, non-finite, and wrong-shape inputs.
- Model evaluation/no-gradient settings and supported device/dtype behavior are explicit.
- Standard logs, traces, metrics, and public errors contain no raw probabilities, feature vectors, or questionnaire tokens/values. The protected audit database is the only permitted persistence destination and must enforce the configured India data fence.
- Model limitations clearly state synthetic-data provenance and prohibit diagnostic interpretation.

## Blockers and feedback path

If the model implementation, training-time transforms, input provenance, or output semantics cannot be recovered, stop and document the exact missing evidence. Return model/input feasibility to the Product Manager and artifact/runtime design to the Software Architect. AI, Backend, and Frontend work must not bind to ML payloads until the registry marks them unblocked.

After ML publishes verified contracts or a precise blocker, hand off to the AI Architect to design the LLM/LangGraph and RAG architecture. The RAG Engineer then implements the approved retrieval design, followed by AI Engineer implementation. Shared system/API changes return here for review.
