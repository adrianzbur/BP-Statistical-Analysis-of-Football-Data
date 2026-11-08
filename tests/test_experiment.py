import pandas as pd
import pytest

from football_analysis.experiment import evaluate, prepare_totals
from football_analysis.pythagorean import pythagorean_expectation


def fixture_totals():
    # Two teams draw both fixtures: two real points each, not three.
    return pd.DataFrame([
        dict(league="TEST", year="2020", team=t, played=2, wins=0, draws=2,
             loses=0, scored=2, missed=2, xG=1.5, xGA=1.5, pts=2)
        for t in ("A", "B")])


def test_draw_bias_is_visible_and_models_use_identical_mapping():
    data = prepare_totals(fixture_totals(), "TEST", ["2020"], 2)
    predictions, metrics = evaluate(data)
    assert predictions.predicted_goals.tolist() == [3, 3]
    assert predictions.predicted_xg.tolist() == [3, 3]
    assert metrics.mae.eq(1).all()
    assert metrics.bias.eq(1).all()


@pytest.mark.parametrize("change", ["duplicate", "missing_team", "partial", "nan", "points", "averages"])
def test_invalid_inputs_are_rejected(change):
    data = fixture_totals()
    if change == "duplicate":
        data = pd.concat([data, data.iloc[:1]])
    elif change == "missing_team":
        data = data.iloc[:1]
    elif change == "partial":
        data.loc[0, "played"] = 1
    elif change == "nan":
        data.loc[0, "xG"] = float("nan")
    elif change == "points":
        data.loc[0, "pts"] = 5
    else:
        data["scored"] = 0.5
    with pytest.raises(ValueError):
        prepare_totals(data, "TEST", ["2020"], 2)


@pytest.mark.parametrize("value", [float("nan"), float("inf")])
def test_nonfinite_goals_rejected(value):
    with pytest.raises(ValueError):
        pythagorean_expectation(value, 2)


def test_large_totals_do_not_overflow():
    assert pythagorean_expectation(1e200, 1e200) == pytest.approx(0.5)
