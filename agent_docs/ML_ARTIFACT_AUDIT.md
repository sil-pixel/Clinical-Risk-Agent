# DCMFNet Artifact and Runtime Audit

Status: Deterministic inference verified; generic genetic-input policy approved; manual field definitions pending

Owner: ML Engineer

Date: 2026-08-16

## Authoritative evidence

The user identified the sibling `../Thesis/` repository and its thesis report as the authoritative implementation and documentation. The implementation was inspected at Thesis Git revision `2f6d96db481873fce8a3ba35f29d6e4ee5359dd9`, principally:

- `Models/DCMFNet/Method/dcmfnet/model.py`
- `Models/DCMFNet/Method/dcmfnet/schema.py`
- `Models/DCMFNet/Method/dcmfnet/artifact.py`
- `Models/DCMFNet/Method/dcmfnet/predictor.py`
- `Models/DCMFNet/Method/dcmfnet/training/data.py`
- `Models/DCMFNet/Method/dcmfnet/synthetic_data/generator.py`

The repository artifacts are byte-for-byte identical to the corresponding Thesis exports. The inference-only architecture and preprocessing were ported into this repository so runtime operation does not depend on an adjacent checkout.

## Verified runtime semantics

DCMFNet is a tabular regression model. Its 11 ordered groups are:

`SUD15` (anchor), `PRS`, `SCZ15`, `ADHD9`, `ASD9`, `ACE15`, `ACE18`, `SUD18`, `SES`, `SEX` (nine fusion modalities after the anchor), and `batch_.*_x_PC` (independent modality).

This explains why the artifacts contain 11 groups while `num_modalities` is 9. The negative artifact applies two fusion layers to each fusion modality. The positive artifact uses layer depths `[5, 2, 1, 5, 4, 1, 1, 1, 5]`.

Every inference record must contain all 105 unique feature keys and no unknown keys. Values are converted to float32, NaN values are replaced with training-fitted medians, and each group is standardized as `(value - mean) / scale`. Infinite and non-numeric values fail closed. Inference is currently verified on CPU only.

Each artifact returns one raw final-linear-layer value named `normalized_symptom_severity`. The product owner defines these values as separate research risk probabilities:

| Artifact | Target | Meaning |
| --- | --- | --- |
| `dcmfnet_pos` | `SCZ18_Pos_Norm` | Positive-symptom risk probability, including risk of psychotic and manic symptoms |
| `dcmfnet_neg` | `SCZ18_Neg_Norm` | Negative-symptom risk probability, including risk of depressive symptoms |

The inference runtime does not apply sigmoid, clamp values to `[0, 1]`, create thresholds or risk bands, combine the two probabilities, or calculate feature attribution. The probabilities are raw research outputs; they are not clinically validated, diagnoses, screening results, or evidence of causality. A downstream deterministic boundary gate—not the model or LLM—must fail closed on values outside inclusive `[0.0, 1.0]`. The UI returns only the approved internal-system-variance message; the exact invalid raw value is available solely to the encrypted audit port and never standard logs.

The current exported checkpoints were trained on fully synthetic data. The thesis report provides scientific background and limitations for the research, but it does not turn these particular exports into clinically validated individual-risk models. Every result UI must state that synthetic-data models may underrepresent real-world clinical comorbidities found in the Indian healthcare ecosystem.

## Artifact inventory

| Artifact | SHA-256 | Verified facts |
| --- | --- | --- |
| `dcmfnet_neg.pt` | `a1c35eaf7056fd356b77a9a075fd420757bc8806d5d64ac19b6d4c1768c68c51` | Version 1; 194 finite float32 tensors; 71,623 parameters |
| `dcmfnet_neg.metadata.json` | `20ed9d339c8ea557643b1277cf1cbb35cc4d7158f6d01f33b887c8f7271ac807` | Exactly matches embedded configuration, schema, and target |
| `dcmfnet_pos.pt` | `f4f97b793627c230fa1b0898629c2224187e9446566545e275fe3b4c69b1b63d` | Version 1; 250 finite float32 tensors; 105,501 parameters |
| `dcmfnet_pos.metadata.json` | `d82b6ef29c667bf742fa7a5b2a4695125e21409c3c862f927c9faa59118120b2` | Exactly matches embedded configuration, schema, and target |

Artifacts are loaded with `torch.load(..., map_location="cpu", weights_only=True)`. There is no unsafe pickle fallback. Sidecar and embedded metadata must match exactly; state dictionaries load strictly into the verified architecture.

## Golden verification cases

The following values were independently generated with the authoritative Thesis runtime and now pass against this repository's adapter:

| Input fixture | Positive output | Negative output |
| --- | ---: | ---: |
| Every feature set to its exported median | `0.14801442623138428` | `0.2506878674030304` |
| Every feature set to its exported mean | `0.2374962866306305` | `0.33564072847366333` |
| Every feature set to NaN | Equals the median fixture | Equals the median fixture |

These are regression fixtures, not clinically meaningful example patients.

## Delivered implementation

- `src/clinical_risk_agent/inference/model.py`: verified DCMFNet layers and forward pass
- `src/clinical_risk_agent/inference/schema.py`: immutable schema and exact preprocessing
- `src/clinical_risk_agent/inference/runtime.py`: target-specific, CPU-only predictor
- `src/clinical_risk_agent/inference/artifacts.py`: safe artifact validation and inspection
- `src/clinical_risk_agent/contracts/model_inference.py`: typed input-schema and immutable result contracts
- `tests/unit/test_dcmfnet_runtime.py`: golden, deterministic, schema, error, and limitation tests
- `tests/unit/test_model_artifacts.py`: integrity and fail-closed artifact tests

Verification command:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_*.py' -v
```

Result: 13 tests passed.

## Remaining questionnaire work

Executable inference is unblocked, but the complete public questionnaire contract still needs approved wording, units, encodings, valid ranges, and collection rules for manually answered clinical/research variables.

For the portfolio MVP, the Product Manager approved `generic_genetic_profile_v1`: the runtime reads the selected artifact's exported training medians for the 16 PRS and four batch-by-PC inputs. These generic assumptions must be disclosed and must not be presented as measured or personalized genomic values. They are never adjusted from family history, nationality, ethnicity, race, or descent. No other unavailable measurement receives an invented default, and a conversational diet history is not sufficient for these models.

## Resolved product definition

On 2026-08-16, the product owner clarified that `SCZ18_Pos_Norm` is the positive-symptom research risk probability and `SCZ18_Neg_Norm` is the negative-symptom research risk probability. They remain distinct and must not be combined, recalculated, or modified by the LLM. The user-input collection decision remains open.
