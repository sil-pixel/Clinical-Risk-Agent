"""Private questionnaire validation and target-specific model input assembly.

The current public option order is the prototype's accepted code mapping. This is
an implementation decision, not evidence of source-instrument equivalence.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from math import isfinite

from clinical_risk_agent.contracts import (
    GENERIC_PROFILE_VERSION,
    QUESTIONNAIRE_VERSION,
    ModelTarget,
    QuestionnaireAssessmentResult,
    QuestionnaireRequirement,
    QuestionnaireRequirements,
    QuestionnaireStatus,
    QuestionnaireValidationResult,
)

from .runtime import DCMFNetPredictor


def _numbered(group: str, count: int) -> tuple[str, ...]:
    return tuple(f"{group}_var_{index}" for index in range(1, count + 1))


# Public IDs are intentionally unrelated to feature names. The age-18 experience
# section renders q074-q076 before q073; IDs still map to artifact column order.
MANUAL_FEATURE_NAMES = (
    "SUD15_Cigarettes15", "SUD15_Snuff15", "SUD15_Alcohol15",
    "SUD15_Cannabis15", "SUD15_OtherDrugs15", "SUD15_Painkillers_opioids15",
    "SCZ15_PROD_seen_hallucinations9", "SCZ15_Spied15",
    "SCZ15_Others_Read_thoughts15", "SCZ15_Special_messages15",
    "SCZ15_Special_powers15", "SCZ15_Under_control_special_power15",
    "SCZ15_Read_others_minds15", "SCZ15_Seen_hallucinations15",
    "SCZ15_Extreme_excitement15", "SCZ15_Irritable15",
    "SCZ15_Unrealistic_abilities15", "SCZ15_Not_tired15",
    "SCZ15_Too_much_energy15", "SCZ15_Racing_thoughts15",
    "SCZ15_Talking_fast15", "SCZ15_Sexual_inappropriate15",
    "SCZ15_Rage_attacks15", "SCZ15_Hear_voices15", "SCZ15_headaches15",
    "SCZ15_worry15", "SCZ15_unhappy15", "SCZ15_lose_confidence15",
    "SCZ15_easily_scared15",
    *_numbered("ADHD9", 19),
    *_numbered("ASD9", 17),
    "ACE15_other_bullying15", "ACE15_bullied_often15",
    "ACE15_tease_bullying15", "ACE15_emotional_bullying15",
    "ACE15_rumours_bullying15", "ACE15_bullying_by_num15",
    "ACE15_bullying_time15",
    "ACE18_other_abuse18", "ACE18_hate_crime18",
    "ACE18_emotional_abuse18", "ACE18_witness_crime18",
    "SUD18_cigarettes18", "SUD18_snuff18", "SUD18_alcohol_often18",
    "SUD18_drugs_often18", "SES_education_father",
    "SES_birth_country_father", "SES_education_mother",
    "SES_birth_country_mother", "SEX",
)

# Counts and code starts follow the displayed option sets in questionnaireData.js.
# Each tuple is (first public question, last public question, option count, first code).
OPTION_GROUPS = (
    (1, 2, 6, 0), (3, 6, 4, 0), (7, 14, 3, 0),
    (15, 24, 4, 0), (25, 29, 3, 0), (30, 65, 3, 0),
    (66, 70, 5, 1), (71, 72, 6, 1), (73, 76, 2, 0),
    (77, 78, 8, 0), (79, 80, 5, 0), (81, 81, 5, 1),
    (82, 82, 2, 0), (83, 83, 5, 1), (84, 84, 2, 0),
    (85, 85, 2, 1),
)


@dataclass(frozen=True, slots=True)
class _PrivateQuestion:
    feature_name: str
    codes: tuple[int, ...]


def _question_id(index: int) -> str:
    return f"q{index:03d}"


def _make_mapping() -> dict[str, _PrivateQuestion]:
    by_index: dict[int, tuple[int, ...]] = {}
    for first, last, count, start in OPTION_GROUPS:
        for index in range(first, last + 1):
            if index in by_index:
                raise RuntimeError("Questionnaire option groups overlap")
            by_index[index] = tuple(range(start, start + count))
    if set(by_index) != set(range(1, 86)) or len(MANUAL_FEATURE_NAMES) != 85:
        raise RuntimeError("Questionnaire mapping must cover exactly 85 questions")
    if len(set(MANUAL_FEATURE_NAMES)) != 85:
        raise RuntimeError("Questionnaire feature names must be unique")
    return {
        _question_id(index): _PrivateQuestion(MANUAL_FEATURE_NAMES[index - 1], by_index[index])
        for index in range(1, 86)
    }


_PRIVATE_MAPPING = _make_mapping()


def questionnaire_requirements() -> QuestionnaireRequirements:
    return QuestionnaireRequirements(
        version=QUESTIONNAIRE_VERSION,
        questions=tuple(
            QuestionnaireRequirement(
                question_id=question_id,
                option_ids=tuple(f"o{index:02d}" for index in range(1, len(item.codes) + 1)),
            )
            for question_id, item in _PRIVATE_MAPPING.items()
        ),
    )


def validate_questionnaire(
    answers: Mapping[str, str], *, version: str = QUESTIONNAIRE_VERSION
) -> QuestionnaireValidationResult:
    if version != QUESTIONNAIRE_VERSION:
        raise ValueError("Unsupported questionnaire version")
    if not isinstance(answers, Mapping):
        raise TypeError("Questionnaire answers must be a mapping")
    if any(not isinstance(question_id, str) for question_id in answers):
        raise TypeError("Questionnaire question IDs must be strings")
    missing = tuple(question_id for question_id in _PRIVATE_MAPPING if question_id not in answers)
    unknown = tuple(sorted(set(answers) - set(_PRIVATE_MAPPING)))
    invalid = tuple(
        question_id
        for question_id, item in _PRIVATE_MAPPING.items()
        if question_id in answers
        and (
            not isinstance((option_id := answers[question_id]), str)
            or option_id == "memory_unknown"
            or option_id not in tuple(
                f"o{index:02d}"
                for index in range(1, len(item.codes) + 1)
            )
        )
    )
    status = (
        QuestionnaireStatus.INVALID if invalid or unknown else
        QuestionnaireStatus.INCOMPLETE if missing else
        QuestionnaireStatus.COMPLETE
    )
    return QuestionnaireValidationResult(version, status, missing, invalid, unknown)


def assemble_model_record(
    answers: Mapping[str, str], predictor: DCMFNetPredictor,
    *, version: str = QUESTIONNAIRE_VERSION,
) -> dict[str, float]:
    """Return exactly 105 values, using this artifact's medians for hidden fields."""
    result = validate_questionnaire(answers, version=version)
    if not result.authorizes_inference:
        raise ValueError("Questionnaire is incomplete or invalid")
    schema = predictor.schema
    all_names = schema.flat_feature_names
    manual_names = set(MANUAL_FEATURE_NAMES)
    hidden_names = {
        name for group, names in zip(schema.modality_names, schema.feature_names, strict=True)
        if group in {"PRS", "batch_.*_x_PC"} for name in names
    }
    if (
        len(all_names) != 105 or len(hidden_names) != 20
        or set(all_names) != manual_names | hidden_names
        or manual_names & hidden_names
    ):
        raise ValueError("Artifact schema does not match the questionnaire contract")
    median_by_name = {
        name: median
        for names, medians in zip(schema.feature_names, schema.medians, strict=True)
        for name, median in zip(names, medians, strict=True)
    }
    record = {name: float(median_by_name[name]) for name in hidden_names}
    for question_id, item in _PRIVATE_MAPPING.items():
        option_index = int(answers[question_id][1:]) - 1
        record[item.feature_name] = float(item.codes[option_index])
    return {name: record[name] for name in all_names}


