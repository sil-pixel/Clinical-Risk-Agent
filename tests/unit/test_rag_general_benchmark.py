"""Metric checks for the frozen general-association retrieval comparison."""

from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

SCRIPTS_ROOT = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from rag_general_benchmark import _scores  # noqa: E402


class SourceMetricTests(unittest.TestCase):
    def test_direct_source_at_first_rank(self) -> None:
        values = _scores(["pmid:10", "pmid:20", "pmid:30"], {"10": 2, "20": 1}, 5)
        self.assertEqual(values["precision_at_5"], 0.2)
        self.assertEqual(values["recall_at_5"], 1.0)
        self.assertEqual(values["mrr_at_5"], 1.0)
        self.assertEqual(values["ndcg_at_5"], 1.0)

    def test_context_is_graded_but_not_direct_hit(self) -> None:
        values = _scores(["pmid:20", "pmid:30", "pmid:10"], {"10": 2, "20": 1}, 5)
        self.assertEqual(values["precision_at_5"], 0.2)
        self.assertEqual(values["recall_at_5"], 1.0)
        self.assertAlmostEqual(values["mrr_at_5"], 1 / 3)
        self.assertTrue(0 < values["ndcg_at_5"] < 1)

    def test_missing_direct_source(self) -> None:
        values = _scores(["pmid:20"], {"10": 2, "20": 1}, 5)
        self.assertEqual(values["precision_at_5"], 0.0)
        self.assertEqual(values["recall_at_5"], 0.0)
        self.assertEqual(values["mrr_at_5"], 0.0)
        self.assertTrue(math.isfinite(values["ndcg_at_5"]))


if __name__ == "__main__":
    unittest.main()
