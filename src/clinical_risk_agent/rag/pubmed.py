"""PubMed XML discovery for public scientific records; no runtime user payloads."""

from __future__ import annotations

import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date

from .corpus import ScientificSource


@dataclass(frozen=True, slots=True)
class QualityAppraisal:
    passed: bool
    score: float
    rubric_version: str


def _text(element: ET.Element | None) -> str:
    return " ".join("".join(element.itertext()).split()) if element is not None else ""


def _publication_date(article: ET.Element) -> date | None:
    paths = (
        "./MedlineCitation/Article/ArticleDate",
        "./MedlineCitation/Article/Journal/JournalIssue/PubDate",
        "./MedlineCitation/DateCompleted",
    )
    for path in paths:
        node = article.find(path)
        if node is None:
            continue
        year, month, day = (node.findtext(key) for key in ("Year", "Month", "Day"))
        if year and month and day and month.isdigit():
            try:
                return date(int(year), int(month), int(day))
            except ValueError:
                continue
    return None


def _study_design(publication_types: set[str]) -> str:
    if "practice guideline" in publication_types or "guideline" in publication_types:
        return "clinical_guideline"
    if "meta-analysis" in publication_types:
        return "meta_analysis"
    if "systematic review" in publication_types:
        return "systematic_review"
    if "randomized controlled trial" in publication_types:
        return "randomized_trial"
    if "observational study" in publication_types or "cohort studies" in publication_types:
        return "observational_study"
    return "unknown"


def parse_pubmed_xml(
    payload: bytes,
    *,
    checked_on: date,
    appraisals: Mapping[str, QualityAppraisal],
) -> tuple[ScientificSource, ...]:
    """Parse NCBI EFetch XML; missing appraisal/design/date stays ineligible."""
    root = ET.fromstring(payload)
    sources: list[ScientificSource] = []
    for record in root.findall("./PubmedArticle"):
        pmid = record.findtext("./MedlineCitation/PMID")
        if not pmid:
            continue
        article = record.find("./MedlineCitation/Article")
        if article is None:
            continue
        abstract_parts = []
        for node in article.findall("./Abstract/AbstractText"):
            label = node.get("Label") or node.get("NlmCategory")
            body = _text(node)
            if body:
                abstract_parts.append(f"{label}: {body}" if label else body)
        publication_types = {
            _text(node).lower() for node in article.findall("./PublicationTypeList/PublicationType")
        }
        corrections = {
            (node.get("RefType") or "").lower()
            for node in record.findall("./MedlineCitation/CommentsCorrectionsList/CommentsCorrections")
        }
        retracted = any("retract" in name for name in publication_types | corrections)
        doi = next(((_text(node).strip().lower())
                    for node in record.findall("./PubmedData/ArticleIdList/ArticleId")
                    if node.get("IdType") == "doi"), None)
        authors = tuple(
            name for node in article.findall("./AuthorList/Author")
            if (name := " ".join(filter(None, (
                node.findtext("ForeName"), node.findtext("LastName")
            ))))
        )
        appraisal = appraisals.get(pmid)
        published_on = _publication_date(record)
        source = ScientificSource(
            source_id=f"pmid:{pmid}",
            title=_text(article.find("./ArticleTitle")),
            authors=authors,
            publication=_text(article.find("./Journal/Title")),
            published_on=published_on or date.min,
            doi=doi,
            pmid=pmid,
            source_type="clinical_guideline" if _study_design(publication_types)
                        == "clinical_guideline" else "pubmed_record",
            study_design=_study_design(publication_types),
            peer_reviewed=False,
            pubmed_indexed=True,
            authority_approved=False,
            quality_passed=bool(appraisal and appraisal.passed),
            quality_rubric_version=appraisal.rubric_version if appraisal else "",
            quality_score=appraisal.score if appraisal else 0.0,
            retraction_state="retracted" if retracted else "current",
            retraction_checked_on=checked_on,
            abstract=" ".join(abstract_parts),
        )
        sources.append(source)
    return tuple(sources)


class PubMedClient:
    """Bounded EFetch client for approved PMIDs; callers own rate limiting."""

    def __init__(self, fetch: Callable[[str], bytes] | None = None) -> None:
        self._fetch = fetch or self._http_fetch

    @staticmethod
    def _http_fetch(url: str) -> bytes:
        request = urllib.request.Request(url, headers={"User-Agent": "ClinicalRiskResearch/0.1"})
        with urllib.request.urlopen(request, timeout=15) as response:
            return response.read(10_000_001)

    def fetch_pmids(
        self,
        pmids: Sequence[str],
        *,
        checked_on: date,
        appraisals: Mapping[str, QualityAppraisal],
    ) -> tuple[ScientificSource, ...]:
        if not pmids or len(pmids) > 200 or any(not item.isdigit() for item in pmids):
            raise ValueError("Supply 1 to 200 numeric PMIDs")
        parameters = urllib.parse.urlencode({
            "db": "pubmed", "id": ",".join(pmids), "retmode": "xml",
        })
        url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?{parameters}"
        payload = self._fetch(url)
        if len(payload) > 10_000_000:
            raise ValueError("PubMed response exceeded the ingestion limit")
        results = parse_pubmed_xml(payload, checked_on=checked_on, appraisals=appraisals)
        requested = set(pmids)
        if {item.pmid for item in results} != requested:
            raise ValueError("PubMed response did not match the requested PMID set")
        return results


def refresh_retraction_status(
    sources: Sequence[ScientificSource], current_records: Sequence[ScientificSource]
) -> tuple[ScientificSource, ...]:
    """Fail closed for missing records; retain original quality and text only if current."""
    by_pmid = {item.pmid: item for item in current_records}
    refreshed = []
    for source in sources:
        current = by_pmid.get(source.pmid)
        if current is None or current.doi != source.doi:
            refreshed.append(replace(source, retraction_state="unverified"))
        else:
            refreshed.append(replace(
                source,
                retraction_state=current.retraction_state,
                retraction_checked_on=current.retraction_checked_on,
            ))
    return tuple(refreshed)
