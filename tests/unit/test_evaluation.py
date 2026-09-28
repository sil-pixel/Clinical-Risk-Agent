import unittest

from clinical_risk_agent.evaluation import regression_metrics


class EvaluationTests(unittest.TestCase):
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
