# ML Engineer Handoff

Status: **Complete for private `prototype_demo` integration**. Public assessment delivery belongs to the AI, Backend, Frontend, and Testing owners. Historical source-instrument equivalence is an explicitly accepted prototype assumption, not a verified finding.

Updated: 2026-09-24

## Decision and scope

On 2026-09-24 the product owner accepted the existing public question and answer-option order as the exact mapping to use for this prototype. If source-codebook or measurement-equivalence evidence later reveals a discrepancy, return the affected mapping to Product and ML review. This decision authorizes implementation against `prototype_questionnaire_v1`; it does not establish clinical validity, source-instrument equivalence, or suitability for a hospital product. The missing authoritative CATSS column codebook and the adult-retrospective versus source-instrument difference remain recorded in [`ML_QUESTIONNAIRE_COMPATIBILITY_AUDIT.md`](ML_QUESTIONNAIRE_COMPATIBILITY_AUDIT.md).

The ML-owned implementation is usable inside the local Python process. The public questionnaire still cannot submit to a deployed model because the protected assessment workflow, API, session and safety boundaries, and release tests are not implemented.

## Delivered to downstream owners

| Deliverable | Canonical location | Contract |
| --- | --- | --- |
| Safe artifact inspection and CPU-only DCMFNet predictor | `src/clinical_risk_agent/inference/artifacts.py`, `runtime.py` | `ArtifactInspection`, `InferenceInputSchema`, `InferenceResult` |
| Versioned opaque questionnaire and validation result | `src/clinical_risk_agent/contracts/questionnaire.py` | `QuestionnaireRequirements`, `QuestionnaireValidationResult` |
| Private option-to-feature mapping, 105-input assembly, paired inference | `src/clinical_risk_agent/inference/questionnaire.py` | `QuestionnaireAssessmentResult` |
| Artifact/runtime evidence and golden fixtures | [`ML_ARTIFACT_AUDIT.md`](ML_ARTIFACT_AUDIT.md), `tests/unit/test_dcmfnet_runtime.py`, `tests/unit/test_model_artifacts.py` | Fixed artifact identity and output regression |
| Questionnaire and frontend/backend alignment checks | `tests/unit/test_questionnaire_contract.py`, `frontend/test/` | Opaque IDs, answer validity, 85/20 assembly, separate targets |

The public questionnaire copy and displayed order live in `questionnaire.md` and `frontend/src/questionnaireData.js`. Internal feature names, numeric codes, and the 20 hidden fields belong only on the backend. The browser must send opaque question and option IDs; it must not submit machine feature keys or numeric model values.

## Integration contract

1. Load exactly one `DCMFNetPredictor` for each pinned artifact pair: `model_artifacts/dcmfnet_pos.pt` with its matching metadata, and `model_artifacts/dcmfnet_neg.pt` with its matching metadata. Loading validates artifact identity, schema, finite weights, and target. CPU is the verified execution device.
2. Accept only a structured answer mapping for `prototype_questionnaire_v1`. `questionnaire_requirements()` exposes 85 opaque IDs and allowed option IDs. `validate_questionnaire(answers, version=...)` reports missing, invalid, and unknown IDs. `memory_unknown` is not scored and does not authorize inference. An unsupported version raises `ValueError`.
3. After independent workflow authorization, call `predict_questionnaire(answers, positive_predictor, negative_predictor, version=...)`. It revalidates the questionnaire, maps all 85 manual fields, fills the 16 PRS and four batch-by-PC fields from **each selected artifact's own training medians**, builds each exact 105-feature record, and invokes the two target-specific predictors. Do not derive generic values from family history or population descriptors. No other unanswered field receives an invented default.
4. Preserve the immutable positive and negative `InferenceResult` objects separately. Their targets are `SCZ18_Pos_Norm` and `SCZ18_Neg_Norm`; each contains one raw `normalized_symptom_severity` value, artifact version, SHA-256, and fixed limitations. The paired adapter rejects a non-finite or out-of-`[0.0, 1.0]` output and returns no assessment result. The API must convert that failure to the approved safe internal-system-variance response without exposing the raw value.
5. The ML adapter does not provide route authorization, transport validation, session handling, a public API, presentation percentages, scientific evidence, SHAP attribution, or an LLM explanation. The AI/Backend workflow owns those boundaries. DCMFNet is callable only for an explicitly authorized, complete structured assessment; no chat, educational, diet, diabetes, medication, or general-medical route may invoke it.

The age-18 adverse-experience section displays `q074`, `q075`, `q076`, then `q073`; the private mapping binds IDs rather than display position. Version and target checks must remain in place if copy, order, options, or artifacts change. Do not duplicate the private mapping in the UI or AI layer.

## Verified evidence

- Both exported artifacts match the audited Thesis exports and load through `weights_only=True` with strict state dictionaries. Golden median/mean results and deterministic CPU inference are recorded in [`ML_ARTIFACT_AUDIT.md`](ML_ARTIFACT_AUDIT.md).
- The current questionnaire adapter covers 85 manual fields, creates 20 target-specific generic-profile fields, and yields exact schema-ordered 105-feature records for both artifacts.
- Tests reject missing, unknown, unscored, and out-of-range option IDs; verify representative field codes and the unusual `q073` display order; compare the backend's opaque option contract against the frontend's actual option IDs; and confirm separate unchanged model outputs.
- On 2026-09-24, `.venv/bin/python -m unittest discover -s tests -q` passed **19 tests**; `npm test` passed **12 tests** in `frontend/`; `npm run build` succeeded. The Python/frontend contract test needs Node.js to run and skips that check when Node.js is unavailable.

For a clean environment, install this package's dependencies from `pyproject.toml`, then run `python -m unittest discover -s tests -q` and, in `frontend/`, `npm test` and `npm run build`. Test fixtures are synthetic; they are not clinically meaningful participants.

## Remaining limitations and transfer

- The accepted option-order mapping is a product-owner prototype assumption. Exact historical code direction, recoding, transformations, missing-value handling, source time frames, and equivalence of adult retrospective self-report to the original source instruments have not been independently established. Do not describe them as verified. A discovered mismatch returns to ML/Product for a versioned contract change and regression tests; retraining and revalidation may be necessary.
- DCMFNet was trained on fully synthetic data. Its raw outputs are research-only, not clinically calibrated, diagnostic, screening, causal, or suitable for care decisions. No feature importance is available from this handoff.
- AI Engineer: bind the adapter only after deterministic safety, mode, route, session, and completeness checks; preserve targets and values through graph state and response validation; handle questionnaire/artifact/inference failures as distinct typed outcomes.
- Backend Engineer: expose the structured questionnaire request only through the approved protected API, enforce volatile state and safe errors, load/pin both artifacts, and never log answers, feature vectors, raw probabilities, or personalized responses.
- Frontend Engineer: keep opaque IDs and the Calculate button disabled until that protected API and safety tests pass; then display only validated separate results and the required prototype, synthetic-data, and generic-profile limitations.
- Testing Agent: run the questionnaire-to-model contract tests plus negative-path, routing, result-integrity, privacy, expiry, and end-to-end assessment checks before public submission is enabled.

ML has no further implementation prerequisite for the private prototype adapter. Scientific equivalence and release suitability remain open findings, while application integration belongs to the downstream owners above.
