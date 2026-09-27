"""Conservative local routing ports for the bounded public prototype.

These deterministic rules make the current demo functional; they are not a
substitute for the versioned classifier artifacts and evaluation required for
a production or clinical release.
"""

from __future__ import annotations

import re

from clinical_risk_agent.rag.answering import CURATED_QUESTIONS

from .routing import (
    Intent,
    IntentDecision,
    LanguageDecision,
    LanguageStatus,
    PreflightRequest,
    SafetyCategory,
    SafetyDecision,
)

POLICY_VERSION = "prototype-safety-rules-v1"
ROUTER_VERSION = "prototype-bounded-router-v1"


def _normalized(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().rstrip("?!. ").casefold())


class PrototypeSafetyPort:
    """High-precision deterministic intercepts with architecture-defined priority."""

    def evaluate(self, request: PreflightRequest) -> SafetyDecision:
        text = (request.text or "").casefold()
        rules = (
            (SafetyCategory.EMERGENCY_REDIRECTION, (
                "overdose", "immediate danger", "medical emergency", "call an ambulance",
            )),
            (SafetyCategory.CRITICAL_SAFETY_REDIRECTION, (
                "kill myself", "end my life", "want to die", "suicide", "self-harm",
                "self harm",
            )),
            (SafetyCategory.ACUTE_DISTRESS_REDIRECTION, (
                "i am hallucinating", "i'm hallucinating", "i hear voices",
                "voices are telling me", "someone is watching me", "severe panic",
            )),
            (SafetyCategory.STATE_INELIGIBLE_MINOR, (
                "i am under 18", "i'm under 18", "i am a minor", "i'm a minor",
            )),
            (SafetyCategory.THIRD_PARTY_REFUSAL, (
                "assess my child", "assess my partner", "diagnose my child",
                "diagnose my partner", "my child's risk", "my partner's risk",
            )),
            (SafetyCategory.DIAGNOSTIC_REFUSAL, (
                "diagnose me", "do i have adhd", "do i have autism", "do i have depression",
                "do i have schizophrenia", "am i psychotic",
            )),
            (SafetyCategory.PRESCRIPTIVE_REFUSAL, (
                "recommend medication", "which medication", "what medication",
                "what drug should", "which drug should", "change my medication",
                "stop my medication", "start medication", "dose should", "dosage should",
                "treatment plan",
            )),
        )
        for category, phrases in rules:
            if any(phrase in text for phrase in phrases):
                return SafetyDecision(category, POLICY_VERSION, f"rule_{category.value.lower()}")
        return SafetyDecision(
            SafetyCategory.ALLOW_NORMAL_PROCESSING, POLICY_VERSION, "no_rule_match",
        )


class PrototypeLanguagePort:
    """Bounded English gate for the demo; intentionally abstains on non-ASCII input."""

    def classify(self, text: str) -> LanguageDecision:
        letters = re.findall(r"[A-Za-z]", text)
        if text.isascii() and len(letters) >= 2:
            status = LanguageStatus.SUPPORTED_ENGLISH
            rationale = "ascii_english_candidate"
        else:
            status = LanguageStatus.UNCERTAIN_LANGUAGE
            rationale = "prototype_language_abstention"
        return LanguageDecision(status, "prototype-ascii-gate-v1", rationale)


class PrototypeIntentPort:
    """Routes only bounded, recognizable demo intents; ambiguous text abstains."""

    _curated = {_normalized(item.question) for item in CURATED_QUESTIONS}
    _topics = {
        "adhd", "autism", "asd", "bullying", "cyberbullying", "substance", "alcohol",
        "cannabis", "smoking", "nicotine", "genetic", "genetics", "depression",
        "schizophrenia", "psychosis", "abuse", "adverse childhood", "ace",
    }
    _research_terms = {
        "association", "associated", "research", "evidence", "study", "studies",
        "paper", "papers", "linked", "relationship", "mechanism", "population",
    }

    @staticmethod
    def _decision(intent: Intent, confidence: float, clarify: bool, rationale: str):
        return IntentDecision(
            intent, confidence, clarify, "deterministic-prototype-rules",
            "not-applicable-no-model-artifact", "prototype-rules-not-calibrated",
            ROUTER_VERSION, rationale,
        )

    def classify(self, text: str) -> IntentDecision:
        normalized = _normalized(text)
        tokens = set(re.findall(r"[a-z]+", normalized))
        if normalized in self._curated:
            return self._decision(Intent.SCIENTIFIC_QUESTION, 1.0, False, "curated_question")
        if any(phrase in normalized for phrase in (
            "calculate my risk", "estimate my risk", "risk assessment", "take the questionnaire",
            "fill the questionnaire",
        )):
            return self._decision(Intent.RISK_ASSESSMENT, 1.0, False, "assessment_request")
        if any(phrase in normalized for phrase in (
            "explain my result", "explain my risk", "what does my score mean",
        )):
            return self._decision(Intent.EXPLAIN_MY_RISK, 1.0, False, "result_explanation")
        if tokens & self._topics and (tokens & self._research_terms or "?" in text):
            return self._decision(Intent.SCIENTIFIC_QUESTION, 0.95, False, "bounded_research")
        if normalized in {"hi", "hello", "hey", "good morning", "good afternoon", "good evening"}:
            return self._decision(Intent.GENERAL_CONVERSATION, 1.0, False, "greeting")
        if len(tokens) < 3:
            return self._decision(Intent.UNSUPPORTED_OR_UNSAFE, 0.0, True, "too_ambiguous")
        return self._decision(Intent.UNSUPPORTED_OR_UNSAFE, 1.0, False, "outside_bounded_scope")
