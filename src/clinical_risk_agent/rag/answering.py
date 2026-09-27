"""Bounded, extractive answers for the five curated research assertions.

This is a local research-demo path, not a general medical answer generator.
Question matching is deliberately exact after case/whitespace/punctuation
normalization. A near miss must abstain rather than inherit another endpoint.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from clinical_risk_agent.contracts import EvidenceResult, EvidenceStatus


@dataclass(frozen=True, slots=True)
class CuratedQuestion:
    claim_id: str
    question: str
    pmid: str
    answer: str


CURATED_QUESTIONS = (
    CuratedQuestion(
        "childhood_adhd_later_abuse_dependence",
        "Is childhood ADHD associated with later substance abuse or dependence?",
        "21382538",
        "A meta-analysis of prospective studies reported an association between childhood "
        "ADHD and later "
        "substance abuse or dependence for several substances [S1]. This does not establish "
        "causation or an individual's risk.",
    ),
    CuratedQuestion(
        "mta_childhood_adhd_later_use_frequency",
        "Did the MTA childhood ADHD cohort find more frequent cannabis use and smoking by age 25?",
        "29315559",
        "The MTA cohort reported more frequent marijuana use and daily cigarette smoking "
        "among participants with childhood ADHD [S1]. These are use-frequency findings, "
        "not a diagnosed substance-use-disorder finding.",
    ),
    CuratedQuestion(
        "peer_victimization_later_substance_use",
        "Is fifth-grade peer victimization associated with later adolescent substance use?",
        "28562268",
        "A study reported a small indirect association from fifth-grade peer victimization "
        "through depressive symptoms to tenth-grade substance use [S1]. It does not "
        "establish causation or diagnosed substance use disorder.",
    ),
    CuratedQuestion(
        "cybervictimization_later_experimentation",
        "Is cyberbullying victimization associated with later substance experimentation?",
        "40625792",
        "A cohort study reported an association between cyberbullying victimization and "
        "later alcohol, nicotine, or cannabis experimentation [S1]. Experimentation is "
        "not a diagnosed substance use disorder, and the finding is not causal proof.",
    ),
    CuratedQuestion(
        "bullying_perpetration_early_smoking_drinking",
        "Is bullying perpetration associated with smoking or drinking at age 13?",
        "33224066",
        "A study of adolescents reported an association between bullying perpetration "
        "and smoking or drinking at age 13 [S1]. It does not establish the same finding "
        "for bullying victimization, diagnosed disorder, or causation.",
    ),
)

NO_ADEQUATE_EVIDENCE = (
    "No adequate claim-verified evidence is available for this question in the current "
    "research corpus. Related passages, if shown, are candidates for review, not proof."
)
RETRIEVAL_UNAVAILABLE = (
    "Research retrieval is unavailable right now. No evidence-based answer was produced."
)
RESEARCH_LIMITATION = "Research-only; not a diagnosis, individual risk estimate, or medical advice."


def _normalized(question: str) -> str:
    return re.sub(r"\s+", " ", question.strip().rstrip("?!. ").casefold())


class BoundedResearchAnswerer:
    """Question -> claim ID -> support-filtered retrieval -> cited fixed answer."""

    def __init__(
        self,
        *,
        claim_ids: set[str],
        retrieve_supported: Callable[[str, str], EvidenceResult],
        exploratory_search: Callable[[str, int], dict[str, Any]],
        bounded_use: Callable[[str], str],
    ) -> None:
        expected = {item.claim_id for item in CURATED_QUESTIONS}
        if not expected <= claim_ids:
            raise ValueError("Answer templates differ from the curated assertion catalog")
        self._questions = {_normalized(item.question): item for item in CURATED_QUESTIONS}
        if len(self._questions) != len(CURATED_QUESTIONS):
            raise ValueError("Curated question normalization is not unique")
        self._retrieve_supported = retrieve_supported
        self._exploratory_search = exploratory_search
        self._bounded_use = bounded_use

    @property
    def example_questions(self) -> tuple[str, ...]:
        return tuple(item.question for item in CURATED_QUESTIONS)

    def answer(self, question: str) -> dict[str, Any]:
        if not isinstance(question, str) or not 3 <= len(question.strip()) <= 500:
            raise ValueError("Question must be 3 to 500 characters")
        spec = self._questions.get(_normalized(question))
        if spec is None:
            try:
                exploratory = self._exploratory_search(question, 3)
            except Exception:
                return self._unavailable()
            if exploratory.get("match_status") == "retrieval_unavailable":
                return self._unavailable()
            related = [
                {key: value for key, value in match.items() if key != "citation_id"}
                | {"support_status": "not_verified_for_this_question"}
                for match in exploratory.get("matches", [])
            ]
            return {
                "status": "no_adequate_evidence",
                "research_only": True,
                "answer": NO_ADEQUATE_EVIDENCE,
                "limitation": RESEARCH_LIMITATION,
                "claim_id": None,
                "citations": [],
                "related_unverified_passages": related,
            }
        try:
            result = self._retrieve_supported(question, spec.claim_id)
        except Exception:
            return self._unavailable()
        if result.status is EvidenceStatus.RETRIEVAL_UNAVAILABLE:
            return self._unavailable()
        if (result.status is not EvidenceStatus.SUFFICIENT
                or len(result.items) != 1 or len(result.displays) != 1):
            return self._no_adequate(spec.claim_id)
        item, display = result.items[0], result.displays[0]
        if (item.pmid != spec.pmid or item.citation_id != "S1"
                or display.citation_id != item.citation_id
                or display.source_id != item.source_id
                or display.exact_matched_text != item.exact_matched_text):
            return self._no_adequate(spec.claim_id)
        return {
            "status": "curated_support_available",
            "research_only": True,
            "answer": spec.answer,
            "limitation": RESEARCH_LIMITATION,
            "claim_id": spec.claim_id,
            "retrieval_mode": result.retrieval_mode.value if result.retrieval_mode else None,
            "corpus_version": result.corpus_version,
            "citations": [{
                "citation_id": item.citation_id,
                "pmid": item.pmid,
                "chunk_id": item.chunk_id,
                "title": display.title,
                "exact_matched_text": display.exact_matched_text,
                "bounded_use": self._bounded_use(spec.pmid),
            }],
            "related_unverified_passages": [],
        }

    @staticmethod
    def _no_adequate(claim_id: str) -> dict[str, Any]:
        return {
            "status": "no_adequate_evidence",
            "research_only": True,
            "answer": NO_ADEQUATE_EVIDENCE,
            "limitation": RESEARCH_LIMITATION,
            "claim_id": claim_id,
            "citations": [],
            "related_unverified_passages": [],
        }

    @staticmethod
    def _unavailable() -> dict[str, Any]:
        return {
            "status": "retrieval_unavailable",
            "research_only": True,
            "answer": RETRIEVAL_UNAVAILABLE,
            "limitation": RESEARCH_LIMITATION,
            "claim_id": None,
            "citations": [],
            "related_unverified_passages": [],
        }
