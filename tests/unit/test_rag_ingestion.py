"""Manifest checks keep unreviewed papers out of benchmark collections."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parents[2] / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from clinical_risk_agent.rag.ingestion import load_approved_sources  # noqa: E402
from clinical_risk_agent.rag.ingestion import fetch_approved_pubmed_sources  # noqa: E402
from clinical_risk_agent.rag.pubmed import PubMedClient  # noqa: E402


class IngestionManifestTests(unittest.TestCase):
    def test_reviewed_source_required(self) -> None:
        record = {
            "pmid": "12345", "topic": "depression",
            "study_design": "observational_study", "reviewer": "reviewer-1",
            "reviewed_on": "2026-09-20",
            "appraisal": {"passed": True, "score": 0.8, "rubric_version": "rubric-v1"},
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sources.json"
            path.write_text(json.dumps({"schema_version": 1, "sources": [record]}))
            approved = load_approved_sources(path, today=date(2026, 9, 24))
            self.assertEqual(approved[0].pmid, "12345")
            record["appraisal"]["passed"] = False
            path.write_text(json.dumps({"schema_version": 1, "sources": [record]}))
            with self.assertRaisesRegex(ValueError, "must pass"):
                load_approved_sources(path, today=date(2026, 9, 24))

    def test_pubmed_design_conflict_requires_documented_override(self) -> None:
        record = {
            "pmid": "12345", "topic": "schizophrenia",
            "study_design": "observational_study", "reviewer": "reviewer-1",
            "reviewed_on": "2026-09-20",
            "appraisal": {"passed": True, "score": 0.8, "rubric_version": "rubric-v1"},
        }
        xml = b"""<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>12345</PMID>
        <Article><Journal><JournalIssue><PubDate><Year>2024</Year></PubDate>
        </JournalIssue><Title>Fixture</Title></Journal><ArticleTitle>Fixture title</ArticleTitle>
        <Abstract><AbstractText>Fixture abstract.</AbstractText></Abstract>
        <PublicationTypeList><PublicationType>Meta-Analysis</PublicationType>
        </PublicationTypeList></Article></MedlineCitation></PubmedArticle></PubmedArticleSet>"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sources.json"
            path.write_text(json.dumps({"schema_version": 1, "sources": [record]}))
            approved = load_approved_sources(path, today=date(2026, 9, 24))
            with self.assertRaisesRegex(ValueError, "conflicts"):
                fetch_approved_pubmed_sources(
                    approved, today=date(2026, 9, 24), client=PubMedClient(fetch=lambda _: xml)
                )
            record["design_override_reason"] = "Primary nested case-control analysis"
            path.write_text(json.dumps({"schema_version": 1, "sources": [record]}))
            approved = load_approved_sources(path, today=date(2026, 9, 24))
            source = fetch_approved_pubmed_sources(
                approved, today=date(2026, 9, 24), client=PubMedClient(fetch=lambda _: xml)
            )[0]
            self.assertEqual(source.study_design, "observational_study")


if __name__ == "__main__":
    unittest.main()
