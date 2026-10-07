"""Categorical input-drift metrics over aggregate per-feature answer-code counts.

Only counts are compared, so live monitoring never needs to retain individual
questionnaire submissions. Reference missing values are excluded from the
reference distribution because live submissions must be complete.
"""

import math

import numpy as np

# Jensen-Shannon distance threshold matches Evidently's default for categorical columns;
# PSI bands are the conventional 0.1 (moderate) and 0.25 (major) shift cut-offs.
JS_THRESHOLD = 0.1
PSI_MODERATE, PSI_MAJOR = 0.1, 0.25
DATASET_DRIFT_SHARE = 0.5
MIN_CURRENT_N = 30
_EPSILON = 1e-4


def count_codes(rows, feature_names):
    """Count observed integer answer codes and missing values per feature."""
    counts = {name: {} for name in feature_names}
    missing = dict.fromkeys(feature_names, 0)
    for row in rows:
        for name in feature_names:
            value = row.get(name)
            if value is None or value == "" or (isinstance(value, float) and math.isnan(value)):
                missing[name] += 1
                continue
            code = float(value)
            if not code.is_integer():
                raise ValueError(f"{name} contains a non-integer answer code")
            key = str(int(code))
            counts[name][key] = counts[name].get(key, 0) + 1
    return counts, missing


def categorical_drift(reference, current):
    """Return Jensen-Shannon distance (base 2) and PSI between two code-count maps."""
    categories = sorted(set(reference) | set(current), key=int)
    ref = np.array([reference.get(key, 0) for key in categories], dtype=float)
    cur = np.array([current.get(key, 0) for key in categories], dtype=float)
    if ref.sum() <= 0 or cur.sum() <= 0:
        raise ValueError("Both distributions need at least one observation")
    p, q = ref / ref.sum(), cur / cur.sum()
    m = (p + q) / 2

    def kl(a, b):
        """Compute base-2 Kullback-Leibler divergence over the support of a."""
        mask = a > 0
        return float(np.sum(a[mask] * np.log2(a[mask] / b[mask])))

    js = math.sqrt(max(0.0, (kl(p, m) + kl(q, m)) / 2))
    # Smoothing keeps PSI finite when a category is absent from one distribution.
    ps, qs = np.clip(p, _EPSILON, None), np.clip(q, _EPSILON, None)
    psi = float(np.sum((qs - ps) * np.log(qs / ps)))
    return {"js_distance": js, "psi": psi}


def drift_report(reference_counts, current_counts, current_n, *, min_n=MIN_CURRENT_N,
                 threshold=JS_THRESHOLD, dataset_share=DATASET_DRIFT_SHARE):
    """Compare current inputs with the reference; suppress per-feature output below min_n."""
    if current_n < min_n:
        return {"status": "insufficient_data", "n": current_n, "min_n": min_n}
    features = []
    for name, reference in reference_counts.items():
        current = current_counts.get(name, {})
        if not sum(current.values()):
            continue
        scores = categorical_drift(reference, current)
        psi = scores["psi"]
        features.append({"feature": name, **scores,
                         "drifted": scores["js_distance"] >= threshold,
                         "psi_band": ("major" if psi >= PSI_MAJOR else
                                      "moderate" if psi >= PSI_MODERATE else "stable")})
    features.sort(key=lambda item: item["js_distance"], reverse=True)
    drifted = sum(item["drifted"] for item in features)
    share = drifted / len(features) if features else 0.0
    return {"status": "drift" if share >= dataset_share else "stable", "n": current_n,
            "min_n": min_n, "method": "jensen_shannon_distance", "threshold": threshold,
            "dataset_drift_share": dataset_share, "drifted_features": drifted,
            "evaluated_features": len(features), "drift_share": share, "features": features}
