"""Out-of-distribution scoring of questionnaire answer codes against aggregate reference statistics.

Two per-submission scores are compared with thresholds taken from the reference rows:
average answer surprise (negative log-likelihood under independent, Laplace-smoothed
reference marginals) and squared Mahalanobis distance, which also reflects correlations.
Only the reference statistics are stored; live submissions are scored and discarded.
"""

import numpy as np

OOD_QUANTILE = 0.99
OOD_MIN_N = 30  # the live OOD rate is a share of submissions; hide it until this many


def _matrix(rows, features, counts, rng):
    """Stack answer codes, drawing each missing value from that feature's observed codes.

    Live submissions are always complete. Filling gaps with the modal code would make
    reference rows look more typical than real complete answers and bias every threshold.
    """
    marginals = {}
    for name in features:
        codes = sorted(counts[name], key=int)
        weights = np.array([counts[name][code] for code in codes], dtype=float)
        marginals[name] = (np.array([int(code) for code in codes]), weights / weights.sum())
    matrix = np.empty((len(rows), len(features)))
    for i, row in enumerate(rows):
        for j, name in enumerate(features):
            value = row.get(name)
            missing = value is None or value == "" or np.isnan(float(value))
            if missing:
                codes, probabilities = marginals[name]
                matrix[i, j] = rng.choice(codes, p=probabilities)
            else:
                matrix[i, j] = round(float(value))
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


def build_ood_reference(rows, features, counts, quantile=OOD_QUANTILE, seed=0):
    """Fit aggregate OOD statistics, thresholds and surprise moments from reference rows."""
    log_probs, unseen = {}, {}
    for name in features:
        values = counts[name]
        denominator = sum(values.values()) + len(values) + 1
        log_probs[name] = {code: float(np.log((n + 1) / denominator))
                           for code, n in values.items()}
        unseen[name] = float(np.log(1 / denominator))
    matrix = _matrix(rows, features, counts, np.random.default_rng(seed))
    mean = matrix.mean(axis=0)
    precision = np.linalg.pinv(np.atleast_2d(np.cov(matrix, rowvar=False)))
    surprise = _surprise(matrix, features, log_probs, unseen)
    distance = _mahalanobis(matrix, mean, precision)
    return {"features": list(features), "quantile": quantile,
            "log_probs": log_probs, "unseen_log_prob": unseen,
            "mean": mean.tolist(), "precision": precision.tolist(),
            "surprise_threshold": float(np.quantile(surprise, quantile)),
            # Moments of per-submission surprise, for the running drift z-score.
            "surprise_mean": float(surprise.mean()), "surprise_std": float(surprise.std(ddof=1)),
            "mahalanobis_threshold": float(np.quantile(distance, quantile))}


def score_rows(rows, reference, counts, seed=0):
    """Answer surprise for a batch of rows; gaps are drawn from the reference marginals."""
    features = reference["features"]
    matrix = _matrix(rows, features, counts, np.random.default_rng(seed))
    return _surprise(matrix, features, reference["log_probs"], reference["unseen_log_prob"])


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
