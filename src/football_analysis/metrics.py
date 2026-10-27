"""Evaluation metrics for expectation estimates."""

from collections.abc import Iterable
import math


def _paired_values(
    actual: Iterable[float],
    predicted: Iterable[float],
) -> list[tuple[float, float]]:
    actual_values = list(actual)
    predicted_values = list(predicted)
    if not actual_values:
        raise ValueError("At least one observation is required")
    if len(actual_values) != len(predicted_values):
        raise ValueError("Metric inputs must have equal lengths")
    pairs = list(zip(actual_values, predicted_values))
    if any(not math.isfinite(a) or not math.isfinite(p) for a, p in pairs):
        raise ValueError("Metric inputs must be finite")
    return pairs


def mean_absolute_error(
    actual: Iterable[float],
    predicted: Iterable[float],
) -> float:
    """Return the mean absolute difference between two sequences."""
    pairs = _paired_values(actual, predicted)
    return sum(abs(a - p) for a, p in pairs) / len(pairs)


def root_mean_squared_error(
    actual: Iterable[float],
    predicted: Iterable[float],
) -> float:
    """Return the root mean squared difference between two sequences."""
    pairs = _paired_values(actual, predicted)
    return math.sqrt(sum((a - p) ** 2 for a, p in pairs) / len(pairs))
