"""Public-record ingestion tests use synthetic XML, never patient data."""

from __future__ import annotations

import sys
import unittest
from dataclasses import replace
from datetime import date
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parents[2] / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from clinical_risk_agent.rag.corpus import source_rejection_reasons  # noqa: E402
from clinical_risk_agent.rag.pubmed import (  # noqa: E402
    PubMedClient,
    QualityAppraisal,
    parse_pubmed_xml,
    refresh_retraction_status,
)

TODAY = date(2026, 9, 24)
XML = b"""<PubmedArticleSet><PubmedArticle><MedlineCitation>
<PMID>12345</PMID><Article><Journal><JournalIssue><PubDate><Year>2025</Year>
<Month>09</Month><Day>01</Day></PubDate></JournalIssue><Title>Fixture Journal</Title></Journal>
<ArticleTitle>Fixture systematic review</ArticleTitle><Abstract>
<AbstractText Label="RESULTS">Bullying evidence in a synthetic fixture.</AbstractText></Abstract>
<AuthorList><Author><ForeName>Fixture</ForeName><LastName>Author</LastName></Author></AuthorList>
<PublicationTypeList><PublicationType>Systematic Review</PublicationType></PublicationTypeList>
</Article></MedlineCitation><PubmedData><ArticleIdList><ArticleId IdType="doi">
10.5555/fixture.12345</ArticleId></ArticleIdList></PubmedData></PubmedArticle></PubmedArticleSet>"""


class PubMedTests(unittest.TestCase):
    def test_appraisal_is_mandatory_and_metadata_is_preserved(self) -> None:
        missing = parse_pubmed_xml(XML, checked_on=TODAY, appraisals={})[0]
        self.assertIn("quality_appraisal_missing_or_failed",
                      source_rejection_reasons(missing, today=TODAY))
        appraisals = {"12345": QualityAppraisal(True, 0.85, "rubric-v1")}
        source = parse_pubmed_xml(XML, checked_on=TODAY, appraisals=appraisals)[0]
        self.assertEqual(source.source_id, "pmid:12345")
        self.assertEqual(source.study_design, "systematic_review")
        self.assertEqual(source.authors, ("Fixture Author",))
        self.assertEqual(source_rejection_reasons(source, today=TODAY), ())

    def test_bounded_fetch_rejects_missing_records(self) -> None:
        client = PubMedClient(fetch=lambda url: XML)
        with self.assertRaisesRegex(ValueError, "did not match"):
            client.fetch_pmids(("12345", "54321"), checked_on=TODAY, appraisals={})
        with self.assertRaisesRegex(ValueError, "numeric PMIDs"):
            client.fetch_pmids(("patient name",), checked_on=TODAY, appraisals={})

    def test_retraction_refresh_fails_closed_on_missing_or_changed_identity(self) -> None:
        source = parse_pubmed_xml(XML, checked_on=TODAY, appraisals={})[0]
        self.assertEqual(refresh_retraction_status((source,), ())[0].retraction_state,
                         "unverified")
        altered = replace(source, doi="10.5555/different")
        self.assertEqual(refresh_retraction_status((source,), (altered,))[0].retraction_state,
                         "unverified")
        retracted = replace(source, retraction_state="retracted")
        self.assertEqual(refresh_retraction_status((source,), (retracted,))[0].retraction_state,
                         "retracted")


if __name__ == "__main__":
    unittest.main()
