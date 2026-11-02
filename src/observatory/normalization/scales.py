"""Scale-aware normalization. Each O*NET scale is normalized by its own published range; mixing is refused."""

from __future__ import annotations

from dataclasses import dataclass


class ScaleMismatchError(ValueError):
    pass


@dataclass(frozen=True)
class Scale:
    scale_id: str
    name: str
    minimum: float
    maximum: float

    def normalize(self, value: float) -> float:
        if value < self.minimum - 1e-9 or value > self.maximum + 1e-9:
            raise ValueError(f"{value} outside scale {self.scale_id} [{self.minimum}, {self.maximum}]")
        return (value - self.minimum) / (self.maximum - self.minimum)


class ScaleRegistry:
    def __init__(self, scales: dict[str, Scale]):
        self._scales = scales

    @classmethod
    def from_rows(cls, rows: list[dict[str, str]]) -> ScaleRegistry:
        return cls(
            {
                r["Scale ID"]: Scale(r["Scale ID"], r["Scale Name"], float(r["Minimum"]), float(r["Maximum"]))
                for r in rows
            }
        )

    def get(self, scale_id: str) -> Scale:
        if scale_id not in self._scales:
            raise ScaleMismatchError(f"unknown scale {scale_id!r}")
        return self._scales[scale_id]

    def normalize(self, scale_id: str, value: float) -> float:
        return self.get(scale_id).normalize(value)

    def __contains__(self, scale_id: str) -> bool:
        return scale_id in self._scales


def mean_normalized(values: list[tuple[str, float]], registry: ScaleRegistry) -> float:
    """Average of values that are each normalized by their own scale first (never raw)."""
    if not values:
        raise ValueError("no values")
    return sum(registry.normalize(s, v) for s, v in values) / len(values)


def expected_frequency(distribution: dict[str, float], n_categories: int = 7) -> float:
    """O*NET FT is a percent distribution over categories 1..n; returns E[category] normalized to 0-1."""
    total = sum(distribution.values())
    if total <= 0:
        raise ValueError("empty frequency distribution")
    expected = sum(int(c) * p for c, p in distribution.items()) / total
    return (expected - 1) / (n_categories - 1)
