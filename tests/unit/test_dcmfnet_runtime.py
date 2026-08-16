from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from clinical_risk_agent.contracts import ModelTarget  # noqa: E402
from clinical_risk_agent.inference import (  # noqa: E402
    DCMFNetPredictor,
    InferenceError,
    InferenceErrorCode,
)


ARTIFACTS = {
    ModelTarget.POSITIVE_SYMPTOM_SEVERITY: (
        "dcmfnet_pos",
        0.14801442623138428,
        0.2374962866306305,
    ),
    ModelTarget.NEGATIVE_SYMPTOM_SEVERITY: (
        "dcmfnet_neg",
        0.2506878674030304,
        0.33564072847366333,
    ),
}


def load_predictor(target: ModelTarget) -> DCMFNetPredictor:
    stem = ARTIFACTS[target][0]
    artifact_root = REPOSITORY_ROOT / "model_artifacts"
    return DCMFNetPredictor(
        artifact_root / f"{stem}.pt",
        artifact_root / f"{stem}.metadata.json",
    )


def record_from_schema(
    predictor: DCMFNetPredictor, source: str
) -> dict[str, float]:
    values = getattr(predictor.schema, source)
    return {
        name: value
        for names, group_values in zip(
            predictor.schema.feature_names, values, strict=True
        )
        for name, value in zip(names, group_values, strict=True)
    }


class DCMFNetRuntimeTests(unittest.TestCase):
    def test_golden_predictions_match_authoritative_thesis_runtime(self) -> None:
        for target, (_, median_output, mean_output) in ARTIFACTS.items():
            with self.subTest(target=target):
                predictor = load_predictor(target)
                median_record = record_from_schema(predictor, "medians")
                mean_record = record_from_schema(predictor, "means")

                median_result = predictor.predict([median_record])
                mean_result = predictor.predict([mean_record])

                self.assertAlmostEqual(
                    median_result.predictions[0].normalized_symptom_severity,
                    median_output,
                    places=7,
                )
                self.assertAlmostEqual(
                    mean_result.predictions[0].normalized_symptom_severity,
                    mean_output,
                    places=7,
                )

    def test_nan_values_are_imputed_with_exported_training_medians(self) -> None:
        for target, (_, median_output, _) in ARTIFACTS.items():
            with self.subTest(target=target):
                predictor = load_predictor(target)
                nan_record = {
                    name: math.nan for name in predictor.schema.flat_feature_names
                }
                result = predictor.predict([nan_record])
                self.assertAlmostEqual(
                    result.predictions[0].normalized_symptom_severity,
                    median_output,
                    places=7,
                )

    def test_schema_preserves_exported_group_order_and_feature_count(self) -> None:
        predictor = load_predictor(ModelTarget.POSITIVE_SYMPTOM_SEVERITY)
        schema = predictor.input_schema()

        self.assertEqual(schema.target, ModelTarget.POSITIVE_SYMPTOM_SEVERITY)
        self.assertEqual(schema.feature_count, 105)
        self.assertEqual(
            tuple(group.name for group in schema.groups),
            (
                "SUD15",
                "PRS",
                "SCZ15",
                "ADHD9",
                "ASD9",
                "ACE15",
                "ACE18",
                "SUD18",
                "SES",
                "SEX",
                "batch_.*_x_PC",
            ),
        )
        self.assertTrue(schema.requires_all_feature_keys)
        self.assertTrue(schema.nan_values_use_training_median)

    def test_prediction_result_preserves_target_artifact_and_limitations(self) -> None:
        predictor = load_predictor(ModelTarget.NEGATIVE_SYMPTOM_SEVERITY)
        result = predictor.predict([record_from_schema(predictor, "means")])

        self.assertEqual(result.target, ModelTarget.NEGATIVE_SYMPTOM_SEVERITY)
        self.assertEqual(result.output_name, "normalized_symptom_severity")
        self.assertEqual(result.artifact_sha256, predictor.inspection.checkpoint_sha256)
        self.assertTrue(any("not a diagnosis" in item.lower() for item in result.limitations))
        self.assertTrue(any("without clamping" in item.lower() for item in result.limitations))

    def test_predictions_are_deterministic_and_batch_order_is_preserved(self) -> None:
        predictor = load_predictor(ModelTarget.POSITIVE_SYMPTOM_SEVERITY)
        median_record = record_from_schema(predictor, "medians")
        mean_record = record_from_schema(predictor, "means")

        first = predictor.predict([median_record, mean_record])
        second = predictor.predict([median_record, mean_record])

        self.assertEqual(first, second)
        self.assertAlmostEqual(
            first.predictions[0].normalized_symptom_severity,
            ARTIFACTS[ModelTarget.POSITIVE_SYMPTOM_SEVERITY][1],
            places=7,
        )
        self.assertAlmostEqual(
            first.predictions[1].normalized_symptom_severity,
            ARTIFACTS[ModelTarget.POSITIVE_SYMPTOM_SEVERITY][2],
            places=7,
        )

    def test_invalid_records_fail_with_typed_errors(self) -> None:
        predictor = load_predictor(ModelTarget.NEGATIVE_SYMPTOM_SEVERITY)
        valid = record_from_schema(predictor, "means")

        cases = []
        missing = dict(valid)
        missing.pop(next(iter(missing)))
        cases.append(missing)
        unknown = dict(valid)
        unknown["invented_feature"] = 1.0
        cases.append(unknown)
        non_numeric = dict(valid)
        non_numeric[next(iter(non_numeric))] = "invalid"  # type: ignore[assignment]
        cases.append(non_numeric)
        infinite = dict(valid)
        infinite[next(iter(infinite))] = math.inf
        cases.append(infinite)

        for record in cases:
            with self.subTest(record=list(record)[-1]):
                with self.assertRaises(InferenceError) as raised:
                    predictor.predict([record])
                self.assertEqual(
                    raised.exception.code, InferenceErrorCode.INVALID_FEATURES
                )

        with self.assertRaises(InferenceError) as raised:
            predictor.predict([])
        self.assertEqual(raised.exception.code, InferenceErrorCode.EMPTY_REQUEST)

    def test_non_cpu_runtime_is_rejected_until_verified(self) -> None:
        stem = ARTIFACTS[ModelTarget.POSITIVE_SYMPTOM_SEVERITY][0]
        artifact_root = REPOSITORY_ROOT / "model_artifacts"
        with self.assertRaises(InferenceError) as raised:
            DCMFNetPredictor(
                artifact_root / f"{stem}.pt",
                artifact_root / f"{stem}.metadata.json",
                device="cuda",
            )
        self.assertEqual(raised.exception.code, InferenceErrorCode.MODEL_LOAD_FAILED)


if __name__ == "__main__":
    unittest.main()
