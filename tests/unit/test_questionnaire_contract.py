from __future__ import annotations

import sys
import json
import shutil
import subprocess
import unittest
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from clinical_risk_agent.contracts import QuestionnaireStatus  # noqa: E402
from clinical_risk_agent.inference import DCMFNetPredictor  # noqa: E402
from clinical_risk_agent.inference.questionnaire import (  # noqa: E402
    MANUAL_FEATURE_NAMES,
    assemble_model_record,
    predict_questionnaire,
    questionnaire_requirements,
    validate_questionnaire,
)


def complete_answers() -> dict[str, str]:
    return {item.question_id: item.option_ids[0] for item in questionnaire_requirements().questions}


def predictor(stem: str) -> DCMFNetPredictor:
    root = REPOSITORY_ROOT / "model_artifacts"
    return DCMFNetPredictor(root / f"{stem}.pt", root / f"{stem}.metadata.json")


class QuestionnaireContractTests(unittest.TestCase):
    def test_public_requirements_have_opaque_ids_and_exact_option_counts(self) -> None:
        requirements = questionnaire_requirements()
        self.assertEqual(len(requirements.questions), 85)
        self.assertEqual(
            [item.question_id for item in requirements.questions],
            [f"q{index:03d}" for index in range(1, 86)],
        )
        for item in requirements.questions:
            self.assertTrue(all(option.startswith("o") for option in item.option_ids))
        self.assertEqual(len(requirements.questions[0].option_ids), 6)
        self.assertEqual(len(requirements.questions[70].option_ids), 6)
        self.assertEqual(len(requirements.questions[84].option_ids), 2)

    def test_backend_option_contract_matches_rendered_frontend(self) -> None:
        if shutil.which("node") is None:
            self.skipTest("Node.js is unavailable")
        script = (
            "import { allQuestions, getOptionsForQuestion } from './src/questionnaireData.js';"
            "console.log(JSON.stringify(allQuestions.map(q => "
            "[q.id, getOptionsForQuestion(q).map(o => o.id)])))"
        )
        completed = subprocess.run(
            ["node", "--input-type=module", "-e", script],
            cwd=REPOSITORY_ROOT / "frontend",
            check=True,
            capture_output=True,
            text=True,
        )
        frontend_contract = dict(json.loads(completed.stdout))
        backend_contract = {
            item.question_id: list(item.option_ids)
            for item in questionnaire_requirements().questions
        }
        self.assertEqual(frontend_contract, backend_contract)

    def test_validation_rejects_missing_unknown_and_unscored_answers(self) -> None:
        answers = complete_answers()
        self.assertTrue(validate_questionnaire(answers).authorizes_inference)
        answers.pop("q001")
        self.assertEqual(validate_questionnaire(answers).status, QuestionnaireStatus.INCOMPLETE)
        answers["q001"] = "memory_unknown"
        self.assertEqual(validate_questionnaire(answers).invalid_question_ids, ("q001",))
        answers["q001"] = "o07"
        self.assertEqual(validate_questionnaire(answers).status, QuestionnaireStatus.INVALID)
        answers["q001"] = "o01"
        answers["q999"] = "o01"
        self.assertEqual(validate_questionnaire(answers).unknown_question_ids, ("q999",))
        with self.assertRaises(ValueError):
            validate_questionnaire(answers, version="wrong")

    def test_mapping_covers_both_artifacts_and_uses_target_specific_hidden_medians(self) -> None:
        answers = complete_answers()
        for stem in ("dcmfnet_pos", "dcmfnet_neg"):
            with self.subTest(stem=stem):
                model = predictor(stem)
                record = assemble_model_record(answers, model)
                self.assertEqual(tuple(record), model.schema.flat_feature_names)
                self.assertEqual(len(record), 105)
                self.assertEqual(len(MANUAL_FEATURE_NAMES), 85)
                self.assertEqual(record["SUD15_Cigarettes15"], 0.0)
                self.assertEqual(record["ACE15_other_bullying15"], 1.0)
                self.assertEqual(record["ACE18_other_abuse18"], 0.0)
                self.assertEqual(record["SES_education_father"], 1.0)
                self.assertEqual(record["SES_birth_country_father"], 0.0)
                self.assertEqual(record["SEX"], 1.0)
                median_by_name = {
                    name: median
                    for names, medians in zip(
                        model.schema.feature_names, model.schema.medians, strict=True
                    )
                    for name, median in zip(names, medians, strict=True)
                }
                for name in set(record) - set(MANUAL_FEATURE_NAMES):
                    self.assertEqual(record[name], median_by_name[name])
                model.predict([record])

    def test_option_codes_and_public_order_are_explicit(self) -> None:
        model = predictor("dcmfnet_pos")
        answers = complete_answers()
        answers.update({
            "q003": "o04", "q015": "o04", "q030": "o03",
            "q066": "o05", "q071": "o06", "q073": "o02",
            "q074": "o01", "q076": "o02", "q077": "o08",
            "q079": "o05", "q081": "o05", "q082": "o01",
            "q084": "o02", "q085": "o02",
        })
        record = assemble_model_record(answers, model)
        expected = {
            "SUD15_Alcohol15": 3, "SCZ15_Extreme_excitement15": 3,
            "ADHD9_var_1": 2, "ACE15_other_bullying15": 5,
            "ACE15_bullying_by_num15": 6, "ACE18_other_abuse18": 1,
            "ACE18_hate_crime18": 0, "ACE18_witness_crime18": 1,
            "SUD18_cigarettes18": 7, "SUD18_alcohol_often18": 4,
            "SES_education_father": 5, "SES_birth_country_father": 0,
            "SES_birth_country_mother": 1, "SEX": 2,
        }
        for feature, value in expected.items():
            self.assertEqual(record[feature], value)
        with self.assertRaises(ValueError):
            assemble_model_record({"q001": "o01"}, model)

    def test_complete_assessment_returns_separate_unchanged_target_outputs(self) -> None:
        positive = predictor("dcmfnet_pos")
        negative = predictor("dcmfnet_neg")
        answers = complete_answers()
        result = predict_questionnaire(answers, positive, negative)
        self.assertEqual(result.questionnaire_version, questionnaire_requirements().version)
        self.assertEqual(result.generic_profile_version, "generic_genetic_profile_v1")
        self.assertEqual(
            result.positive,
            positive.predict([assemble_model_record(answers, positive)]),
        )
        self.assertEqual(
            result.negative,
            negative.predict([assemble_model_record(answers, negative)]),
        )
        with self.assertRaises(ValueError):
            predict_questionnaire({"q001": "o01"}, positive, negative)
        with self.assertRaises(ValueError):
            predict_questionnaire(answers, negative, positive)


if __name__ == "__main__":
    unittest.main()
