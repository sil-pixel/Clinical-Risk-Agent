"""Protected one-turn conversational orchestration for the research prototype."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

from .errors import EvidenceAbstention, ResponseIntegrityError
from .explanation import ResultExplainer
from .generation import GenerationRequest, StructuredGenerator
from .judging import AnswerJudge
from .messages import (
    ACUTE_DISTRESS_RESPONSE,
    ASSESSMENT_RESPONSE,
    CLARIFICATION_RESPONSE,
    CRISIS_BACKSTOP_INSTRUCTION,
    CRISIS_RESPONSE,
    DIAGNOSTIC_RESPONSE,
    EMERGENCY_RESPONSE,
    GENERAL_RESPONSE,
    GENERATION_UNAVAILABLE,
    LANGUAGE_RESPONSE,
    MINOR_RESPONSE,
    NO_PRIOR_RESULT_RESPONSE,
    PRESCRIPTIVE_RESPONSE,
    QUESTIONNAIRE_ACTION,
    RESEARCH_ACTION,
    SUGGESTION_FOOTER,
    SUGGESTION_QUESTIONS,
    THIRD_PARTY_RESPONSE,
    UNSUPPORTED_RESPONSE,
)
from .response_cache import CuratedAnswerCache, FixedReplyCache
from .routing import (
    Intent,
    PreflightRequest,
    RequestKind,
    Route,
    RoutingGraph,
    SafetyCategory,
)

class ConversationalResearchPort(Protocol):
    """Define bounded research answering and broader corpus search for chat."""
    def answer_text(self, question: str) -> dict[str, Any]:
        """Answer a free-text research question through the bounded evidence workflow."""
        ...
    def search_general(self, question: str) -> dict[str, Any]:
        """Retrieve broader corpus passages for a general research question."""
        ...


@dataclass(frozen=True, slots=True)
class ConversationOutcome:
    """Package a public assistant response with citations and generation provenance."""
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
        """Serialize the outcome into the public response contract."""
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


class ProtectedConversationOrchestrator:
    """Route protected requests into research, education or conversational generation."""
    def __init__(self, router: RoutingGraph, research: ConversationalResearchPort,
                 generator: StructuredGenerator | None, *,
                 judge: StructuredGenerator | None = None) -> None:
        """Bind the protected router, research service and optional LLM generator."""
        self._router = router
        self._research = research
        self._generator = generator
        self._judge = judge if judge is not None else generator
        self._explainer = ResultExplainer(generator)
        self._fixed_replies = FixedReplyCache()
        self._curated_answers = CuratedAnswerCache()
        # Route-to-handler table: a new route adds an entry instead of another branch.
        self._handlers: dict[Route, Callable[..., ConversationOutcome]] = {
            Route.SAFETY_TERMINAL: lambda text, decision, prior: self._safety(
                decision.safety_category),
            Route.LANGUAGE_TERMINAL: lambda text, decision, prior: ConversationOutcome(
                "LANGUAGE_UNSUPPORTED", LANGUAGE_RESPONSE, route=decision.route.value),
            Route.CLARIFY_INTENT: lambda text, decision, prior: self._clarify(
                decision.suggested_intent, decision.route),
            Route.ASSESSMENT_REDIRECTION: lambda text, decision, prior: ConversationOutcome(
                "ASSESSMENT_REDIRECTION", ASSESSMENT_RESPONSE,
                actions=({"id": "launch_research_questionnaire_router",
                          "label": "Launch Research Questionnaire Router"},),
                route=decision.route.value),
            Route.LOAD_PRIOR_RESULT: self._prior_result,
            Route.SCIENTIFIC_RETRIEVAL: lambda text, decision, prior: self._scientific(
                text, decision.route),
            Route.GENERAL_GENERATION: lambda text, decision, prior: self._general(
                text, decision.route),
        }

    def close(self) -> None:
        """Release the owned runtime or provider resources."""
        if self._generator is not None:
            self._generator.close()
        if self._judge is not None and self._judge is not self._generator:
            self._judge.close()

    def evaluate_response(self, question: str, result: dict[str, Any]) -> dict[str, Any]:
        """Judge a delivered live answer; callers retain scores only, never this context."""
        if self._judge is None:
            raise RuntimeError("Quality judge unavailable")
        return AnswerJudge(self._judge).evaluate(question, result)

    def safety_response(self, text: str, *, deployment_mode: str) -> dict[str, Any] | None:
        """Return the fixed safety reply if the safety rules intercept text, else None."""
        decision = self._router.safety_decision(PreflightRequest(
            kind=RequestKind.FREE_TEXT, deployment_mode=deployment_mode,
            session_valid=True, text=text,
        ))
        if decision.category is SafetyCategory.ALLOW_NORMAL_PROCESSING:
            return None
        return self._safety(decision.category).public_dict()

    def handle(self, text: str, *, deployment_mode: str, session_valid: bool,
               confirmed_intent: str | None = None,
               prior_result: dict[str, Any] | None = None) -> dict[str, Any]:
        """Return a cached fixed reply for repeated text, else route and answer.

        ``prior_result`` is this session's validated assessment result, if any; it lets
        result-explanation questions answer from the person's own scores. Replies that
        depend on it are never cached.
        """
        key = None
        if prior_result is None and session_valid:
            key = FixedReplyCache.key(text, deployment_mode=deployment_mode,
                                      confirmed_intent=confirmed_intent)
            cached = self._fixed_replies.get(key)
            if cached is not None:
                return cached
        result = self._respond(text, deployment_mode=deployment_mode,
                               session_valid=session_valid, confirmed_intent=confirmed_intent,
                               prior_result=prior_result)
        if key is not None:
            self._fixed_replies.put(key, result)
        return result

    def _respond(self, text: str, *, deployment_mode: str, session_valid: bool,
                 confirmed_intent: str | None, prior_result: dict[str, Any] | None,
                 ) -> dict[str, Any]:
        """Run protected routing and return the appropriate public conversational outcome."""
        decision = self._router.advance(PreflightRequest(
            kind=RequestKind.FREE_TEXT, deployment_mode=deployment_mode,
            session_valid=session_valid, text=text,
            confirmed_intent=Intent(confirmed_intent) if confirmed_intent else None,
        ))
        handler = self._handlers.get(decision.route)
        if handler is None:
            return ConversationOutcome(
                "UNSUPPORTED", UNSUPPORTED_RESPONSE, route=decision.route.value,
            ).public_dict()
        return handler(text, decision, prior_result).public_dict()

    def _prior_result(self, text: str, decision, prior_result) -> ConversationOutcome:
        """Explain the session's own result, or say there is none yet."""
        if prior_result is not None:
            return self._explain_followup(text, prior_result, decision.route)
        return ConversationOutcome("NO_PRIOR_ASSESSMENT_RESULT", NO_PRIOR_RESULT_RESPONSE,
                                   route=decision.route.value)

    @staticmethod
    def _clarify(suggested: Intent | None, route: Route) -> ConversationOutcome:
        """Ask about the router's best guess when there is one, else offer the generic menu."""
        if suggested is None:
            return ConversationOutcome(
                "INTENT_CLARIFICATION_REQUIRED", CLARIFICATION_RESPONSE,
                actions=(QUESTIONNAIRE_ACTION, RESEARCH_ACTION), route=route.value,
            )
        if suggested is Intent.RISK_ASSESSMENT:
            # Opening the questionnaire already is the confirmation; no resend is needed.
            actions = ({**QUESTIONNAIRE_ACTION, "label": "Yes, open the questionnaire"},
                       RESEARCH_ACTION)
        else:
            actions = ({"id": "confirm_intent", "label": "Yes", "intent": suggested.value},
                       QUESTIONNAIRE_ACTION, RESEARCH_ACTION)
        return ConversationOutcome(
            "INTENT_CLARIFICATION_REQUIRED",
            f"{SUGGESTION_QUESTIONS[suggested]} {SUGGESTION_FOOTER}",
            actions=actions, route=route.value,
        )

    @staticmethod
    def _safety(category: SafetyCategory | None) -> ConversationOutcome:
        """Return the approved terminal message for the selected safety category."""
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
        """Retrieve support and generate a validated research or general-education answer."""
        result = self._research.answer_text(text)
        status = result.get("status")
        if status == "no_adequate_evidence":
            result = self._research.search_general(text)
            status = result.get("status")
        if status == "retrieval_unavailable":
            return ConversationOutcome(
                "RETRIEVAL_UNAVAILABLE", result["answer"],
                limitation=result.get("limitation"), route=route.value,
            )
        if status not in {"curated_support_available", "general_evidence_available"}:
            if self._is_broad_education(text):
                return self._education(text, route)
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
            if status == "curated_support_available":
                message = self._generate_validated(result)
                citations = tuple(result["citations"])
            else:
                message, used_ids = self._generate_general_evidence(text, result)
                citations = tuple(
                    item for item in result["citations"]
                    if item["citation_id"] in used_ids
                )
        except EvidenceAbstention:
            if self._is_broad_education(text):
                return self._education(text, route)
            return ConversationOutcome(
                "NO_ELIGIBLE_EVIDENCE",
                "The retrieved papers do not adequately support an answer to this question.",
                limitation="The corpus is limited; other research may exist.",
                route=route.value, corpus_version=result.get("corpus_version"),
            )
        except Exception:
            return ConversationOutcome(
                "GENERATION_UNAVAILABLE", GENERATION_UNAVAILABLE,
                limitation=result.get("limitation"), route=route.value,
                corpus_version=result.get("corpus_version"),
            )
        return ConversationOutcome(
            "GROUNDED_ANSWER", message, citations,
            result.get("limitation"), route=route.value,
            provider=self._generator.provider.value, model=self._generator.model,
            corpus_version=result.get("corpus_version"),
        )

    @staticmethod
    def _is_broad_education(text: str) -> bool:
        """Identify overview-style questions eligible for general-knowledge education."""
        return bool(re.search(
            r"\b(tell me about|what is|what are|explain|describe|overview)\b",
            text, re.IGNORECASE,
        ))

    def _education(self, text: str, route: Route) -> ConversationOutcome:
        """Generate a mental-health overview without claiming local-corpus support."""
        if self._generator is None:
            return ConversationOutcome(
                "GENERATION_UNAVAILABLE", GENERATION_UNAVAILABLE, route=route.value,
            )
        request = GenerationRequest(
            "Provide a helpful, concise general educational answer about mental health using "
            "your general knowledge. Explain the topic directly in plain language. Do not claim "
            "that the local corpus supports the answer, invent citations, diagnose the user, or "
            "recommend personalized treatment. Avoid blanket disclaimers; the interface displays "
            "the research-demo notice. Return response_kind=conversation with no citation IDs. "
            + CRISIS_BACKSTOP_INSTRUCTION,
            text,
        )
        try:
            draft = self._generator.generate(request)
            if draft.response_kind == "refusal":
                return self._safety(SafetyCategory.CRITICAL_SAFETY_REDIRECTION)
            if draft.citation_ids or self._inline_citation_ids(draft.text):
                raise ResponseIntegrityError("education_citation_mismatch")
            return ConversationOutcome(
                "GENERAL_EDUCATION", draft.text, route=route.value,
                provider=self._generator.provider.value, model=self._generator.model,
            )
        except Exception:
            return ConversationOutcome(
                "GENERATION_UNAVAILABLE", GENERATION_UNAVAILABLE, route=route.value,
            )

    def _general(self, text: str, route: Route) -> ConversationOutcome:
        """Generate a bounded conversational reply without research citations."""
        if self._generator is None:
            return ConversationOutcome(
                "CONVERSATION", GENERAL_RESPONSE, route=route.value,
            )
        request = GenerationRequest(
            (
                "You are a friendly conversational assistant in a research demonstration. "
                "Answer ordinary, non-clinical conversation naturally and concisely. Do not "
                "diagnose, estimate personal health risk, prescribe treatment, or claim to have "
                "searched evidence. If the user asks for medical advice, direct them to an "
                "appropriate professional. Return response_kind=conversation and no citations. "
                + CRISIS_BACKSTOP_INSTRUCTION
            ),
            text,
        )
        try:
            draft = self._generator.generate(request)
            if draft.response_kind == "refusal":
                return self._safety(SafetyCategory.CRITICAL_SAFETY_REDIRECTION)
            if (draft.response_kind != "conversation" or draft.citation_ids
                    or re.search(r"\[[A-Za-z0-9_-]+\]", draft.text)):
                raise ResponseIntegrityError("general_conversation_contract_mismatch")
        except Exception:
            return ConversationOutcome(
                "GENERATION_UNAVAILABLE", GENERATION_UNAVAILABLE, route=route.value,
            )
        return ConversationOutcome(
            "CONVERSATION", draft.text, route=route.value,
            provider=self._generator.provider.value, model=self._generator.model,
        )

    def _generate_general_evidence(
        self, question: str, result: dict[str, Any],
    ) -> tuple[str, list[str]]:
        """Generate a passage-grounded answer and validate its used citation identifiers."""
        citations = result["citations"]
        allowed_ids = [item["citation_id"] for item in citations]
        evidence = "\n\n".join(
            f"{item['citation_id']} | PMID {item.get('pmid') or 'unavailable'} | "
            f"Title: {item.get('title', '')} | Passage: {item.get('exact_matched_text', '')} | "
            f"Approved use: {item.get('bounded_use', '')}"
            for item in citations
        )
        request = GenerationRequest(
            (
                "You are answering a general mental-health research question from only the "
                "retrieved appraised passages supplied below. Do not use outside knowledge. "
                "Give a concise plain-language answer, distinguish association from causation, "
                "and do not diagnose, prescribe, or personalize risk. Cite every factual paragraph "
                "with one or more allowed IDs in square brackets. Do not repeat general disclaimers; "
                "the interface already displays them. Return response_kind=grounded_answer and list "
                "the citation IDs you used."
            ),
            question,
            f"ALLOWED_CITATION_IDS: {allowed_ids}\n\n{evidence}",
        )
        draft = self._generator.generate(request)
        if draft.response_kind == "refusal":
            raise EvidenceAbstention("retrieved_passages_do_not_support_answer")
        used_ids = self._validate_general_evidence_draft(
            draft.response_kind, draft.text, draft.citation_ids, allowed_ids, citations,
        )
        text = draft.text.strip()
        if not self._inline_citation_ids(text):
            text = f"{text} {' '.join(f'[{item}]' for item in used_ids)}"
        return text, used_ids

    @staticmethod
    def _inline_citation_ids(text: str) -> list[str]:
        """Extract supported source identifiers from inline citation groups."""
        ids: list[str] = []
        for group in re.findall(r"\[([^\]]+)\]", text):
            ids.extend(re.findall(r"\bS\d+\b", group))
        return ids

    @staticmethod
    def _validate_general_evidence_draft(
        response_kind: str, text: str, citation_ids: list[str],
        allowed_ids: list[str], citations: list[dict[str, Any]],
    ) -> list[str]:
        """Reject unknown citations and return the source identifiers used by a draft."""
        inline_ids = ProtectedConversationOrchestrator._inline_citation_ids(text)
        reported_ids = [
            match
            for item in citation_ids
            for match in re.findall(r"\bS\d+\b", item)
        ]
        if (response_kind not in {"grounded_answer", "conversation"}
                or any(item not in allowed_ids for item in inline_ids)
                or any(item not in allowed_ids for item in reported_ids)):
            raise ResponseIntegrityError("general_evidence_contract_mismatch")
        for citation in citations:
            excerpt = citation.get("exact_matched_text")
            if excerpt and len(excerpt) > 200 and excerpt in text:
                raise ResponseIntegrityError("raw_evidence_excerpt_in_prose")
        used_ids = list(dict.fromkeys(inline_ids))
        if not used_ids:
            used_ids = list(dict.fromkeys(reported_ids))
        if not used_ids:
            raise EvidenceAbstention("no_sources_identified_by_generator")
        return used_ids

    def explain_assessment(self, result: dict[str, Any]) -> dict[str, Any]:
        """Explain the user's two scores by their level within the reference group."""
        return self._explainer.summarize(result)

    def _explain_followup(self, question: str, result: dict[str, Any],
                          route: Route) -> ConversationOutcome:
        """Answer a chat question about the session's own validated result."""
        try:
            message = self._explainer.answer(question, result)
        except Exception:
            return ConversationOutcome("GENERATION_UNAVAILABLE", GENERATION_UNAVAILABLE,
                                       route=route.value)
        generated = self._generator is not None
        return ConversationOutcome(
            "RESULT_EXPLANATION", message, route=route.value,
            provider=self._generator.provider.value if generated else None,
            model=self._generator.model if generated else None)

    def _generate_validated(self, result: dict[str, Any]) -> str:
        """Generate an approved curated-claim answer with one integrity-repair attempt."""
        answer = result["answer"]
        citations = result["citations"]
        allowed_ids = [item["citation_id"] for item in citations]
        cached = self._curated_answers.get(answer, allowed_ids)
        if cached is not None:
            return cached
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
                # Validation guarantees the text equals the approved answer, so reuse is exact.
                self._curated_answers.put(answer, allowed_ids, draft.text)
                return draft.text
            except ResponseIntegrityError as error:
                last_error = error
        raise last_error or ResponseIntegrityError("response validation failed")

    @staticmethod
    def _validate_draft(response_kind: str, text: str, citation_ids: list[str],
                        approved_answer: str, allowed_ids: list[str],
                        citations: list[dict[str, Any]]) -> None:
        """Check a curated draft against the approved wording and citation contract."""
        inline_ids = re.findall(r"\[([A-Za-z0-9_-]+)\]", text)
        if (response_kind != "grounded_answer" or text != approved_answer
                or citation_ids != allowed_ids or inline_ids != allowed_ids
                or not 1 <= len(set(allowed_ids)) <= 5):
            raise ResponseIntegrityError("draft_contract_mismatch")
        for citation in citations:
            excerpt = citation.get("exact_matched_text")
            if excerpt and excerpt in text:
                raise ResponseIntegrityError("raw_evidence_excerpt_in_prose")