def predict_questionnaire(
    answers: Mapping[str, str],
    positive_predictor: DCMFNetPredictor,
    negative_predictor: DCMFNetPredictor,
    *,
    version: str = QUESTIONNAIRE_VERSION,
) -> QuestionnaireAssessmentResult:
    """Invoke both pinned targets only for a complete structured questionnaire."""
    if (
        positive_predictor.target is not ModelTarget.POSITIVE_SYMPTOM_SEVERITY
        or negative_predictor.target is not ModelTarget.NEGATIVE_SYMPTOM_SEVERITY
    ):
        raise ValueError("Assessment predictor targets are incompatible")
    positive_record = assemble_model_record(answers, positive_predictor, version=version)
    negative_record = assemble_model_record(answers, negative_predictor, version=version)
    positive = positive_predictor.predict([positive_record])
    negative = negative_predictor.predict([negative_record])
    for result in (positive, negative):
        if len(result.predictions) != 1:
            raise ValueError("Assessment must return exactly one prediction per target")
        value = result.predictions[0].normalized_symptom_severity
        if not isfinite(value) or not 0.0 <= value <= 1.0:
            raise ValueError("Assessment produced an invalid probability")
    return QuestionnaireAssessmentResult(
        questionnaire_version=version,
        generic_profile_version=GENERIC_PROFILE_VERSION,
        positive=positive,
        negative=negative,
    )


__all__ = [
    "GENERIC_PROFILE_VERSION", "MANUAL_FEATURE_NAMES", "assemble_model_record",
    "predict_questionnaire", "questionnaire_requirements", "validate_questionnaire",
]
