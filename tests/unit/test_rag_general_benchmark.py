"""Metric checks for the frozen general-association retrieval comparison."""

from __future__ import annotations

import math
import json
import tempfile
import sys
import unittest
from pathlib import Path

SCRIPTS_ROOT = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from rag_general_benchmark import _answerable, _relevance_first, _scores, _validate, _sha256  # noqa: E402


class SourceMetricTests(unittest.TestCase):
    def test_locked_context_only_case_and_tamper_detection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.json"
            source.write_text("{}")
            corpus = {"source_manifest": str(source), "source_pmids": ["10"]}
            corpus_path = root / "corpus.json"
            corpus_path.write_text(json.dumps(corpus))
            gold = {"status": "pre_run_locked_provisional_ai_reviewed_research_only",
                    "corpus_manifest_sha256": _sha256(corpus_path),
                    "source_manifest_sha256": _sha256(source),
                    "predeclared_run": {"k": 5, "ranking": "relevance_first"},
                    "cases": [{"id": "negative", "grades": {"10": 1}, "reference_answer": None}]}
            path = root / "gold.json"
            path.write_text(json.dumps(gold))
            path.with_suffix(".lock.json").write_text(json.dumps({"gold_sha256": _sha256(path)}))
            _validate(gold, corpus, path, corpus_path)
            path.write_text(path.read_text() + "\n")
            with self.assertRaisesRegex(ValueError, "changed after lock"):
                _validate(gold, corpus, path, corpus_path)

    def test_context_only_is_not_answerable(self):
        self.assertFalse(_answerable({"grades": {"10": 1}}))
        self.assertTrue(_answerable({"grades": {"10": 2}}))

    def test_ranking_preserves_legacy_and_honors_new_lock(self):
        self.assertFalse(_relevance_first({"predeclared_run": {}}))
        self.assertTrue(_relevance_first({"predeclared_run": {"ranking": "relevance_first"}}))
        with self.assertRaises(ValueError):
            _relevance_first({"predeclared_run": {"ranking": "unknown"}})

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
