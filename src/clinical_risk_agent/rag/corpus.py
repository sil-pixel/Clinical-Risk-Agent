"""Strict scientific-source admission and immutable corpus metadata."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date


DOI_PATTERN = re.compile(r"^10\.\d{4,9}/\S+$", re.IGNORECASE)
PMID_PATTERN = re.compile(r"^[1-9]\d*$")
RETRACTION_MAX_AGE_DAYS = 14
EVIDENCE_TIERS = {
    "clinical_guideline": 1,
    "systematic_review": 2,
    "meta_analysis": 2,
    "randomized_trial": 3,
    "observational_study": 4,
    "expert_opinion": 5,
}
SOURCE_TYPES = {"journal_article", "pubmed_record", "authority_publication", "clinical_guideline"}


@dataclass(frozen=True, slots=True)
class SourceSection:
    name: str
    text: str
    locator: str


@dataclass(frozen=True, slots=True)
class ScientificSource:
    source_id: str
    title: str
    authors: tuple[str, ...]
    publication: str
    published_on: date
    doi: str | None
    pmid: str | None
    source_type: str
    study_design: str
    peer_reviewed: bool
    pubmed_indexed: bool
    authority_approved: bool
    quality_passed: bool
    quality_rubric_version: str
    retraction_state: str
    retraction_checked_on: date
    abstract: str
    full_text_sections: tuple[SourceSection, ...] = ()
    full_text_license: str | None = None
    license_allows_storage_display: bool = False
    data_class: str = "scientific_publication"
    document_scope: str = "general_mental_health"
    contains_patient_data: bool = False
    stance: str | None = None
    stance_claim_id: str | None = None
    quality_score: float = 0.0
    issuing_authority: str | None = None


def _twenty_year_cutoff(today: date) -> date:
    try:
        return today.replace(year=today.year - 20)
    except ValueError:  # February 29
        return today.replace(year=today.year - 20, day=28)


def source_rejection_reasons(source: ScientificSource, *, today: date) -> tuple[str, ...]:
    """Return only stable reason codes, never source text or identifiers."""
    reasons: list[str] = []
    if (
        source.data_class != "scientific_publication"
        or source.document_scope != "general_mental_health"
        or source.contains_patient_data
    ):
        reasons.append("isolation_metadata_invalid")
    if not source.source_id or not source.title.strip() or not source.publication.strip():
        reasons.append("bibliography_incomplete")
    if not (
        (source.doi and DOI_PATTERN.fullmatch(source.doi))
        or (source.pmid and PMID_PATTERN.fullmatch(source.pmid))
    ):
        reasons.append("identifier_missing")
    if source.published_on < _twenty_year_cutoff(today) or source.published_on > today:
        reasons.append("publication_date_ineligible")
    if (
        source.source_type not in SOURCE_TYPES
        or not (source.peer_reviewed or source.pubmed_indexed or source.authority_approved)
    ):
        reasons.append("source_class_ineligible")
    if source.study_design not in EVIDENCE_TIERS:
        reasons.append("study_design_unknown")
    if not source.quality_passed or not source.quality_rubric_version:
        reasons.append("quality_appraisal_missing_or_failed")
    if not 0.0 <= source.quality_score <= 1.0:
        reasons.append("quality_score_invalid")
    if source.retraction_state != "current":
        reasons.append("retracted_or_unverified")
    if not 0 <= (today - source.retraction_checked_on).days <= RETRACTION_MAX_AGE_DAYS:
        reasons.append("retraction_check_stale")
    if not source.abstract.strip() and not source.full_text_sections:
        reasons.append("source_text_missing")
    if source.full_text_sections and (
        not source.full_text_license or not source.license_allows_storage_display
    ):
        reasons.append("full_text_license_unverified")
    if any(not section.name or not section.text.strip() or not section.locator
           for section in source.full_text_sections):
        reasons.append("section_invalid")
    if (source.stance not in (None, "supports", "refutes")
            or (source.stance is None) != (source.stance_claim_id is None)
            or (source.stance_claim_id is not None and not source.stance_claim_id.strip())):
        reasons.append("stance_invalid")
    return tuple(reasons)


def eligible_source(source: ScientificSource, *, today: date) -> bool:
    return not source_rejection_reasons(source, today=today)
