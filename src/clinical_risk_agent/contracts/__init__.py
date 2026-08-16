"""Canonical cross-component contracts."""

from .model_artifacts import ArtifactInspection
from .model_inference import (
    FeatureGroup,
    InferenceInputSchema,
    InferenceResult,
    ModelTarget,
    SymptomSeverityPrediction,
)

__all__ = [
    "ArtifactInspection",
    "FeatureGroup",
    "InferenceInputSchema",
    "InferenceResult",
    "ModelTarget",
    "SymptomSeverityPrediction",
]
