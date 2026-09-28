import unittest
from pathlib import Path
import tempfile

from clinical_risk_agent.evaluation import regression_metrics
from clinical_risk_agent.backend.monitoring import Monitor


class EvaluationTests(unittest.TestCase):
    def test_live_quality_scores_and_privacy(self):
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
        result = regression_metrics([1, 2, 3], [1, 2, 4])
        self.assertAlmostEqual(result["mse"], 1 / 3)
        self.assertAlmostEqual(result["rmse"], (1 / 3) ** .5)
        self.assertAlmostEqual(result["r2"], .5)
        self.assertAlmostEqual(result["spearman_rho"], 1)

    def test_ties_and_undefined_correlations(self):
        self.assertAlmostEqual(regression_metrics([1, 1, 3], [3, 3, 1])["spearman_rho"], -1)
        result = regression_metrics([1, 1, 1], [2, 2, 2])
        self.assertIsNone(result["spearman_rho"])
        self.assertIsNone(result["r2"])

    def test_invalid_pairs_rejected(self):
        for y, p in [([1], [2]), ([1, 2], [1]), ([1, float('nan')], [1, 2])]:
            with self.assertRaises(ValueError):
                regression_metrics(y, p)
