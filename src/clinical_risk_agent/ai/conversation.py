"""Protected one-turn conversational orchestration for the research prototype."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Protocol

from .generation import GenerationRequest, StructuredGenerator
from .routing import (
    LanguageStatus,
    PreflightRequest,
    RequestKind,
    Route,
    RoutingGraph,
    SafetyCategory,
)

CRISIS_RESPONSE = (
    "If you or someone you know is in crisis, help is available. You are not alone. "
    "Please reach out now to Tele-MANAS at 14416 or 1800-89-14416 (free, 24/7), or "
    "the Vandrevala Foundation at +91 9999 666 555 (24/7). If there is immediate "
    "danger, call 112 or go to the nearest hospital emergency department."
)
EMERGENCY_RESPONSE = (
    "EMERGENCY DETECTED: This tool is not a triage or emergency response service. If you "
    "are experiencing a medical or psychological emergency, call 112 (India's national "
    "emergency number) or go immediately to the nearest hospital emergency department."
)
ACUTE_DISTRESS_RESPONSE = (
    "It sounds like you are experiencing a deeply overwhelming and stressful moment. "
    "Because this is an automated research demonstration, I cannot provide the clinical "
    "grounding or support you need right now. Please connect with a trusted friend, family "
    "member, or a qualified mental health professional immediately."
)
MINOR_RESPONSE = (
    "Access denied. This research prototype is approved for adults aged 18 and over. "
    "No risk calculation has been performed."
)
THIRD_PARTY_RESPONSE = (
    "I cannot assess or interpret another person's health information. I can provide "
    "general, non-personalized education, or that person may choose to use the adult "
    "research demonstration themselves."
)
DIAGNOSTIC_RESPONSE = (
    "I am an AI research prototype and cannot diagnose any medical or psychiatric condition."
)
PRESCRIPTIVE_RESPONSE = (
    "I cannot recommend, select, dose, evaluate, start, stop, or change medication or "
    "treatment plans. Please consult a registered medical practitioner, psychiatrist, or "
    "treating doctor before making any changes."
)
LANGUAGE_RESPONSE = "Input error: Language unsupported. Please resubmit your query in English."
ASSESSMENT_RESPONSE = (
    "I cannot calculate clinical probabilities or interpret metric values directly inside "
    "this chat window. To compute a simulated research risk estimate for psychotic or manic "
    "patterns based on generic genetic baselines, please click the link below to launch the "
    "assessment questionnaire."
)
CLARIFICATION_RESPONSE = "I didn't quite catch that. Please select what you would like to do:"
NO_PRIOR_RESULT_RESPONSE = (
    "There is no validated assessment result in this session to explain. You can launch the "
    "research questionnaire if you would like to create one."
)
GENERAL_RESPONSE = (
    "Hello. I can answer the supported research questions about substance use and ADHD or "
    "bullying, or you can open the optional research questionnaire."
)
UNSUPPORTED_RESPONSE = (
    "That request is outside this prototype's bounded research scope. Ask one of the listed "
    "research questions or open the optional research questionnaire."
)
GENERATION_UNAVAILABLE = (
    "I couldn't generate a validated evidence-based response at this time. Please try again later."
)


class ConversationalResearchPort(Protocol):
    def answer_text(self, question: str) -> dict[str, Any]: ...


@dataclass(frozen=True, slots=True)
class ConversationOutcome:
    response_kind: str
    message: str
    citations: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    limitation: str | None = None
    actions: tuple[dict[str, str], ...] = field(default_factory=tuple)
    route: str | None = None
    provider: str | None = None
    model: str | None = None
    corpus_version: str | None = None

    def public_dict(self) -> dict[str, Any]:
        return {
            "response_kind": self.response_kind,
            "message": self.message,
            "citations": list(self.citations),
            "limitation": self.limitation,
            "actions": list(self.actions),
            "route": self.route,
            "provider": self.provider,
            "model": self.model,
            "corpus_version": self.corpus_version,
        }


class ResponseIntegrityError(ValueError):
    """A provider draft failed deterministic post-generation validation."""


class ProtectedConversationOrchestrator:
    def __init__(self, router: RoutingGraph, research: ConversationalResearchPort,
                 generator: StructuredGenerator | None) -> None:
        self._router = router
        self._research = research
        self._generator = generator

    def close(self) -> None:
        if self._generator is not None:
            self._generator.close()

    def handle(self, text: str, *, deployment_mode: str, session_valid: bool) -> dict[str, Any]:
        decision = self._router.advance(PreflightRequest(
            kind=RequestKind.FREE_TEXT, deployment_mode=deployment_mode,
            session_valid=session_valid, text=text,
        ))
        if decision.route is Route.SAFETY_TERMINAL:
            return self._safety(decision.safety_category).public_dict()
        if decision.route is Route.LANGUAGE_TERMINAL:
            return ConversationOutcome(
                "LANGUAGE_UNSUPPORTED", LANGUAGE_RESPONSE, route=decision.route.value,
            ).public_dict()
        if decision.route is Route.CLARIFY_INTENT:
            return ConversationOutcome(
                "INTENT_CLARIFICATION_REQUIRED", CLARIFICATION_RESPONSE,
                actions=(
                    {"id": "submit_risk_assessment_questionnaire",
                     "label": "Submit Risk Assessment Questionnaire"},
                    {"id": "ask_about_schizophrenia_and_clinical_associations",
                     "label": "Ask About Schizophrenia & Clinical Associations"},
                ), route=decision.route.value,
            ).public_dict()
        if decision.route is Route.ASSESSMENT_REDIRECTION:
            return ConversationOutcome(
                "ASSESSMENT_REDIRECTION", ASSESSMENT_RESPONSE,
                actions=({"id": "launch_research_questionnaire_router",
                          "label": "Launch Research Questionnaire Router"},),
                route=decision.route.value,
            ).public_dict()
        if decision.route is Route.LOAD_PRIOR_RESULT:
            return ConversationOutcome(
                "NO_PRIOR_ASSESSMENT_RESULT", NO_PRIOR_RESULT_RESPONSE,
                route=decision.route.value,
            ).public_dict()
        if decision.route is Route.SCIENTIFIC_RETRIEVAL:
            return self._scientific(text, decision.route).public_dict()
        if decision.route is Route.GENERAL_GENERATION:
            return ConversationOutcome(
                "CONVERSATION", GENERAL_RESPONSE, route=decision.route.value,
            ).public_dict()
        return ConversationOutcome(
            "UNSUPPORTED", UNSUPPORTED_RESPONSE, route=decision.route.value,
        ).public_dict()

    @staticmethod
    def _safety(category: SafetyCategory | None) -> ConversationOutcome:
        response = {
            SafetyCategory.EMERGENCY_REDIRECTION: EMERGENCY_RESPONSE,
            SafetyCategory.CRITICAL_SAFETY_REDIRECTION: CRISIS_RESPONSE,
            SafetyCategory.ACUTE_DISTRESS_REDIRECTION: ACUTE_DISTRESS_RESPONSE,
            SafetyCategory.STATE_INELIGIBLE_MINOR: MINOR_RESPONSE,
            SafetyCategory.THIRD_PARTY_REFUSAL: THIRD_PARTY_RESPONSE,
            SafetyCategory.DIAGNOSTIC_REFUSAL: DIAGNOSTIC_RESPONSE,
            SafetyCategory.PRESCRIPTIVE_REFUSAL: PRESCRIPTIVE_RESPONSE,
        }.get(category, UNSUPPORTED_RESPONSE)
        kind = category.value if category is not None else "SAFETY_TERMINAL"
        return ConversationOutcome(kind, response, route=Route.SAFETY_TERMINAL.value)

    def _scientific(self, text: str, route: Route) -> ConversationOutcome:
        result = self._research.answer_text(text)
        status = result.get("status")
        if status == "retrieval_unavailable":
            return ConversationOutcome(
                "RETRIEVAL_UNAVAILABLE", result["answer"],
                limitation=result.get("limitation"), route=route.value,
            )
        if status != "curated_support_available":
            return ConversationOutcome(
                "NO_ELIGIBLE_EVIDENCE", result["answer"],
                limitation=result.get("limitation"), route=route.value,
                corpus_version=result.get("corpus_version"),
            )
        if self._generator is None:
            return ConversationOutcome(
                "GENERATION_UNAVAILABLE", GENERATION_UNAVAILABLE,
                limitation=result.get("limitation"), route=route.value,
                corpus_version=result.get("corpus_version"),
            )
        try:
            message = self._generate_validated(result)
        except Exception:
            return ConversationOutcome(
                "GENERATION_UNAVAILABLE", GENERATION_UNAVAILABLE,
                limitation=result.get("limitation"), route=route.value,
                corpus_version=result.get("corpus_version"),
            )
        return ConversationOutcome(
            "GROUNDED_ANSWER", message, tuple(result["citations"]),
            result.get("limitation"), route=route.value,
            provider=self._generator.provider.value, model=self._generator.model,
            corpus_version=result.get("corpus_version"),
        )

    def _generate_validated(self, result: dict[str, Any]) -> str:
        answer = result["answer"]
        citations = result["citations"]
        allowed_ids = [item["citation_id"] for item in citations]
        evidence = "\n\n".join(
            f"{item['citation_id']} | PMID {item.get('pmid') or 'unavailable'} | "
            f"{item.get('exact_matched_text', '')}" for item in citations
        )
        system = (
            "You are formatting a research-only answer from verified evidence. Return the "
            "required structured object. Copy the APPROVED_ANSWER exactly into text, set "
            "response_kind to grounded_answer, and return exactly the ALLOWED_CITATION_IDS. "
            "Do not add, remove, paraphrase, diagnose, prescribe, or infer anything."
        )
        context = (
            f"APPROVED_ANSWER:\n{answer}\n\n"
            f"ALLOWED_CITATION_IDS: {allowed_ids}\n\nVERIFIED_EVIDENCE:\n{evidence}"
        )
        request = GenerationRequest(system, "Format the approved evidence-grounded answer.", context)
        last_error: Exception | None = None
        for _attempt in range(2):
            draft = self._generator.generate(request)
            try:
                self._validate_draft(draft.response_kind, draft.text, draft.citation_ids,
                                     answer, allowed_ids, citations)
                return draft.text
            except ResponseIntegrityError as error:
                last_error = error
        raise last_error or ResponseIntegrityError("response validation failed")

    @staticmethod
    def _validate_draft(response_kind: str, text: str, citation_ids: list[str],
                        approved_answer: str, allowed_ids: list[str],
                        citations: list[dict[str, Any]]) -> None:
        inline_ids = re.findall(r"\[([A-Za-z0-9_-]+)\]", text)
        if (response_kind != "grounded_answer" or text != approved_answer
                or citation_ids != allowed_ids or inline_ids != allowed_ids
                or not 1 <= len(set(allowed_ids)) <= 5):
            raise ResponseIntegrityError("draft_contract_mismatch")
        for citation in citations:
            excerpt = citation.get("exact_matched_text")
            if excerpt and excerpt in text:
                raise ResponseIntegrityError("raw_evidence_excerpt_in_prose")
