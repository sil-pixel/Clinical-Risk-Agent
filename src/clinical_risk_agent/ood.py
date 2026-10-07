"""Out-of-distribution scoring of questionnaire answer codes against aggregate reference statistics.

Two per-submission scores are compared with thresholds taken from the reference rows:
average answer surprise (negative log-likelihood under independent, Laplace-smoothed
reference marginals) and squared Mahalanobis distance, which also reflects correlations.
Only the reference statistics are stored; live submissions are scored and discarded.
"""

import numpy as np

OOD_QUANTILE = 0.99


def _modes(counts):
    """Return each feature's most frequent reference code, used to fill missing values."""
    return {name: int(max(values, key=values.get)) for name, values in counts.items()}


def _matrix(rows, features, modes):
    """Stack answer codes, filling missing reference values with the feature's modal code."""
    matrix = np.empty((len(rows), len(features)))
    for i, row in enumerate(rows):
        for j, name in enumerate(features):
            value = row.get(name)
            missing = value is None or value == "" or np.isnan(float(value))
            matrix[i, j] = modes[name] if missing else round(float(value))
    return matrix


def _surprise(matrix, features, log_probs, unseen):
    """Average negative log-likelihood per feature; unseen codes receive the smoothed floor."""
    total = np.zeros(len(matrix))
    for j, name in enumerate(features):
        table = log_probs[name]
        total += [table.get(str(int(code)), unseen[name]) for code in matrix[:, j]]
    return -total / len(features)


def _mahalanobis(matrix, mean, precision):
    """Squared Mahalanobis distance of each row from the reference centroid."""
    centered = matrix - mean
    return np.einsum("ij,jk,ik->i", centered, precision, centered)


def build_ood_reference(rows, features, counts, quantile=OOD_QUANTILE):
    """Fit aggregate OOD statistics and reference-quantile thresholds from labeled rows."""
    log_probs, unseen = {}, {}
    for name in features:
        values = counts[name]
        denominator = sum(values.values()) + len(values) + 1
        log_probs[name] = {code: float(np.log((n + 1) / denominator))
                           for code, n in values.items()}
        unseen[name] = float(np.log(1 / denominator))
    matrix = _matrix(rows, features, _modes(counts))
    mean = matrix.mean(axis=0)
    precision = np.linalg.pinv(np.cov(matrix, rowvar=False))
    surprise = _surprise(matrix, features, log_probs, unseen)
    distance = _mahalanobis(matrix, mean, precision)
    return {"features": list(features), "quantile": quantile,
            "log_probs": log_probs, "unseen_log_prob": unseen,
            "mean": mean.tolist(), "precision": precision.tolist(),
            "surprise_threshold": float(np.quantile(surprise, quantile)),
            "mahalanobis_threshold": float(np.quantile(distance, quantile))}


def score_submission(codes, reference):
    """Return both OOD scores and flags for one complete set of answer codes."""
    features = reference["features"]
    row = np.array([[float(codes[name]) for name in features]])
    surprise = float(_surprise(row, features, reference["log_probs"],
                               reference["unseen_log_prob"])[0])
    distance = float(_mahalanobis(row, np.asarray(reference["mean"]),
                                  np.asarray(reference["precision"]))[0])
    return {"surprise": surprise, "mahalanobis": distance,
            "surprise_ood": surprise > reference["surprise_threshold"],
            "mahalanobis_ood": distance > reference["mahalanobis_threshold"]}
