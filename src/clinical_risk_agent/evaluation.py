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
