"""Validated deterministic inference for one exported DCMFNet artifact."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import torch

from clinical_risk_agent.contracts import (
    FeatureGroup,
    InferenceInputSchema,
    InferenceResult,
    ModelTarget,
    SymptomSeverityPrediction,
)
from clinical_risk_agent.contracts.model_inference import MODEL_LIMITATIONS, OUTPUT_NAME

from .artifacts import inspect_artifact
from .errors import InferenceError, InferenceErrorCode
from .model import DeepCrossModalFusionModel
from .schema import FeatureSchema, transform_records


def build_model(config: Mapping[str, Any]) -> DeepCrossModalFusionModel:
    """Construct the exact architecture declared by an exported artifact."""

    return DeepCrossModalFusionModel(
        M=int(config["num_modalities"]),
        L=config["num_layers"],
        n_features_per_modality=list(config["feature_sizes"]),
        se_reduction=int(config["se_reduction"]),
        dropout=float(config["dropout"]),
        hidden_dim_min=int(config["hidden_dim_min"]),
    )


class DCMFNetPredictor:
    """One immutable, target-specific DCMFNet inference adapter."""

    def __init__(
        self,
        checkpoint_path: str | Path,
        metadata_path: str | Path,
        *,
        device: str = "cpu",
    ) -> None:
        self.device = torch.device(device)
        if self.device.type != "cpu":
            raise InferenceError(
                InferenceErrorCode.MODEL_LOAD_FAILED,
                "Only CPU inference is verified for the current model contract.",
            )
        self.inspection = inspect_artifact(checkpoint_path, metadata_path)
        try:
            payload = torch.load(
                Path(checkpoint_path), map_location=self.device, weights_only=True
            )
            self.model = build_model(payload["model_config"])
            self.model.load_state_dict(payload["state_dict"], strict=True)
            self.model.to(self.device).eval()
            self.schema = FeatureSchema.from_dict(payload["feature_schema"])
            self.target = ModelTarget(payload["target"])
        except (KeyError, TypeError, ValueError, RuntimeError) as exc:
            raise InferenceError(
                InferenceErrorCode.MODEL_LOAD_FAILED,
                "DCMFNet could not be constructed from the validated artifact.",
            ) from exc

    def input_schema(self) -> InferenceInputSchema:
        return InferenceInputSchema(
            target=self.target,
            groups=tuple(
                FeatureGroup(name=name, feature_names=features)
                for name, features in zip(
                    self.schema.modality_names,
                    self.schema.feature_names,
                    strict=True,
                )
            ),
            feature_count=len(self.schema.flat_feature_names),
            requires_all_feature_keys=True,
            nan_values_use_training_median=True,
        )

    def predict(
        self, records: Sequence[Mapping[str, float]]
    ) -> InferenceResult:
        try:
            arrays = transform_records(records, self.schema)
        except (TypeError, ValueError) as exc:
            code = (
                InferenceErrorCode.EMPTY_REQUEST
                if not records
                else InferenceErrorCode.INVALID_FEATURES
            )
            raise InferenceError(code, str(exc)) from exc
        tensors = [torch.from_numpy(array).to(self.device) for array in arrays]
        with torch.inference_mode():
            scores = self.model(tensors).squeeze(-1).cpu().numpy()
        if not np.isfinite(scores).all():
            raise InferenceError(
                InferenceErrorCode.NON_FINITE_OUTPUT,
                "DCMFNet produced a non-finite normalized symptom-severity value.",
            )
        return InferenceResult(
            target=self.target,
            predictions=tuple(
                SymptomSeverityPrediction(normalized_symptom_severity=float(score))
                for score in scores
            ),
            artifact_version=self.inspection.artifact_version,
            artifact_sha256=self.inspection.checkpoint_sha256,
            output_name=OUTPUT_NAME,
            limitations=MODEL_LIMITATIONS,
        )
