"""Place a model score within the reference distribution of the same model's outputs.

The reference is the deployed checkpoint's predictions on the synthetic dataset, built in
the same form live users submit (complete answers, hidden genetic inputs at training
medians). A percentile and a coarse level are descriptive positions within that synthetic
group, never clinical cut-offs or diagnoses.
"""

from __future__ import annotations

import bisect
import json
from pathlib import Path

SCORE_REFERENCE_PATH = Path("data/monitoring/score_reference.json")
# Levels by percentile within the reference group: below 25, 25-74, 75-89, 90 and above.
LEVELS = ((90, "high"), (75, "above typical"), (25, "typical"), (0, "low"))
DEFINITIONS = {
    "positive": ("psychotic and manic symptom patterns, such as hearing or seeing things others "
                 "do not, firmly held beliefs that do not match reality, or unusually elevated "
                 "mood or energy"),
    "negative": ("depressive symptom patterns, such as persistent low mood and loss of interest "
                 "(this model's negative target, which differs from the clinical meaning of "
                 "negative symptoms in schizophrenia)"),
}


def ordinal(number: int) -> str:
    """Return an English ordinal such as 1st, 22nd or 93rd."""
    suffix = "th" if 10 <= number % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")
    return f"{number}{suffix}"


def load_score_reference(root: Path) -> dict | None:
    """Load the reference score quantiles, or None when they have not been built."""
    try:
        return json.loads((root / SCORE_REFERENCE_PATH).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def interpret(value: float, quantiles: list[float]) -> dict:
    """Return the percentile (0-99) of value among reference quantiles and its level."""
    if len(quantiles) != 101:
        raise ValueError("Expected quantiles at every percentile from 0 to 100")
    percentile = min(99, max(0, bisect.bisect_right(quantiles, value) - 1))
    level = next(name for floor, name in LEVELS if percentile >= floor)
    text = ("lowest percentile" if percentile == 0 else
            "highest percentile" if percentile == 99 else f"{ordinal(percentile)} percentile")
    return {"percentile": percentile, "level": level, "percentile_text": text}


def fallback_explanation(result: dict) -> str:
    """Deterministic explanation used when the LLM explanation is unavailable."""
    parts = []
    for target, label in (("positive", "positive-symptom"), ("negative", "negative-symptom")):
        value = result[f"{target}_symptom_research_probability"]
        context = result.get(f"{target}_reference")
        position = (f", which is {context['level']} ({context['percentile_text']} of the "
                    f"synthetic reference group)" if context else "")
        parts.append(f"Your {label} estimate is {value}{position}. It reflects "
                     f"{DEFINITIONS[target]}.")
    return (" ".join(parts) + " These are separate research-model estimates from synthetic "
            "training data, not a diagnosis.")
