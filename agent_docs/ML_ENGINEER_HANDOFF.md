# ML Engineer Handoff

Status: Deterministic inference ready; questionnaire requirements approved for implementation and awaiting codebook verification

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
| `QuestionnaireRequirements` | Ready to implement | Use approved 85-visible/20-derived contract; verify training-codebook compatibility before release |
| `QuestionnaireValidationResult` | Ready to implement | Fail closed on missing, invalid, non-scored, unknown, or codebook-unverified values |

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

The Product Manager approved the wording, response options, ranges, required-field behavior, and 85-visible/20-derived split in [`questionnaire.md`](../questionnaire.md). The ML Engineer must verify each approved mapping, order, time frame, and transformation against the authoritative training codebook before public inference. A mismatch fails readiness and returns to product review; it must not be repaired with an undocumented local mapping. The UI must describe results as questionnaire-based simulated research estimates using generic, unmeasured genetic assumptions—not personalized genetic probabilities.

## Verification and completion evidence

```text
13 tests passed
Golden outputs match the authoritative Thesis runtime for both artifacts
Both artifacts load with weights_only=True and strict state dictionaries on CPU
Missing, unknown, non-numeric, and infinite input values fail with typed errors
NaN behavior matches training-fitted median imputation
No output transform, combined probability, or questionnaire semantics were invented
```

Next workflow owners: ML Engineer for questionnaire contract implementation/codebook verification, then RAG and AI Engineers under the approved AI architecture.
