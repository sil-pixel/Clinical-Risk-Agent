"""Manifest-gated public PubMed ingestion for the two benchmark strategies."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path

from .corpus import EVIDENCE_TIERS, ScientificSource
from .pubmed import PubMedClient, QualityAppraisal


@dataclass(frozen=True, slots=True)
class ApprovedSource:
    pmid: str
    appraisal: QualityAppraisal
    reviewer: str
    reviewed_on: date
    topic: str
    study_design: str
    design_override_reason: str | None = None


APPROVED_TOPICS = frozenset({
    "substance_use", "schizophrenia", "depression", "psychosis",
    "emotional_abuse", "sexual_abuse", "physical_abuse", "bullying",
    "adhd", "asd", "supported_association",
})


def load_approved_sources(path: Path, *, today: date) -> tuple[ApprovedSource, ...]:
    """Fail closed on missing or unreviewed sources; do not infer appraisals."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("schema_version") != 1:
        raise ValueError("Expected source manifest schema_version 1")
    entries = raw.get("sources")
    if not isinstance(entries, list) or not entries:
        raise ValueError("Source manifest must contain approved publications")
    approved: list[ApprovedSource] = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("Source manifest entry must be an object")
        pmid = entry.get("pmid")
        reviewer = entry.get("reviewer")
        topic = entry.get("topic")
        study_design = entry.get("study_design")
        design_override_reason = entry.get("design_override_reason")
        appraisal = entry.get("appraisal")
        if (not isinstance(pmid, str) or not pmid.isdigit() or pmid.startswith("0")
                or not isinstance(reviewer, str) or not reviewer.strip()
                or topic not in APPROVED_TOPICS or study_design not in EVIDENCE_TIERS
                or (design_override_reason is not None and
                    (not isinstance(design_override_reason, str)
                     or not design_override_reason.strip()))
                or not isinstance(appraisal, dict)):
            raise ValueError("Source identity, reviewer, topic, or appraisal is invalid")
        reviewed_on = date.fromisoformat(entry["reviewed_on"])
        if reviewed_on > today:
            raise ValueError("Source appraisal date cannot be in the future")
        if appraisal.get("passed") is not True:
            raise ValueError("Source quality appraisal must pass before ingestion")
        score = appraisal.get("score")
        rubric = appraisal.get("rubric_version")
        if (isinstance(score, bool) or not isinstance(score, (int, float))
                or not 0 <= score <= 1 or not isinstance(rubric, str)
                or not rubric.strip()):
            raise ValueError("Source quality score or rubric is invalid")
        approved.append(ApprovedSource(
            pmid, QualityAppraisal(True, float(score), rubric),
            reviewer.strip(), reviewed_on, topic, study_design,
            design_override_reason.strip() if design_override_reason else None,
        ))
    if len({item.pmid for item in approved}) != len(approved):
        raise ValueError("Duplicate PMID in source manifest")
    return tuple(approved)


def fetch_approved_pubmed_sources(
    approved: tuple[ApprovedSource, ...], *, today: date,
    client: PubMedClient | None = None,
) -> tuple[ScientificSource, ...]:
    """Fetch in bounded EFetch batches; source eligibility is checked downstream."""
    pubmed = client or PubMedClient()
    appraisals: Mapping[str, QualityAppraisal] = {
        item.pmid: item.appraisal for item in approved
    }
    results = []
    for start in range(0, len(approved), 200):
        pmids = tuple(item.pmid for item in approved[start:start + 200])
        results.extend(pubmed.fetch_pmids(
            pmids, checked_on=today, appraisals=appraisals
        ))
    by_pmid = {item.pmid: item for item in approved}
    normalized = []
    for source in results:
        declared = by_pmid[source.pmid].study_design
        if (source.study_design != "unknown" and source.study_design != declared
                and not by_pmid[source.pmid].design_override_reason):
            raise ValueError("Reviewed study design conflicts with PubMed metadata")
        normalized.append(replace(source, study_design=declared))
    return tuple(normalized)
