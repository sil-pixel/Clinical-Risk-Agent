import unittest
from pathlib import Path
import tempfile

from clinical_risk_agent.evaluation import regression_metrics
from clinical_risk_agent.backend.monitoring import Monitor


class EvaluationTests(unittest.TestCase):
    """Provide evaluation tests fixtures and assertions."""
    def test_live_quality_scores_and_privacy(self):
        """Verify live quality scores and privacy."""
        with tempfile.TemporaryDirectory() as directory:
            monitor = Monitor(Path(directory))
            monitor.quality_started()
            monitor.quality_finished("scored", "GROUNDED_ANSWER", {
                "groundedness": .8, "correctness": .6, "judge_model": "fixture",
                "question": "secret", "answer": "private", "passages": ["private"],
            })
            monitor.quality_started()
            monitor.quality_finished("scored", "GENERAL_EDUCATION", {
                "correctness": 1, "groundedness": None,
            })
            monitor.quality_started()
            monitor.quality_finished("error", "CONVERSATION")
            monitor.quality_finished("skipped", "CONVERSATION")
            quality = monitor.snapshot()["live_quality"]
            self.assertEqual(quality["groundedness"], {"mean": .8, "n": 1})
            self.assertEqual(quality["correctness"], {"mean": .8, "n": 2})
            self.assertEqual(quality["errors"], 1)
            self.assertEqual(quality["skipped"], 1)
            self.assertEqual(quality["pending"], 0)
            self.assertNotIn("secret", str(quality))
            self.assertNotIn("private", str(quality))

    def test_known_regression_errors(self):
        """Verify known regression errors."""
        result = regression_metrics([1, 2, 3], [1, 2, 4])
        self.assertAlmostEqual(result["mse"], 1 / 3)
        self.assertAlmostEqual(result["rmse"], (1 / 3) ** .5)
        self.assertAlmostEqual(result["r2"], .5)
        self.assertAlmostEqual(result["spearman_rho"], 1)

    def test_ties_and_undefined_correlations(self):
        """Verify ties and undefined correlations."""
        self.assertAlmostEqual(regression_metrics([1, 1, 3], [3, 3, 1])["spearman_rho"], -1)
        result = regression_metrics([1, 1, 1], [2, 2, 2])
        self.assertIsNone(result["spearman_rho"])
        self.assertIsNone(result["r2"])

    def test_invalid_pairs_rejected(self):
        """Verify invalid pairs rejected."""
        for y, p in [([1], [2]), ([1, 2], [1]), ([1, float('nan')], [1, 2])]:
            with self.assertRaises(ValueError):
                regression_metrics(y, p)


class ClassificationMetricTests(unittest.TestCase):
    """Check routing classification metrics, including clarification handling."""

    def test_precision_recall_with_clarification(self):
        """Verify clarifying lowers recall only, and expected clarifications score as correct."""
        from clinical_risk_agent.evaluation import CLARIFY, classification_metrics

        result = classification_metrics(
            ["a", "a", "b", CLARIFY], ["a", CLARIFY, "a", CLARIFY], ["a", "b"])
        a, b = result["per_label"]["a"], result["per_label"]["b"]
        self.assertEqual((a["precision"], a["recall"]), (0.5, 0.5))
        self.assertIsNone(b["precision"])
        self.assertEqual(b["recall"], 0.0)
        self.assertEqual(result["accuracy"], 0.5)
        self.assertEqual(result["macro_precision"], 0.25)
        self.assertEqual(result["coverage"], 0.5)
        self.assertEqual(result["clarified_labeled_cases"], 1)
        self.assertEqual(result["confusion"]["b"]["a"], 1)

    def test_invalid_labels_rejected(self):
        """Verify unpaired, empty or unknown labels are rejected."""
        from clinical_risk_agent.evaluation import classification_metrics

        for expected, predicted in ([[], []], [["a"], []], [["z"], ["a"]]):
            with self.assertRaises(ValueError):
                classification_metrics(expected, predicted, ["a"])
