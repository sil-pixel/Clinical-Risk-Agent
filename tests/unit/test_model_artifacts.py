from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

import torch

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from clinical_risk_agent.inference import (  # noqa: E402
    ArtifactErrorCode,
    ArtifactValidationError,
    inspect_artifact,
)


class ModelArtifactInspectionTests(unittest.TestCase):
    def test_repository_artifacts_load_safely_and_match_known_integrity_facts(self) -> None:
        expected = {
            "dcmfnet_neg": {
                "target": "SCZ18_Neg_Norm",
                "checkpoint_sha256": "a1c35eaf7056fd356b77a9a075fd420757bc8806d5d64ac19b6d4c1768c68c51",
                "metadata_sha256": "20ed9d339c8ea557643b1277cf1cbb35cc4d7158f6d01f33b887c8f7271ac807",
                "tensor_count": 194,
            },
            "dcmfnet_pos": {
                "target": "SCZ18_Pos_Norm",
                "checkpoint_sha256": "f4f97b793627c230fa1b0898629c2224187e9446566545e275fe3b4c69b1b63d",
                "metadata_sha256": "d82b6ef29c667bf742fa7a5b2a4695125e21409c3c862f927c9faa59118120b2",
                "tensor_count": 250,
            },
        }

        for stem, facts in expected.items():
            with self.subTest(stem=stem):
                inspection = inspect_artifact(
                    REPOSITORY_ROOT / "model_artifacts" / f"{stem}.pt",
                    REPOSITORY_ROOT / "model_artifacts" / f"{stem}.metadata.json",
                )
                self.assertEqual(inspection.target, facts["target"])
                self.assertEqual(inspection.checkpoint_sha256, facts["checkpoint_sha256"])
                self.assertEqual(inspection.metadata_sha256, facts["metadata_sha256"])
                self.assertEqual(inspection.artifact_version, 1)
                self.assertEqual(inspection.runtime, "dcmfnet")
                self.assertEqual(inspection.feature_group_count, 11)
                self.assertEqual(inspection.feature_count, 105)
                self.assertEqual(inspection.configured_num_modalities, 9)
                self.assertEqual(inspection.tensor_count, facts["tensor_count"])
                self.assertGreater(inspection.parameter_count, 0)
                self.assertEqual(inspection.tensor_dtypes, ("torch.float32",))

    def test_sidecar_checkpoint_mismatch_fails_closed(self) -> None:
        source_metadata = REPOSITORY_ROOT / "model_artifacts" / "dcmfnet_neg.metadata.json"
        checkpoint = REPOSITORY_ROOT / "model_artifacts" / "dcmfnet_neg.pt"
        metadata = json.loads(source_metadata.read_text(encoding="utf-8"))
        metadata["target"] = "unsupported_changed_target"

        with tempfile.TemporaryDirectory() as directory:
            changed_sidecar = Path(directory) / "changed.metadata.json"
            changed_sidecar.write_text(json.dumps(metadata), encoding="utf-8")
            with self.assertRaises(ArtifactValidationError) as raised:
                inspect_artifact(checkpoint, changed_sidecar)

        self.assertEqual(raised.exception.code, ArtifactErrorCode.METADATA_MISMATCH)

    def test_invalid_feature_group_length_fails_before_inference(self) -> None:
        source_metadata = REPOSITORY_ROOT / "model_artifacts" / "dcmfnet_neg.metadata.json"
        checkpoint = REPOSITORY_ROOT / "model_artifacts" / "dcmfnet_neg.pt"
        metadata = json.loads(source_metadata.read_text(encoding="utf-8"))
        metadata["feature_schema"]["scales"][0] = metadata["feature_schema"]["scales"][0][:-1]

        with tempfile.TemporaryDirectory() as directory:
            invalid_sidecar = Path(directory) / "invalid.metadata.json"
            invalid_sidecar.write_text(json.dumps(metadata), encoding="utf-8")
            with self.assertRaises(ArtifactValidationError) as raised:
                inspect_artifact(checkpoint, invalid_sidecar)

        self.assertEqual(raised.exception.code, ArtifactErrorCode.INVALID_METADATA)

    def test_non_finite_state_dict_fails_closed(self) -> None:
        source_checkpoint = REPOSITORY_ROOT / "model_artifacts" / "dcmfnet_neg.pt"
        source_metadata = REPOSITORY_ROOT / "model_artifacts" / "dcmfnet_neg.metadata.json"
        payload = torch.load(source_checkpoint, map_location="cpu", weights_only=True)
        payload = copy.deepcopy(payload)
        first_tensor = next(iter(payload["state_dict"].values()))
        first_tensor.view(-1)[0] = float("nan")

        with tempfile.TemporaryDirectory() as directory:
            invalid_checkpoint = Path(directory) / "invalid.pt"
            torch.save(payload, invalid_checkpoint)
            with self.assertRaises(ArtifactValidationError) as raised:
                inspect_artifact(invalid_checkpoint, source_metadata)

        self.assertEqual(raised.exception.code, ArtifactErrorCode.INVALID_STATE_DICT)

    def test_layer_count_array_must_match_configured_modalities(self) -> None:
        source_metadata = REPOSITORY_ROOT / "model_artifacts" / "dcmfnet_pos.metadata.json"
        checkpoint = REPOSITORY_ROOT / "model_artifacts" / "dcmfnet_pos.pt"
        metadata = json.loads(source_metadata.read_text(encoding="utf-8"))
        metadata["model_config"]["num_layers"] = metadata["model_config"]["num_layers"][:-1]

        with tempfile.TemporaryDirectory() as directory:
            invalid_sidecar = Path(directory) / "invalid.metadata.json"
            invalid_sidecar.write_text(json.dumps(metadata), encoding="utf-8")
            with self.assertRaises(ArtifactValidationError) as raised:
                inspect_artifact(checkpoint, invalid_sidecar)

        self.assertEqual(raised.exception.code, ArtifactErrorCode.INVALID_METADATA)

    def test_unsafe_or_corrupt_checkpoint_has_no_fallback_loader(self) -> None:
        source_metadata = REPOSITORY_ROOT / "model_artifacts" / "dcmfnet_neg.metadata.json"
        with tempfile.TemporaryDirectory() as directory:
            invalid_checkpoint = Path(directory) / "invalid.pt"
            invalid_checkpoint.write_bytes(b"not a checkpoint")
            with self.assertRaises(ArtifactValidationError) as raised:
                inspect_artifact(invalid_checkpoint, source_metadata)

        self.assertEqual(raised.exception.code, ArtifactErrorCode.INVALID_CHECKPOINT)


if __name__ == "__main__":
    unittest.main()
