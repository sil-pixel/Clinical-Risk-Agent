"""The exploratory gate must count lost direct evidence and false evidence separately."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPTS_ROOT = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from rag_relevance_gate_calibration import _gate_rows, _path_summary  # noqa: E402


class GateSweepTests(unittest.TestCase):
    def test_fallback_summary_counts_direct_and_unsupported_separately(self) -> None:
        rows = [
            {"answerable": True, "direct_pmids": ["1"],
             "outage_top_5_pmids": ["1", "2"], "outage_retrieval_mode": "keyword_fallback",
             "outage_status": "sufficient_evidence"},
            {"answerable": False, "direct_pmids": [],
             "outage_top_5_pmids": ["2"], "outage_retrieval_mode": "keyword_fallback",
             "outage_status": "sufficient_evidence"},
        ]
        result = _path_summary(rows, "outage")
        self.assertEqual(result["direct_source_found_at_5"], 1)
        self.assertEqual(result["no_direct_evidence_returned_sources"], 1)
        self.assertEqual(result["keyword_fallback_cases"], 2)

    def test_cutoff_tradeoff(self) -> None:
        rows = [
            {"answerable": True, "direct_pmids": ["1"],
             "diagnostic_top_5": [{"pmid": "1", "dense_cosine": 0.60}]},
            {"answerable": False, "direct_pmids": [],
             "diagnostic_top_5": [{"pmid": "2", "dense_cosine": 0.65}]},
        ]
        low = _gate_rows(rows, 0.59)
        self.assertEqual(low["direct_source_recall_at_5_answerable"], 1.0)
        self.assertEqual(low["no_direct_evidence_abstention_rate"], 0.0)
        high = _gate_rows(rows, 0.65)
        self.assertEqual(high["direct_source_recall_at_5_answerable"], 0.0)
        self.assertEqual(high["no_direct_evidence_abstention_rate"], 1.0)

    def test_missing_dense_score_is_not_accepted(self) -> None:
        rows = [
            {"answerable": True, "direct_pmids": ["1"],
             "diagnostic_top_5": [{"pmid": "1", "dense_cosine": None}]},
            {"answerable": False, "direct_pmids": [], "diagnostic_top_5": []},
        ]
        result = _gate_rows(rows, 0.0)
        self.assertEqual(result["answerable_acceptance_rate"], 0.0)
        self.assertEqual(result["no_direct_evidence_abstention_rate"], 1.0)


if __name__ == "__main__":
    unittest.main()
