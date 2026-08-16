"""Canonical DCMFNet inference contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ModelTarget(str, Enum):
    POSITIVE_SYMPTOM_SEVERITY = "SCZ18_Pos_Norm"
    NEGATIVE_SYMPTOM_SEVERITY = "SCZ18_Neg_Norm"


@dataclass(frozen=True, slots=True)
class FeatureGroup:
    name: str
    feature_names: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class InferenceInputSchema:
    target: ModelTarget
    groups: tuple[FeatureGroup, ...]
    feature_count: int
    requires_all_feature_keys: bool
    nan_values_use_training_median: bool


@dataclass(frozen=True, slots=True)
class SymptomSeverityPrediction:
    """One raw research risk probability for a normalized symptom target."""

    normalized_symptom_severity: float


@dataclass(frozen=True, slots=True)
class InferenceResult:
    target: ModelTarget
    predictions: tuple[SymptomSeverityPrediction, ...]
    artifact_version: int
    artifact_sha256: str
    output_name: str
    limitations: tuple[str, ...]


OUTPUT_NAME = "normalized_symptom_severity"
MODEL_LIMITATIONS = (
    "Research-only symptom risk probability for a normalized symptom-severity target.",
    "Not clinically calibrated; not a diagnosis, screening result, or medical advice.",
    "Trained on fully synthetic data and not clinically validated for individual use.",
    "Raw model output is returned without clamping, thresholding, risk bands, or combination across targets.",
)
