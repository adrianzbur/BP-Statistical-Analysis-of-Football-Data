import pytest

from football_analysis.metrics import mean_absolute_error, root_mean_squared_error


def test_mean_absolute_error() -> None:
    assert mean_absolute_error([0.0, 1.0], [0.5, 0.5]) == pytest.approx(0.5)


def test_root_mean_squared_error() -> None:
    assert root_mean_squared_error([0.0, 1.0], [0.5, 0.5]) == pytest.approx(0.5)


def test_metrics_reject_empty_inputs() -> None:
    with pytest.raises(ValueError):
        mean_absolute_error([], [])
