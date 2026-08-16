"""Safe, typed failures for model artifact validation."""

from __future__ import annotations

from enum import Enum


class ArtifactErrorCode(str, Enum):
    """Stable non-sensitive artifact validation error codes."""

    FILE_NOT_FOUND = "artifact_file_not_found"
    INVALID_JSON = "artifact_metadata_invalid_json"
    INVALID_METADATA = "artifact_metadata_invalid"
    INVALID_CHECKPOINT = "artifact_checkpoint_invalid"
    METADATA_MISMATCH = "artifact_metadata_mismatch"
    INVALID_STATE_DICT = "artifact_state_dict_invalid"


class ArtifactValidationError(RuntimeError):
    """An expected failure while safely validating a model artifact pair."""

    def __init__(self, code: ArtifactErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code


class InferenceErrorCode(str, Enum):
    EMPTY_REQUEST = "inference_empty_request"
    INVALID_FEATURES = "inference_invalid_features"
    MODEL_LOAD_FAILED = "inference_model_load_failed"
    NON_FINITE_OUTPUT = "inference_non_finite_output"


class InferenceError(RuntimeError):
    """Stable failure from model construction, input transformation, or inference."""

    def __init__(self, code: InferenceErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code
