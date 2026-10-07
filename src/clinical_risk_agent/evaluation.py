"""Regression metrics for labeled non-user evaluation pairs, with tie-aware ranks."""

import numpy as np


def _ranks(values):
    """Assign average ranks to tied values for Spearman correlation."""
    order = np.argsort(values, kind="stable")
    ranks = np.empty(len(values), dtype=float)
    start = 0
    while start < len(values):
        end = start + 1
        while end < len(values) and values[order[end]] == values[order[start]]:
            end += 1
        ranks[order[start:end]] = (start + end - 1) / 2 + 1
        start = end
    return ranks


def regression_metrics(actual, predicted):
    """Compute MSE, RMSE, R-squared and tie-aware Spearman correlation."""
    y, p = np.asarray(actual, dtype=float), np.asarray(predicted, dtype=float)
    if y.ndim != 1 or y.shape != p.shape or len(y) < 2:
        raise ValueError("At least two paired observations are required")
    if not np.isfinite(y).all() or not np.isfinite(p).all():
        raise ValueError("Evaluation values must be finite")
    mse = float(np.mean((y - p) ** 2))
    variance = float(np.sum((y - y.mean()) ** 2))
    ry, rp = _ranks(y), _ranks(p)
    rho = (float(np.corrcoef(ry, rp)[0, 1])
           if np.ptp(ry) > 0 and np.ptp(rp) > 0 else None)
    return {"mse": mse, "rmse": mse ** 0.5,
            "r2": float(1 - np.sum((y - p) ** 2) / variance) if variance > 0 else None,
            "spearman_rho": rho, "n": len(y)}


CLARIFY = "clarify"


def classification_metrics(expected, predicted, labels):
    """Per-label precision/recall/F1, accuracy, macro-F1 and confusion counts.

    ``CLARIFY`` is both a valid prediction (the router abstained) and a valid expectation
    (vague text should be clarified). Abstaining on a labeled case lowers that label's
    recall without counting against any label's precision. Macro averages use ``labels``
    with support only, so the clarification class is reported but not averaged in; a label
    that is never predicted has undefined precision, counted as 0 in the macro average.
    """
    if len(expected) != len(predicted) or not expected:
        raise ValueError("Expected and predicted labels must be non-empty and paired")
    classes = [*labels, CLARIFY]
    unknown = (set(expected) | set(predicted)) - set(classes)
    if unknown:
        raise ValueError(f"Unknown labels: {sorted(unknown)}")
    confusion = {truth: dict.fromkeys(classes, 0) for truth in classes}
    for truth, guess in zip(expected, predicted, strict=True):
        confusion[truth][guess] += 1
    per_label = {}
    for label in classes:
        tp = confusion[label][label]
        predicted_n = sum(confusion[truth][label] for truth in classes)
        support = sum(confusion[label].values())
        precision = tp / predicted_n if predicted_n else None
        recall = tp / support if support else None
        f1 = (2 * precision * recall / (precision + recall)
              if precision and recall else 0.0 if support or predicted_n else None)
        per_label[label] = {"precision": precision, "recall": recall, "f1": f1,
                            "support": support, "predicted": predicted_n}

    def macro(key):
        """Average a per-label score over labels where it is defined."""
        values = [per_label[label][key] or 0.0 for label in labels
                  if per_label[label]["support"]]
        return sum(values) / len(values) if values else None

    correct = sum(truth == guess for truth, guess in zip(expected, predicted, strict=True))
    abstained = [truth for truth, guess in zip(expected, predicted, strict=True)
                 if guess == CLARIFY and truth != CLARIFY]
    return {"n": len(expected), "accuracy": correct / len(expected),
            "macro_precision": macro("precision"), "macro_recall": macro("recall"),
            "macro_f1": macro("f1"),
            "coverage": sum(guess != CLARIFY for guess in predicted) / len(predicted),
            "clarified_labeled_cases": len(abstained),
            "per_label": per_label, "confusion": confusion}
