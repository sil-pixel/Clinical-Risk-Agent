"""Inference-only feature schema and preprocessing from the Thesis runtime."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass(frozen=True, slots=True)
class FeatureSchema:
    modality_names: tuple[str, ...]
    feature_names: tuple[tuple[str, ...], ...]
    medians: tuple[tuple[float, ...], ...]
    means: tuple[tuple[float, ...], ...]
    scales: tuple[tuple[float, ...], ...]

    def __post_init__(self) -> None:
        group_count = len(self.modality_names)
        fields = (self.feature_names, self.medians, self.means, self.scales)
        if any(len(field) != group_count for field in fields):
            raise ValueError("Feature schema group counts do not match")
        for index, names in enumerate(self.feature_names):
            size = len(names)
            if size == 0:
                raise ValueError("Feature groups must not be empty")
            if any(len(field[index]) != size for field in fields[1:]):
                raise ValueError(f"Feature schema size mismatch in group {index}")
            if any(scale <= 0 for scale in self.scales[index]):
                raise ValueError("Feature scales must be positive")
            numeric_values = self.medians[index] + self.means[index] + self.scales[index]
            if not np.isfinite(np.asarray(numeric_values, dtype=float)).all():
                raise ValueError("Feature preprocessing values must be finite")
        flat_names = self.flat_feature_names
        if len(flat_names) != len(set(flat_names)):
            raise ValueError("Feature names must be unique")

    @property
    def sizes(self) -> tuple[int, ...]:
        return tuple(len(names) for names in self.feature_names)

    @property
    def flat_feature_names(self) -> tuple[str, ...]:
        return tuple(name for group in self.feature_names for name in group)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "FeatureSchema":
        return cls(
            modality_names=tuple(str(item) for item in value["modality_names"]),
            feature_names=tuple(
                tuple(map(str, group)) for group in value["feature_names"]
            ),
            medians=tuple(tuple(map(float, group)) for group in value["medians"]),
            means=tuple(tuple(map(float, group)) for group in value["means"]),
            scales=tuple(tuple(map(float, group)) for group in value["scales"]),
        )


def transform_records(
    records: Sequence[Mapping[str, float]], schema: FeatureSchema
) -> list[np.ndarray]:
    """Median-impute NaN and standardize records using training-fitted values."""

    if not records:
        raise ValueError("At least one record is required")
    required = set(schema.flat_feature_names)
    for row, record in enumerate(records):
        missing = sorted(required - set(record))
        if missing:
            raise ValueError(f"Record {row} is missing required features: {missing}")
        unknown = sorted(set(record) - required)
        if unknown:
            raise ValueError(f"Record {row} contains unknown features: {unknown}")
    result: list[np.ndarray] = []
    for names, medians, means, scales in zip(
        schema.feature_names,
        schema.medians,
        schema.means,
        schema.scales,
        strict=True,
    ):
        try:
            values = np.asarray(
                [[record[name] for name in names] for record in records],
                dtype=np.float32,
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("Features must be numeric values") from exc
        values = np.where(np.isnan(values), np.asarray(medians, dtype=np.float32), values)
        values = (values - np.asarray(means, dtype=np.float32)) / np.asarray(
            scales, dtype=np.float32
        )
        if not np.isfinite(values).all():
            raise ValueError("Features must be finite numeric values")
        result.append(values.astype(np.float32, copy=False))
    return result
