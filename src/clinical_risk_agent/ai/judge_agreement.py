"""Chance-adjusted agreement for explicitly reviewed ordinal quality labels."""

LABELS = ("bad", "acceptable", "good")


def cohen_kappa(left, right, *, weights=None):
    """Compute unweighted, linear or quadratic Cohen kappa with fixed label order."""
    if weights not in {None, "linear", "quadratic"}:
        raise ValueError("Unknown kappa weighting")
    if len(left) != len(right) or any(x not in LABELS for x in [*left, *right]):
        raise ValueError("Paired valid labels are required")
    n = len(left)
    matrix = [[0 for _ in LABELS] for _ in LABELS]
    for a, b in zip(left, right):
        matrix[LABELS.index(a)][LABELS.index(b)] += 1
    if not n:
        return {"n": 0, "kappa": None, "agreement": None, "confusion_matrix": matrix}
    rows = [sum(row) for row in matrix]
    columns = [sum(row[j] for row in matrix) for j in range(3)]
    observed = expected = 0.0
    for i in range(3):
        for j in range(3):
            distance = (i != j) if weights is None else abs(i - j) / 2
            if weights == "quadratic":
                distance **= 2
            observed += distance * matrix[i][j] / n
            expected += distance * rows[i] * columns[j] / n ** 2
    return {"n": n, "kappa": 1 - observed / expected if expected > 0 else None,
            "agreement": sum(matrix[i][i] for i in range(3)) / n,
            "confusion_matrix": matrix}


def agreement_report(cases):
    """Compare only confirmed human labels with actual judge and author labels by split."""
    result = {"label_order": list(LABELS), "status": "pending_human_review", "splits": {}}
    for split in ("calibration", "validation", "holdout"):
        reviewed = [c for c in cases if c["split"] == split
                    and c.get("human_reviewed") is True and c.get("human_annotation") in LABELS]
        comparisons = {}
        for field in ("judge_annotation", "assistant_annotation"):
            paired = [c for c in reviewed if c.get(field) in LABELS]
            left = [c["human_annotation"] for c in paired]
            right = [c[field] for c in paired]
            comparisons[field] = {"unweighted": cohen_kappa(left, right),
                                  "linear": cohen_kappa(left, right, weights="linear"),
                                  "quadratic": cohen_kappa(left, right, weights="quadratic")}
        result["splits"][split] = {"reviewed": len(reviewed), "comparisons": comparisons}
    return result
