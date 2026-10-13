"""Plain-language explanations of a person's own validated assessment result."""

from __future__ import annotations

import re
from typing import Any

from clinical_risk_agent.interpretation import DEFINITIONS, fallback_explanation

from .errors import ResponseIntegrityError
from .generation import GenerationRequest, StructuredGenerator
from .messages import CRISIS_BACKSTOP_INSTRUCTION

# Shared constraints for every explanation of a user's own result.
EXPLANATION_RULES = (
    "Use only the numbers in the result context and never invent thresholds, risks or "
    "causes. Do not diagnose, predict whether they will develop a condition, or recommend "
    "treatment. Do not read a percentage as how many similar people develop a condition. "
    "Mention once, briefly, that these are research estimates from a model trained on "
    "synthetic data and compared with a synthetic reference group, not a diagnosis; if they "
    "are worried about their mental health, a qualified professional can help. Speak to "
    "the person as 'you', calmly, without policy language. Return response_kind=conversation "
    "and no citations." + " " + CRISIS_BACKSTOP_INSTRUCTION
)
SUMMARY_INSTRUCTION = (
    "Explain this person's two research-model results directly to them. For each score, "
    "give the exact value, its level and percentile, and what that level means for that "
    "symptom category in everyday words, using the definitions provided. Make the meaning "
    "specific to the level: a high level means the model's estimate is higher than for most "
    "of the reference group; a low level means lower than most. End by inviting them to ask "
    "follow-up questions here. At most two short paragraphs and 170 words."
)
FOLLOWUP_INSTRUCTION = (
    "Answer the person's question about their own results, using only the result context. "
    "Keep it conversational and specific to their levels. If they ask why a score is high "
    "or low, explain that the model weighs all answers together and that per-answer causes "
    "are not available. At most 120 words."
)


def result_context(result: dict[str, Any]) -> str:
    """Describe validated scores, reference positions and definitions for the LLM."""
    lines = []
    for target, label in (("positive", "Positive-symptom"), ("negative", "Negative-symptom")):
        value = result[f"{target}_symptom_research_probability"]
        reference = result.get(f"{target}_reference")
        position = (f"; {reference['level']} level, {reference['percentile_text']} of the "
                    f"synthetic reference group" if reference else
                    "; reference position unavailable")
        lines.append(f"{label} estimate: {value}{position}. Measures {DEFINITIONS[target]}.")
    lines.append("Levels by reference percentile: low below 25th, typical 25th-74th, "
                 "above typical 75th-89th, high 90th and above.")
    return "\n".join(lines)


def required_terms(result: dict[str, Any]) -> list[str]:
    """Exact strings an explanation must preserve: both scores and any percentiles."""
    terms = [str(result["positive_symptom_research_probability"]),
             str(result["negative_symptom_research_probability"])]
    terms += [result[f"{target}_reference"]["percentile_text"]
              for target in ("positive", "negative") if result.get(f"{target}_reference")]
    return terms


class ResultExplainer:
    """Generate result-grounded explanations that cannot change or invent numbers."""

    def __init__(self, generator: StructuredGenerator | None) -> None:
        """Bind the answering model; without one, explanations use the fixed fallback."""
        self._generator = generator

    def _draft(self, instruction: str, user_text: str, result: dict[str, Any], *,
               require_all: bool) -> str:
        """Generate text and reject drafts that alter, omit or add result numbers."""
        draft = self._generator.generate(GenerationRequest(
            instruction + " " + EXPLANATION_RULES, user_text, result_context(result)))
        allowed = set(required_terms(result))
        percentages = set(re.findall(r"\d+(?:\.\d+)?%", draft.text))
        if (draft.response_kind != "conversation" or draft.citation_ids
                or not percentages <= allowed
                or (require_all and not all(term in draft.text for term in allowed))):
            raise ResponseIntegrityError("assessment_explanation_contract_mismatch")
        return draft.text.strip()

    def summarize(self, result: dict[str, Any]) -> dict[str, Any]:
        """Explain both scores by level, falling back to fixed text on any failure."""
        if self._generator is None:
            return {"message": fallback_explanation(result), "provider": None, "model": None,
                    "generated_by_llm": False}
        try:
            message = self._draft(SUMMARY_INSTRUCTION, "Explain my results.", result,
                                  require_all=True)
            generated = True
        except Exception:
            message, generated = fallback_explanation(result), False
        return {"message": message,
                "provider": self._generator.provider.value if generated else None,
                "model": self._generator.model if generated else None,
                "generated_by_llm": generated}

    def answer(self, question: str, result: dict[str, Any]) -> str:
        """Answer one follow-up question from the result; raises if the draft is invalid."""
        if self._generator is None:
            return fallback_explanation(result)
        return self._draft(FOLLOWUP_INSTRUCTION, question, result, require_all=False)
