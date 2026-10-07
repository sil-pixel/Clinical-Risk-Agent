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

POLICY_VERSION = "prototype-safety-rules-v2"
ROUTER_VERSION = "prototype-conversational-router-v2"

_FIRST_PERSON = re.compile(r"\b(i|i'm|im|i've|ive|i'd|i'll|me|my|myself|mine)\b")
_REQUEST_PHRASE = re.compile(r"\b(tell|show|give|help) me\b")
_RESEARCH_FRAMING = re.compile(
    r"\b(research|study|studies|evidence|papers?|literature|cohort|trials?|risks?|rates?|"
    r"prevalence|associat\w*|linked|link|correlat\w*|factors?|predict\w*|population|"
    r"patients|people|individuals|adolescents|youth|among|mechanisms?|statistics|"
    r"what is|what are|tell me about|explain|define)\b"
)
_PILLS = r"(pills|tablets|meds|medication|medicine|sleeping pills|painkillers)"

# Expressions that describe the writer's (or another person's) own danger. These always
# intercept, whatever else the message contains.
_PERSONAL_RISK_RULES = (
    (SafetyCategory.EMERGENCY_REDIRECTION, tuple(re.compile(pattern) for pattern in (
        r"\bimmediate danger\b", r"\bmedical emergency\b", r"\bcall an ambulance\b",
        rf"\b(took|taken|swallowed|ate)\b.{{0,30}}\b(too many|a lot of|all (of )?(my|the)|"
        rf"a bottle of|a bunch of|a handful of)\b.{{0,20}}\b{_PILLS}",
    ))),
    (SafetyCategory.CRITICAL_SAFETY_REDIRECTION, tuple(re.compile(pattern) for pattern in (
        r"\b(kill|hurt|harm|cut|injur|poison|hang|shoot|drown|burn|starv)\w* myself\b",
        r"\b(wants?|going|trying|tried|plans?|planning|threaten\w*) to (kill|hurt|harm) "
        r"(himself|herself|themselves|themself)\b",
        r"\bend(ing)? (it all|my (own )?life)\b",
        r"\btak(e|ing) my (own )?life\b",
        r"\b(don'?t|do not|no longer) want to (live|be alive|exist|be here any ?more|wake up)\b",
        r"\bwant(ed|s)? to (die|be dead)\b",
        r"\bwish i (was|were|had) (dead|never been born)\b",
        r"\bwish i could (die|disappear forever)\b",
        r"\bbetter off (dead|without me)\b",
        r"\b(no|nothing) (reason )?to live for\b",
        r"\bno reason to (live|go on)\b",
        r"\bcan'?t (go on|keep going|take (it|this) any ?more)\b",
        r"\b(kms|unalive)\b",
    ))),
    (SafetyCategory.ACUTE_DISTRESS_REDIRECTION, tuple(re.compile(pattern) for pattern in (
        r"\bi('m| am|m) hallucinating\b", r"\bi (hear|keep hearing) voices\b",
        r"\bvoices\b.{0,20}\b(telling|told|tell) me\b",
        r"\bi('m| am|m) (hearing|seeing) things\b",
        r"\b(someone|people|they) (is|are) (watching|following|after) me\b",
        r"\bhaving a panic attack\b", r"\bsevere panic\b",
    ))),
)

# Topic words that are also legitimate research subjects. They intercept unless the
# message is framed as a research or educational question without any first-person
# reference, so "suicide risk in schizophrenia" is answerable but "my suicide plan" is not.
_TOPIC_RULES = (
    (SafetyCategory.EMERGENCY_REDIRECTION, (re.compile(r"\boverdos\w*"),)),
    (SafetyCategory.CRITICAL_SAFETY_REDIRECTION, (
        re.compile(r"\bsuicid\w*"), re.compile(r"\bself[- ]?harm\w*"),
        re.compile(r"\bself[- ]?injur\w*"),
    )),
)


def _normalized(text: str) -> str:
    """Normalize transient input text for deterministic prototype classification."""
    return re.sub(r"\s+", " ", text.strip().rstrip("?!. ").casefold())


def _safety_text(text: str) -> str:
    """Casefold text and unify apostrophes and whitespace for safety matching."""
    return re.sub(r"\s+", " ", text.replace("’", "'").replace("‘", "'").casefold())


class PrototypeSafetyPort:
    """High-recall deterministic intercepts with architecture-defined priority."""

    def evaluate(self, request: PreflightRequest) -> SafetyDecision:
        """Classify text against the prototype safety interception rules."""
        text = _safety_text(request.text or "")
        research_question = (bool(_RESEARCH_FRAMING.search(text))
                             and not _FIRST_PERSON.search(_REQUEST_PHRASE.sub("", text)))
        for category, patterns in _PERSONAL_RISK_RULES:
            if any(pattern.search(text) for pattern in patterns):
                return SafetyDecision(category, POLICY_VERSION, f"rule_{category.value.lower()}")
        if not research_question:
            for category, patterns in _TOPIC_RULES:
                if any(pattern.search(text) for pattern in patterns):
                    return SafetyDecision(
                        category, POLICY_VERSION, f"rule_{category.value.lower()}_topic",
                    )
        rules = (
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
        """Classify English support using the bounded prototype language rules."""
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
        "schizophrenia", "psychosis", "bipolar", "mania", "anxiety", "ocd", "ptsd",
        "trauma", "mental health", "psychiatric", "abuse", "adverse childhood", "ace",
    }
    _research_terms = {
        "association", "associated", "research", "evidence", "study", "studies",
        "paper", "papers", "linked", "relationship", "mechanism", "population",
    }

    @staticmethod
    def _decision(intent: Intent, confidence: float, clarify: bool, rationale: str):
        """Create a prototype intent decision with stable calibration provenance."""
        return IntentDecision(
            intent, confidence, clarify, "deterministic-prototype-rules",
            "not-applicable-no-model-artifact", "prototype-rules-not-calibrated",
            ROUTER_VERSION, rationale,
        )

    def classify(self, text: str) -> IntentDecision:
        """Classify assessment, research, education or conversational intent."""
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
        educational_phrases = ("tell me about", "what is", "what are", "explain", "describe")
        if tokens & self._topics and (
            tokens & self._research_terms or "?" in text
            or any(phrase in normalized for phrase in educational_phrases)
        ):
            return self._decision(Intent.SCIENTIFIC_QUESTION, 0.95, False, "research_education")
        if normalized in {"hi", "hello", "hey", "good morning", "good afternoon", "good evening"}:
            return self._decision(Intent.GENERAL_CONVERSATION, 1.0, False, "greeting")
        if len(tokens) < 3:
            return self._decision(Intent.UNSUPPORTED_OR_UNSAFE, 0.0, True, "too_ambiguous")
        return self._decision(Intent.GENERAL_CONVERSATION, 0.9, False, "general_conversation")
