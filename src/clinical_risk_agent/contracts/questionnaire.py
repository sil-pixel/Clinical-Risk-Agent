"""Versioned, opaque questionnaire contracts for prototype assessment input."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .model_inference import InferenceResult


QUESTIONNAIRE_VERSION = "prototype_questionnaire_v2"
GENERIC_PROFILE_VERSION = "generic_genetic_profile_v1"


class QuestionnaireStatus(str, Enum):
    """Enumerate questionnaire validation and inference eligibility outcomes."""
    COMPLETE = "complete"
    INCOMPLETE = "incomplete"
    INVALID = "invalid"


@dataclass(frozen=True, slots=True)
class QuestionnaireRequirement:
    """Describe one public questionnaire question and its allowed options."""
    question_id: str
    option_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class QuestionnaireRequirements:
    """Describe the versioned public questionnaire contract."""
    version: str
    questions: tuple[QuestionnaireRequirement, ...]


@dataclass(frozen=True, slots=True)
class QuestionnaireValidationResult:
    """Report completeness, invalid answers and feature-mapping readiness."""
    version: str
    status: QuestionnaireStatus
    missing_question_ids: tuple[str, ...]
    invalid_question_ids: tuple[str, ...]
    unknown_question_ids: tuple[str, ...]

    @property
    def authorizes_inference(self) -> bool:
        """Report whether questionnaire validation permits model inference."""
        return self.status is QuestionnaireStatus.COMPLETE


@dataclass(frozen=True, slots=True)
class QuestionnaireAssessmentResult:
    """Bundle separate positive and negative research-model predictions."""
    questionnaire_version: str
    generic_profile_version: str
    positive: InferenceResult
    negative: InferenceResult
