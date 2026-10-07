import json
from pathlib import Path
import tempfile
import unittest

from clinical_risk_agent.backend.monitoring import DRIFT_REFERENCE_PATH, Monitor
from clinical_risk_agent.drift import categorical_drift, count_codes, drift_report
from clinical_risk_agent.inference import questionnaire_feature_codes, questionnaire_requirements
from clinical_risk_agent.ood import build_ood_reference, score_submission


class DriftMetricTests(unittest.TestCase):
    """Check categorical drift metrics, suppression and aggregate-only monitoring."""

    def test_identical_and_disjoint_distributions(self):
        """Verify identical distributions score zero and disjoint ones score maximal JS."""
        same = categorical_drift({"0": 5, "1": 5}, {"0": 50, "1": 50})
        self.assertAlmostEqual(same["js_distance"], 0)
        self.assertAlmostEqual(same["psi"], 0)
        disjoint = categorical_drift({"0": 10}, {"1": 10})
        self.assertAlmostEqual(disjoint["js_distance"], 1)
        self.assertGreater(disjoint["psi"], 0.25)

    def test_count_codes_excludes_missing_and_normalizes_negative_zero(self):
        """Verify blank and NaN values count as missing and -0.0 maps to code 0."""
        counts, missing = count_codes(
            [{"a": "-0.0"}, {"a": ""}, {"a": float("nan")}, {"a": "2.0"}], ["a"])
        self.assertEqual(counts, {"a": {"0": 1, "2": 1}})
        self.assertEqual(missing, {"a": 2})
        with self.assertRaises(ValueError):
            count_codes([{"a": "0.5"}], ["a"])

    def test_report_suppressed_below_minimum_sample(self):
        """Verify per-feature drift is withheld until enough submissions exist."""
        report = drift_report({"a": {"0": 10}}, {"a": {"1": 5}}, 5)
        self.assertEqual(report, {"status": "insufficient_data", "n": 5, "min_n": 30})

    def test_dataset_drift_share(self):
        """Verify dataset drift requires the configured share of drifted features."""
        reference = {"a": {"0": 50, "1": 50}, "b": {"0": 50, "1": 50}}
        report = drift_report(reference, {"a": {"0": 30}, "b": {"0": 15, "1": 15}}, 30)
        self.assertEqual(report["drifted_features"], 1)
        self.assertEqual(report["status"], "drift")
        self.assertEqual(report["features"][0]["feature"], "a")
        report = drift_report(reference, {"a": {"0": 30}, "b": {"0": 15, "1": 15}}, 30,
                              dataset_share=0.75)
        self.assertEqual(report["status"], "stable")

    def test_questionnaire_feature_codes(self):
        """Verify complete answers map to 85 feature codes and incomplete ones are rejected."""
        answers = {item.question_id: "o01" for item in questionnaire_requirements().questions}
        codes = questionnaire_feature_codes(answers)
        self.assertEqual(len(codes), 85)
        self.assertNotIn("PRS_all", codes)
        self.assertEqual(codes["ACE15_bullied_often15"], 1)
        with self.assertRaises(ValueError):
            questionnaire_feature_codes({"q001": "o01"})

    def test_monitor_exposes_only_scores(self):
        """Verify live drift uses aggregates and never exposes raw per-category counts."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(Monitor(root).input_drift(), {"status": "no_reference", "n": 0})
            path = root / DRIFT_REFERENCE_PATH
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({"dataset": "fixture.csv", "n": 100,
                                        "counts": {"SEX": {"1": 50, "2": 50}}}))
            monitor = Monitor(root)
            for _ in range(29):
                monitor.record_inputs({"SEX": 2})
            self.assertEqual(monitor.snapshot()["input_drift"]["status"], "insufficient_data")
            monitor.record_inputs({"SEX": 2})
            drift = monitor.snapshot()["input_drift"]
            self.assertEqual(drift["status"], "drift")
            self.assertEqual(drift["features"][0]["feature"], "SEX")
            self.assertNotIn("counts", drift)
            self.assertEqual(drift["reference"]["dataset"], "fixture.csv")


class OODTests(unittest.TestCase):
    """Check OOD reference fitting, per-submission scoring and live rate reporting."""

    def reference(self):
        """Build a two-feature OOD reference where both features are usually equal."""
        rows = [{"a": "0", "b": "0"}] * 60 + [{"a": "1", "b": "1"}] * 38 + [
            {"a": "1", "b": "0"}, {"a": "", "b": "1"}]
        counts, _ = count_codes(rows, ["a", "b"])
        return build_ood_reference(rows, ["a", "b"], counts)

    def test_common_codes_pass_and_unseen_codes_flag(self):
        """Verify typical answers stay in distribution and unseen codes are flagged."""
        reference = self.reference()
        typical = score_submission({"a": 0, "b": 0}, reference)
        self.assertFalse(typical["surprise_ood"] or typical["mahalanobis_ood"])
        unseen = score_submission({"a": 4, "b": 4}, reference)
        self.assertTrue(unseen["surprise_ood"])
        self.assertTrue(unseen["mahalanobis_ood"])

    def test_mahalanobis_flags_unusual_combinations(self):
        """Verify a rare combination of common codes raises the correlation-aware distance."""
        reference = self.reference()
        common = score_submission({"a": 1, "b": 1}, reference)["mahalanobis"]
        rare = score_submission({"a": 0, "b": 1}, reference)["mahalanobis"]
        self.assertGreater(rare, common)

    def test_monitor_reports_rates_only_after_minimum_sample(self):
        """Verify the live OOD rate is suppressed below the minimum and keeps no scores."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(Monitor(root).input_ood(), {"status": "no_reference", "n": 0})
            path = root / DRIFT_REFERENCE_PATH
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({"counts": {"a": {"0": 60, "1": 39},
                                                   "b": {"0": 61, "1": 39}},
                                        "ood": self.reference()}))
            monitor = Monitor(root)
            for _ in range(27):
                monitor.record_inputs({"a": 0, "b": 0})
            for _ in range(2):
                monitor.record_inputs({"a": 4, "b": 4})
            self.assertEqual(monitor.input_ood()["status"], "insufficient_data")
            monitor.record_inputs({"a": 4, "b": 4})
            ood = monitor.snapshot()["input_ood"]
            self.assertEqual(ood["status"], "scored")
            self.assertAlmostEqual(ood["either_rate"], 0.1)
            self.assertAlmostEqual(ood["expected_rate"], 0.01)
            self.assertNotIn("surprise", ood)
