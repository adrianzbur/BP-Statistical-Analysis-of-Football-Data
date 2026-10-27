"""Pythagorean expectation calculations."""

import math


def pythagorean_expectation(
    goals_for: float,
    goals_against: float,
    exponent: float = 2.0,
) -> float:
    """Calculate expected win share from goals scored and conceded."""
    if goals_for < 0 or goals_against < 0:
        raise ValueError("Goal totals must be non-negative")
    if exponent <= 0 or not math.isfinite(exponent):
        raise ValueError("Exponent must be a positive finite number")
    if goals_for == 0 and goals_against == 0:
        raise ValueError("At least one goal total must be positive")

    scored = goals_for**exponent
    conceded = goals_against**exponent
    return scored / (scored + conceded)
