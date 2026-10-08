"""Categorical input-drift metrics over aggregate per-feature answer-code counts.

Only counts are compared, so live monitoring never needs to retain individual
questionnaire submissions. Reference missing values are excluded from the
reference distribution because live submissions must be complete.
"""

import math

import numpy as np

# PSI bands are the conventional 0.1 (moderate) and 0.25 (major) shift cut-offs; they are
# reported as effect sizes only. Significance comes from sample-size-aware tests below.
PSI_MODERATE, PSI_MAJOR = 0.1, 0.25
Z_THRESHOLD = 3.0          # two-sided; about 0.3% false alarms per look under no drift
FDR = 0.05                 # Benjamini-Hochberg rate across per-question tests
NULL_SIMULATIONS = 4000    # Monte Carlo draws per question; minimum p-value 1/4001
FEATURE_MIN_N = 10         # privacy: hide per-question results until 10 submissions
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


def _js_rows(p, q):
    """Vectorized base-2 Jensen-Shannon distance between p and each row of q."""
    m = (p + q) / 2

    def kl(a, b):
        """Row-wise KL divergence, treating 0 * log(0) as 0."""
        with np.errstate(divide="ignore", invalid="ignore"):
            terms = np.where(a > 0, a * np.log2(a / b), 0.0)
        return terms.sum(axis=-1)

    return np.sqrt(np.clip((kl(p, m) + kl(q, m)) / 2, 0, None))


def feature_p_value(reference, current, n, rng, simulations=NULL_SIMULATIONS):
    """Monte Carlo p-value of the observed JS distance for n draws from the reference."""
    categories = sorted(set(reference) | set(current), key=int)
    p = np.array([reference.get(key, 0) for key in categories], dtype=float)
    p /= p.sum()
    observed = categorical_drift(reference, current)["js_distance"]
    null = _js_rows(p, rng.multinomial(n, p, size=simulations) / n)
    return float((1 + np.sum(null >= observed - 1e-12)) / (simulations + 1))


def benjamini_hochberg(p_values, rate=FDR):
    """Return which hypotheses are discoveries at the given false-discovery rate."""
    order = np.argsort(p_values)
    m = len(p_values)
    passed = [p_values[i] <= (rank + 1) / m * rate for rank, i in enumerate(order)]
    cutoff = max((rank for rank, ok in enumerate(passed) if ok), default=-1)
    flags = np.zeros(m, dtype=bool)
    flags[order[:cutoff + 1]] = True
    return flags


def running_drift(n, surprise_sum, reference_mean, reference_std, threshold=Z_THRESHOLD):
    """z-score of the live mean answer surprise against the reference, valid from n = 1."""
    mean = surprise_sum / n
    z = (mean - reference_mean) / (reference_std / math.sqrt(n))
    return {"mean_surprise": mean, "reference_mean": reference_mean, "z": z,
            "threshold": threshold, "drifted": abs(z) >= threshold}


def drift_report(reference_counts, current_counts, current_n, *, surprise_sum=None,
                 surprise_mean=None, surprise_std=None, feature_min_n=FEATURE_MIN_N,
                 rate=FDR, seed=0):
    """Running drift score from the first submission; per-question tests from feature_min_n."""
    if current_n == 0:
        return {"status": "no_data", "n": 0, "feature_min_n": feature_min_n}
    report = {"n": current_n, "feature_min_n": feature_min_n, "running": None}
    if surprise_sum is not None and surprise_mean is not None and surprise_std:
        report["running"] = running_drift(current_n, surprise_sum, surprise_mean, surprise_std)
    drifted_any = bool(report["running"] and report["running"]["drifted"])
    if current_n >= feature_min_n:
        rng = np.random.default_rng(seed)
        features = []
        for name, reference in reference_counts.items():
            current = current_counts.get(name, {})
            if not sum(current.values()):
                continue
            scores = categorical_drift(reference, current)
            psi = scores["psi"]
            features.append({"feature": name, **scores,
                             "p_value": feature_p_value(reference, current, current_n, rng),
                             "psi_band": ("major" if psi >= PSI_MAJOR else
                                          "moderate" if psi >= PSI_MODERATE else "stable")})
        flags = benjamini_hochberg([item["p_value"] for item in features], rate)
        for item, flag in zip(features, flags, strict=True):
            item["drifted"] = bool(flag)
        features.sort(key=lambda item: (item["p_value"], -item["js_distance"]))
        report.update(features=features, drifted_features=int(flags.sum()),
                      evaluated_features=len(features), fdr=rate)
        drifted_any = drifted_any or bool(flags.any())
    report["status"] = "drift" if drifted_any else "stable"
    return report
