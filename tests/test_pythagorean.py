import pytest

from football_analysis.pythagorean import pythagorean_expectation


def test_pythagorean_expectation_is_symmetric() -> None:
    assert pythagorean_expectation(2, 2) == pytest.approx(0.5)


def test_pythagorean_expectation_increases_with_more_goals_for() -> None:
    assert pythagorean_expectation(3, 1) == pytest.approx(0.9)


def test_pythagorean_expectation_rejects_zero_total() -> None:
    with pytest.raises(ValueError):
        pythagorean_expectation(0, 0)
