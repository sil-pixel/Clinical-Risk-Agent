# ML Engineer Handoff

Status: Deterministic inference ready; code-free public questionnaire drafted, legal/equivalence/machine mapping blocked

Date: 2026-08-16

## Delivered

- Verified DCMFNet model and preprocessing port from the user-designated Thesis source
- Safe, strict artifact loading and metadata validation
- Target-specific immutable inference result contract for separate positive- and negative-symptom research risk probabilities
- Exported input-schema inspection contract
- Golden-output, determinism, invalid-input, and artifact-integrity tests
- Full evidence record in [`ML_ARTIFACT_AUDIT.md`](ML_ARTIFACT_AUDIT.md)

## Contract status

| Contract | Status | Downstream use |
| --- | --- | --- |
| `ArtifactInspection` | Implemented | Readiness, identity, compatibility, and audit evidence |
| `InferenceInputSchema` | Implemented | Machine-to-machine schema discovery only; not questionnaire copy |
| `InferenceResult` | Implemented | Preserve exact target, raw output, artifact identity, and limitations |
| `QuestionnaireRequirements` | Draft | Code-free public projection and private mapping projection must remain separated; product/legal review pending |
| `QuestionnaireValidationResult` | Blocked for inference | Interactive UX and deterministic fixtures may be validated, but no questionnaire submission may authorize DCMFNet until machine mappings are verified |

Canonical implementation is under `src/clinical_risk_agent/`. Do not copy these contracts into private AI, API, or UI schemas.

## AI Architect handoff

DCMFNet may now be designed as a deterministic tool with one predictor instance per artifact. A valid call supplies all 105 exact numeric feature keys to the selected target-specific predictor. The returned result includes:

- target: `SCZ18_Pos_Norm` or `SCZ18_Neg_Norm`
- ordered predictions named `normalized_symptom_severity`
- artifact version and SHA-256
- fixed limitations

`SCZ18_Pos_Norm` is the positive-symptom research risk probability, including risk of psychotic and manic symptoms. `SCZ18_Neg_Norm` is the negative-symptom research risk probability, including risk of depressive symptoms. The Structured Context must preserve these values and identities verbatim. The LLM may explain approved terminology and limitations but must not calculate, round destructively, clamp, threshold, combine, relabel, or modify the values. It must not call either model for a diabetes/diet question; that path belongs to scientific evidence retrieval and safe general education.

Design explicit workflow outcomes for `questionnaire_contract_unavailable`, invalid structured records, artifact load failure, and inference failure. Do not design conversational collection of PRS or principal-component values. For the portfolio MVP, the context builder uses `generic_genetic_profile_v1`, populated from the selected artifact's medians for those groups, and carries its unmeasured/generic provenance through response validation.

## Remaining questionnaire verification

The Product Manager approved the wording, required-field behavior, 85-visible/20-derived split, and model-aligned group ranges in [`questionnaire.md`](../questionnaire.md). Numeric range validation may now be implemented. The exact code labels, field-specific `SES` subsets, time frames, transformations, and missing-value rules remain unavailable; see [`ML_QUESTIONNAIRE_COMPATIBILITY_AUDIT.md`](ML_QUESTIONNAIRE_COMPATIBILITY_AUDIT.md). The UI may be prototyped only with inference disabled until the original codebook mapping is supplied or the model is retrained and revalidated.

## Verification and completion evidence

```text
13 tests passed
Golden outputs match the authoritative Thesis runtime for both artifacts
Both artifacts load with weights_only=True and strict state dictionaries on CPU
Missing, unknown, non-numeric, and infinite input values fail with typed errors
NaN behavior matches training-fitted median imputation
No output transform, combined probability, or questionnaire semantics were invented
```

Next workflow owner for assessment inference: Product Manager and data owner to supply/approve the source-faithful codebook mapping or authorize retraining. In parallel, the RAG Engineer may implement scientific retrieval because it does not depend on questionnaire scoring.
