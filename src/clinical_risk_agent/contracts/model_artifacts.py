"""Non-sensitive contracts for model artifact readiness."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ArtifactInspection:
    """Integrity facts established from one artifact/sidecar pair."""

    target: str
    artifact_version: int
    runtime: str
    checkpoint_sha256: str
    metadata_sha256: str
    feature_group_count: int
    feature_count: int
    configured_num_modalities: int
    tensor_count: int
    parameter_count: int
    tensor_dtypes: tuple[str, ...]
