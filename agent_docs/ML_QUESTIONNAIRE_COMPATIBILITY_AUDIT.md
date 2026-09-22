# ML Questionnaire Compatibility Audit

Status: Independently worded public UI drafted; product/legal review and machine mapping remain blocked

Owner: ML Engineer

Date: 2026-09-18

## Decision

Use the independently worded, code-free public copy in [`questionnaire.md`](../questionnaire.md) for review. Never render the feature keys or source-derived internal wording archived in [`QUESTIONNAIRE_INTERNAL_MAPPING.md`](QUESTIONNAIRE_INTERNAL_MAPPING.md). Do not enable public DCMFNet submission: the rewritten copy requires product, legal/licensing, and measurement-equivalence review, and the repository still lacks the authoritative column codebook needed to prove every UI-option-to-training-code mapping.

The public copy may inform product review and frontend prototyping with inference disabled. The internal mapping may inform private schema implementation only. Neither document is a complete model-compatible scoring contract until the rewritten instrument is validated and exact code meanings are verified.

## Evidence inspected

- Current exported positive and negative artifact schemas and their exact 105 feature names/order.
- Thesis preprocessing and training code, including `Models/DCMFNet/Method/dcmfnet/training/data.py`.
- Thesis synthetic-schema generator and validator at `synthetic_data/generator.py`.
- Thesis descriptive summary at `Data Preprocessing/Data Visualisation/descriptive_statistics.csv`.
- Thesis column-renaming and target-normalization code at `Data Preprocessing/Data Visualisation/rename_catss_with_mapping.py`.
- Current independently worded public draft in [`questionnaire.md`](../questionnaire.md).
- Private feature-key reference in [`QUESTIONNAIRE_INTERNAL_MAPPING.md`](QUESTIONNAIRE_INTERNAL_MAPPING.md).
- Official CATSS15 and CATSS18 twin survey documents published by the Swedish National Data Service.
- Official A-TAC response and scoring documentation published by the Gillberg Neuropsychiatry Centre.

No authoritative CATSS column codebook or `catss_column_mapping.json` is present in the Thesis repository. The public surveys establish source response descriptions, but the missing mapping file prevents final proof that each translated UI value uses the same integer code and transformation as the training matrix.

## Verified compatibility

- The model has exactly 85 manually sourced fields and 20 generic-profile fields.
- The feature names, order, and group sizes are verified: `6, 16, 23, 19, 17, 7, 4, 4, 4, 1, 4`.
- The 16 PRS and four batch-by-PC fields may be derived from artifact medians through `generic_genetic_profile_v1` as already approved.
- `SEX` uses machine values `1` and `2`; the source summary identifies those as male and female.
- Target normalization is verified as positive symptom sum divided by `46` and negative symptom sum divided by `33`.

## Range reconciliation

| Group | Approved UI encoding | Verified source/training range | Result |
| --- | --- | --- | --- |
| `SUD15` | Field-specific source-derived subsets within `0..5` | Integer `0..5` | UI descriptions complete; machine-code mapping pending. |
| `SCZ15` | Field-specific source-derived subsets within `0..3` | Integer `0..3` | UI descriptions complete; machine-code mapping pending. |
| `ADHD9` | `0=No`, `1=Yes, to some extent`, `2=Yes` | Integer `0..2` | Source labels documented; integer recoding requires confirmation. |
| `ASD9` | `0=No`, `1=Yes, to some extent`, `2=Yes` | Integer `0..2` | Source labels documented; integer recoding requires confirmation. |
| `ACE15` | Source-specific frequency, count, and duration subsets within `1..6` | Integer `1..6` | UI descriptions complete; machine-code mapping pending. |
| `ACE18` | `0=No`, `1=Yes` | Binary `0|1` | UI descriptions complete; machine-code mapping pending. |
| `SUD18` | Field-specific source-derived subsets within `0..7` | Integer `0..7` | UI descriptions complete; machine-code mapping pending. |
| `SES` | Group `0..5`; education `1..5`; birthplace `0|1` | Group observed range `0..5` | Manual labels preserved; source verification and field-specific subsets pending. |
| `SEX` | `1|2` | `1|2` | Machine encoding and labels verified. |

The former generic `1..5` controls have been removed. Numeric bounds can now be enforced without remapping, but matching bounds alone do not prove that a displayed answer label has the same meaning as its training-data code.

## Why implementation must stop

- Treating source-derived English labels as verified training-code mappings could assign the wrong integer to a valid answer while still producing plausible outputs.
- Group-level `SES=0..5` evidence does not establish which values are valid for each individual SES field.
- Median imputation cannot solve missing code semantics; it applies only after a source-compatible encoding exists.
- Item wording, time frames, field-specific transformations, and missing-value rules still require authoritative verification.

## Required resolution

Choose one path before questionnaire inference implementation:

1. **Obtain the authoritative codebook — recommended.** Provide the exact source questionnaire/version, answer labels, numeric codes, missing-value rules, time frames, and item transformations for all 85 manual fields. Update product copy to use source-faithful controls and verify every mapping in tests.
2. **Retrain and revalidate if the source labels are unsuitable.** Define a new project-specific questionnaire and explicit transformation, then retrain/export DCMFNet against those encodings and repeat predictive, calibration, fairness, artifact, and runtime validation.
3. **Keep inference disabled.** Permit questionnaire UX prototyping with deterministic synthetic fixtures only and clearly state that no model calculation is performed.

## Handoff consequence

After final product and legal review, the ML Engineer may publish public-copy requirements and private range constraints in `QuestionnaireRequirements`, but cannot publish a `QuestionnaireValidationResult` that authorizes DCMFNet until measurement equivalence and training-column mappings are verified. The Frontend Engineer may prototype the code-free questionnaire, local completeness checks, accessibility behavior, and deterministic fixtures; internal keys must never appear in rendered markup or public payloads. The final model-submission action must remain unavailable and explain that calculation is not yet enabled.
