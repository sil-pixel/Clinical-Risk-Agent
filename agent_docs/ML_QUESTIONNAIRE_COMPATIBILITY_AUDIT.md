# ML Questionnaire Compatibility Audit

Status: Prototype mapping accepted by product owner on 2026-09-24; independent source-codebook and measurement-equivalence evidence remain unresolved

Owner: ML Engineer

Date: 2026-09-18

## Decision

On 2026-09-24 the product owner accepted the current public question and option order as the prototype's exact input mapping and elected to revisit source-codebook or measurement-equivalence discrepancies if they arise. The implementation now pins this mapping in `prototype_questionnaire_v1`, validates all 85 opaque answers, and assembles the two target-specific 105-input records. This is an explicit product assumption; it does not establish that the historical CATSS/A-TAC training columns used identical codes or that retrospective self-report is measurement-equivalent to the source instrument. Public calculation remains disabled while the protected backend workflow and other release gates are absent.

Use the independently worded, code-free public copy in [`questionnaire.md`](../questionnaire.md). Never render the feature keys or source-derived internal wording archived in [`QUESTIONNAIRE_INTERNAL_MAPPING.md`](QUESTIONNAIRE_INTERNAL_MAPPING.md). The missing authoritative codebook remains a scientific limitation of the accepted prototype mapping. Public DCMFNet submission is still unavailable because the protected workflow, API, and safety release tests do not yet exist; legal/licensing review has not been recorded as complete.

The public copy and private mapping are versioned together as `prototype_questionnaire_v1` for local integration. Their agreement with each other and with the 105-feature artifact schema is tested. That is distinct from independent verification against the historical training-data dictionary.

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
| `SUD15` | Field-specific source-derived subsets within `0..5` | Integer `0..5` | Prototype mapping implemented; historical codes unconfirmed. |
| `SCZ15` | Field-specific source-derived subsets within `0..3` | Integer `0..3` | Prototype mapping implemented; historical codes unconfirmed. |
| `ADHD9` | `0=No`, `1=Yes, to some extent`, `2=Yes` | Integer `0..2` | Prototype mapping implemented; historical recoding unconfirmed. |
| `ASD9` | `0=No`, `1=Yes, to some extent`, `2=Yes` | Integer `0..2` | Prototype mapping implemented; historical recoding unconfirmed. |
| `ACE15` | Source-specific frequency, count, and duration subsets within `1..6` | Integer `1..6` | Prototype mapping implemented; historical codes unconfirmed. |
| `ACE18` | `0=No`, `1=Yes` | Binary `0|1` | Prototype mapping implemented; historical codes unconfirmed. |
| `SUD18` | Field-specific source-derived subsets within `0..7` | Integer `0..7` | Prototype mapping implemented; historical codes unconfirmed. |
| `SES` | Group `0..5`; education `1..5`; birthplace `0|1` | Group observed range `0..5` | Prototype field subsets implemented; historical codes unconfirmed. |
| `SEX` | `1|2` | `1|2` | Machine encoding and labels verified. |

The former generic `1..5` controls have been removed. Numeric bounds can now be enforced without remapping, but matching bounds alone do not prove that a displayed answer label has the same meaning as its training-data code.

## Residual source-equivalence risk

- Treating source-derived English labels as verified training-code mappings could assign the wrong integer to a valid answer while still producing plausible outputs.
- Group-level `SES=0..5` evidence does not establish which values are valid for each individual SES field.
- Median imputation cannot solve missing code semantics; it applies only after a source-compatible encoding exists.
- Item wording, time frames, field-specific transformations, and missing-value rules still require authoritative verification.

## Revisit path if new evidence conflicts

The product owner selected a provisional prototype path for local implementation. The original resolution paths remain relevant if source equivalence becomes a release requirement or a discrepancy is found:

1. **Obtain the authoritative codebook — recommended.** Provide the exact source questionnaire/version, answer labels, numeric codes, missing-value rules, time frames, and item transformations for all 85 manual fields. Update product copy to use source-faithful controls and verify every mapping in tests.
2. **Retrain and revalidate if the source labels are unsuitable.** Define a new project-specific questionnaire and explicit transformation, then retrain/export DCMFNet against those encodings and repeat predictive, calibration, fairness, artifact, and runtime validation.
3. **Keep inference disabled.** Permit questionnaire UX prototyping with deterministic synthetic fixtures only and clearly state that no model calculation is performed.

## Handoff consequence

The ML Engineer has published a versioned prototype `QuestionnaireRequirements`, a validator, and a private mapping/assembly adapter under the product owner's assumption. `QuestionnaireValidationResult` authorizes only the private local adapter for a complete, valid prototype payload; it is not a public release approval. The Frontend Engineer may prototype the code-free questionnaire, local completeness checks, accessibility behavior, and deterministic fixtures; internal keys must never appear in rendered markup or public payloads. The final model-submission action remains unavailable until the protected backend workflow and safety release gates exist.
