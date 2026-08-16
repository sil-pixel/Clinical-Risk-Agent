"""Safe inspection and integrity validation for exported DCMFNet artifacts.

This module deliberately does not construct DCMFNet or run inference. The
repository does not yet contain authoritative model-class, forward-pass,
preprocessing, or output-semantics evidence.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import torch
from torch import Tensor

from clinical_risk_agent.contracts import ArtifactInspection

from .errors import ArtifactErrorCode, ArtifactValidationError

_SIDECAR_KEYS = {"feature_schema", "model_config", "runtime", "target"}
_CHECKPOINT_KEYS = {
    "artifact_version",
    "feature_schema",
    "model_config",
    "state_dict",
    "target",
}
_SCHEMA_KEYS = {"feature_names", "means", "medians", "modality_names", "scales"}
_CONFIG_KEYS = {
    "dropout",
    "feature_sizes",
    "hidden_dim_min",
    "num_layers",
    "num_modalities",
    "se_reduction",
}
_SUPPORTED_ARTIFACT_VERSION = 1
_SUPPORTED_RUNTIME = "dcmfnet"


def inspect_artifact(
    checkpoint_path: str | Path,
    metadata_path: str | Path,
) -> ArtifactInspection:
    """Safely validate a checkpoint/sidecar pair without executing model code.

    Checkpoints are loaded with ``weights_only=True``. Any incompatibility is
    surfaced as a typed, non-sensitive failure; there is no unsafe fallback.
    """

    checkpoint = Path(checkpoint_path)
    sidecar = Path(metadata_path)
    _require_file(checkpoint)
    _require_file(sidecar)

    metadata = _read_metadata(sidecar)
    schema_summary = _validate_metadata(metadata)
    payload = _load_weights_only(checkpoint)
    state_dict = _validate_checkpoint(payload, metadata)

    dtypes = tuple(sorted({str(tensor.dtype) for tensor in state_dict.values()}))
    parameter_count = sum(tensor.numel() for tensor in state_dict.values())

    return ArtifactInspection(
        target=metadata["target"],
        artifact_version=payload["artifact_version"],
        runtime=metadata["runtime"],
        checkpoint_sha256=_sha256(checkpoint),
        metadata_sha256=_sha256(sidecar),
        feature_group_count=schema_summary["feature_group_count"],
        feature_count=schema_summary["feature_count"],
        configured_num_modalities=metadata["model_config"]["num_modalities"],
        tensor_count=len(state_dict),
        parameter_count=parameter_count,
        tensor_dtypes=dtypes,
    )


def _require_file(path: Path) -> None:
    if not path.is_file():
        raise ArtifactValidationError(
            ArtifactErrorCode.FILE_NOT_FOUND,
            f"Required model artifact file is unavailable: {path.name}",
        )


def _read_metadata(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ArtifactValidationError(
            ArtifactErrorCode.INVALID_JSON,
            f"Model metadata is not valid UTF-8 JSON: {path.name}",
        ) from exc
    if not isinstance(value, dict):
        raise ArtifactValidationError(
            ArtifactErrorCode.INVALID_METADATA,
            "Model metadata must be a JSON object.",
        )
    return value


def _validate_metadata(metadata: Mapping[str, Any]) -> dict[str, int]:
    if set(metadata) != _SIDECAR_KEYS:
        _invalid_metadata("Model metadata has missing or unsupported top-level fields.")
    if metadata["runtime"] != _SUPPORTED_RUNTIME:
        _invalid_metadata("Model metadata declares an unsupported runtime.")
    if not isinstance(metadata["target"], str) or not metadata["target"]:
        _invalid_metadata("Model target must be a non-empty string.")

    config = metadata["model_config"]
    schema = metadata["feature_schema"]
    if not isinstance(config, Mapping) or set(config) != _CONFIG_KEYS:
        _invalid_metadata("Model configuration has missing or unsupported fields.")
    if not isinstance(schema, Mapping) or set(schema) != _SCHEMA_KEYS:
        _invalid_metadata("Feature schema has missing or unsupported fields.")

    modality_names = _require_sequence(schema["modality_names"], "modality_names")
    if not modality_names or not all(isinstance(name, str) and name for name in modality_names):
        _invalid_metadata("Every modality name must be a non-empty string.")
    if len(set(modality_names)) != len(modality_names):
        _invalid_metadata("Modality names must be unique.")

    feature_names = _require_grouped_sequence(schema["feature_names"], "feature_names")
    means = _require_grouped_sequence(schema["means"], "means")
    medians = _require_grouped_sequence(schema["medians"], "medians")
    scales = _require_grouped_sequence(schema["scales"], "scales")
    group_count = len(modality_names)
    if any(len(groups) != group_count for groups in (feature_names, means, medians, scales)):
        _invalid_metadata("All feature schema collections must match the modality count.")

    feature_sizes = _require_sequence(config.get("feature_sizes"), "feature_sizes")
    if len(feature_sizes) != group_count or not all(
        isinstance(size, int) and not isinstance(size, bool) and size > 0
        for size in feature_sizes
    ):
        _invalid_metadata("feature_sizes must contain one positive integer per modality group.")

    num_modalities = config.get("num_modalities")
    if not isinstance(num_modalities, int) or isinstance(num_modalities, bool) or num_modalities <= 0:
        _invalid_metadata("num_modalities must be a positive integer.")
    num_layers = config.get("num_layers")
    if isinstance(num_layers, int) and not isinstance(num_layers, bool):
        if num_layers <= 0:
            _invalid_metadata("Scalar num_layers must be positive.")
    else:
        layer_counts = _require_sequence(num_layers, "num_layers")
        if len(layer_counts) != num_modalities or not all(
            isinstance(count, int) and not isinstance(count, bool) and count > 0
            for count in layer_counts
        ):
            _invalid_metadata(
                "Array num_layers must contain one positive integer per configured modality."
            )

    se_reduction = config.get("se_reduction")
    hidden_dim_min = config.get("hidden_dim_min")
    if not isinstance(se_reduction, int) or isinstance(se_reduction, bool) or se_reduction <= 0:
        _invalid_metadata("se_reduction must be a positive integer.")
    if not isinstance(hidden_dim_min, int) or isinstance(hidden_dim_min, bool) or hidden_dim_min <= 0:
        _invalid_metadata("hidden_dim_min must be a positive integer.")
    dropout = config.get("dropout")
    if (
        isinstance(dropout, bool)
        or not isinstance(dropout, (int, float))
        or not math.isfinite(float(dropout))
        or not 0.0 <= float(dropout) < 1.0
    ):
        _invalid_metadata("dropout must be a finite number in the interval [0, 1).")

    for index, expected_size in enumerate(feature_sizes):
        collections = (feature_names[index], means[index], medians[index], scales[index])
        if any(len(values) != expected_size for values in collections):
            _invalid_metadata(f"Feature schema group {index} does not match feature_sizes.")
        names = feature_names[index]
        if not all(isinstance(name, str) and name for name in names) or len(set(names)) != len(names):
            _invalid_metadata(f"Feature names in group {index} must be non-empty and unique.")
        _require_finite_numbers(means[index], f"means[{index}]")
        _require_finite_numbers(medians[index], f"medians[{index}]")
        _require_finite_numbers(scales[index], f"scales[{index}]")
        if any(float(scale) <= 0.0 for scale in scales[index]):
            _invalid_metadata(f"Every scale in group {index} must be positive.")

    flat_names = [name for group in feature_names for name in group]
    if len(set(flat_names)) != len(flat_names):
        _invalid_metadata("Feature names must be unique across all groups.")

    return {"feature_group_count": group_count, "feature_count": len(flat_names)}


def _load_weights_only(path: Path) -> dict[str, Any]:
    try:
        value = torch.load(path, map_location="cpu", weights_only=True)
    except Exception as exc:
        raise ArtifactValidationError(
            ArtifactErrorCode.INVALID_CHECKPOINT,
            "Checkpoint cannot be loaded safely in weights-only mode.",
        ) from exc
    if not isinstance(value, dict):
        raise ArtifactValidationError(
            ArtifactErrorCode.INVALID_CHECKPOINT,
            "Checkpoint payload must be a dictionary.",
        )
    return value


def _validate_checkpoint(
    payload: Mapping[str, Any],
    metadata: Mapping[str, Any],
) -> Mapping[str, Tensor]:
    if set(payload) != _CHECKPOINT_KEYS:
        raise ArtifactValidationError(
            ArtifactErrorCode.INVALID_CHECKPOINT,
            "Checkpoint has missing or unsupported top-level fields.",
        )
    if payload["artifact_version"] != _SUPPORTED_ARTIFACT_VERSION:
        raise ArtifactValidationError(
            ArtifactErrorCode.INVALID_CHECKPOINT,
            "Checkpoint artifact version is unsupported.",
        )
    for field in ("target", "model_config", "feature_schema"):
        if payload[field] != metadata[field]:
            raise ArtifactValidationError(
                ArtifactErrorCode.METADATA_MISMATCH,
                f"Checkpoint and sidecar disagree on {field}.",
            )

    state_dict = payload["state_dict"]
    if not isinstance(state_dict, Mapping) or not state_dict:
        _invalid_state_dict("Checkpoint state_dict must be a non-empty mapping.")
    for name, tensor in state_dict.items():
        if not isinstance(name, str) or not name:
            _invalid_state_dict("Every state_dict key must be a non-empty string.")
        if not isinstance(tensor, Tensor):
            _invalid_state_dict("Every state_dict value must be a tensor.")
        if not tensor.is_floating_point():
            _invalid_state_dict("Every state_dict tensor must use a floating-point dtype.")
        if not bool(torch.isfinite(tensor).all()):
            _invalid_state_dict("Every state_dict tensor must contain only finite values.")
    return state_dict


def _require_sequence(value: Any, field: str) -> Sequence[Any]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _invalid_metadata(f"{field} must be an array.")
    return value


def _require_grouped_sequence(value: Any, field: str) -> Sequence[Sequence[Any]]:
    groups = _require_sequence(value, field)
    if any(isinstance(group, (str, bytes)) or not isinstance(group, Sequence) for group in groups):
        _invalid_metadata(f"{field} must be an array of arrays.")
    return groups


def _require_finite_numbers(values: Sequence[Any], field: str) -> None:
    for value in values:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            _invalid_metadata(f"{field} must contain only numbers.")
        if not math.isfinite(float(value)):
            _invalid_metadata(f"{field} must contain only finite numbers.")


def _invalid_metadata(message: str) -> None:
    raise ArtifactValidationError(ArtifactErrorCode.INVALID_METADATA, message)


def _invalid_state_dict(message: str) -> None:
    raise ArtifactValidationError(ArtifactErrorCode.INVALID_STATE_DICT, message)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
