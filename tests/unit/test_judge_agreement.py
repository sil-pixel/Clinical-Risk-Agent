"""Test ordinal agreement and prevent predicted human labels entering calibration."""

import json
from pathlib import Path
import unittest

from clinical_risk_agent.ai.judge_agreement import agreement_report, cohen_kappa


class JudgeAgreementTests(unittest.TestCase):
    """Check kappa edge cases and the frozen response packet's review boundaries."""

    def test_known_kappa_and_ordinal_weights(self):
        """Verify a hand-computed confusion matrix with one adjacent disagreement."""
        a = ["bad", "acceptable", "good"]
        b = ["bad", "good", "good"]
        self.assertAlmostEqual(cohen_kappa(a, b)["kappa"], .5)
        self.assertAlmostEqual(cohen_kappa(a, b, weights="linear")["kappa"], 2 / 3)
        self.assertAlmostEqual(cohen_kappa(a, b, weights="quadratic")["kappa"], .8)

    def test_empty_degenerate_and_invalid_pairs(self):
        """Return undefined scores for no variation and reject malformed input."""
        self.assertIsNone(cohen_kappa([], [])["kappa"])
        self.assertIsNone(cohen_kappa(["good"], ["good"])["kappa"])
        for a, b in [(["bad"], []), (["guess"], ["good"])]:
            with self.assertRaises(ValueError):
                cohen_kappa(a, b)

    def test_unconfirmed_and_predicted_labels_are_excluded(self):
        """Require explicit human review and actual model labels for judge agreement."""
        case = {"split": "holdout", "human_annotation": "good", "human_reviewed": False,
                "predicted_human_annotation": "good", "assistant_annotation": "good",
                "judge_annotation": "good"}
        result = agreement_report([case])["splits"]["holdout"]
        self.assertEqual(result["reviewed"], 0)
        case.update(human_reviewed=True, judge_annotation=None)
        result = agreement_report([case])["splits"]["holdout"]
        self.assertEqual(result["comparisons"]["judge_annotation"]["unweighted"]["n"], 0)
        self.assertEqual(result["comparisons"]["assistant_annotation"]["unweighted"]["n"], 1)

    def test_frozen_packet_size_and_grouped_splits(self):
        """Verify all hundred fixtures remain unreviewed and query groups never leak."""
        root = Path(__file__).resolve().parents[2]
        packet = json.loads((root / "agent_docs/LLM_JUDGE_REVIEW_100.json").read_text())
        cases = packet["cases"]
        self.assertEqual(len(cases), 100)
        self.assertEqual(len({c["id"] for c in cases}), 100)
        for case in cases:
            self.assertIsNone(case["human_annotation"])
            self.assertFalse(case["human_reviewed"])
        for query in {c["query_id"] for c in cases}:
            self.assertEqual(len({c["split"] for c in cases if c["query_id"] == query}), 1)
        self.assertEqual([sum(c["split"] == s for c in cases)
                          for s in ("calibration", "validation", "holdout")], [50, 25, 25])
