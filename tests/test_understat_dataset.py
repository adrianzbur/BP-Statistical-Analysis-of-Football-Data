import pandas as pd
import pytest

from football_analysis.forecast import forecast_points, summarize_forecasts
from football_analysis.understat_dataset import (
    aggregate_seasons, complete_seasons, pair_team_matches, validate_team_matches,
)


def team_rows():
    rows = []
    # A beats B 2-1; B then beats A 3-1. Each source match has two sides.
    for date, home, away, hg, ag, hx, ax in (
        ("2020-08-01", "A", "B", 2, 1, 1.5, 1.0),
        ("2020-08-08", "B", "A", 3, 1, 2.5, 0.8),
    ):
        for team, venue, gf, ga, xf, xa in (
            (home, "h", hg, ag, hx, ax), (away, "a", ag, hg, ax, hx),
        ):
            win, draw, loss = int(gf > ga), int(gf == ga), int(gf < ga)
            rows.append(dict(id=1 if team == "A" else 2, league="TEST", season="2020",
                             club_name=team, date=date, home_away=venue, scored=gf, missed=ga,
                             xG=xf, xGA=xa, wins=win, draws=draw, loses=loss,
                             result="w" if win else "l" if loss else "d", pts=3*win+draw))
    return pd.DataFrame(rows)


def test_pairing_and_aggregation_do_not_double_count():
    data = validate_team_matches(team_rows())
    paired = pair_team_matches(data)
    totals, audit = complete_seasons(data, paired, "TEST", 2)
    assert len(paired) == 2
    assert audit.included.all()
    a = totals.set_index("team").loc["A"]
    assert a.played == 2 and a.points == 3
    assert a.goals_for == 3 and a.goals_against == 4
    assert a.xg_for == pytest.approx(2.3)
    assert a.xg_against == pytest.approx(3.5)


@pytest.mark.parametrize("change", ["duplicate", "result", "points", "infinity", "date", "venue"])
def test_invalid_match_rows_rejected(change):
    data = team_rows()
    if change == "duplicate":
        data = pd.concat([data, data.iloc[:1]])
    elif change == "result":
        data.loc[0, "result"] = "l"
    elif change == "points":
        data.loc[0, "pts"] = 0
    elif change == "infinity":
        data.loc[0, "xG"] = float("inf")
    elif change == "date":
        data.loc[0, "date"] = None
    else:
        data.loc[0, "home_away"] = "?"
    with pytest.raises(ValueError):
        validate_team_matches(data)


def test_unmatched_and_ambiguous_pairs_rejected():
    data = validate_team_matches(team_rows())
    with pytest.raises(ValueError, match="Unmatched"):
        pair_team_matches(data.iloc[1:])
    extra = data.loc[(data.club_name == "A") & (data.home_away == "h")].copy()
    extra["club_name"] = "C"
    extra["id"] = 3
    with pytest.raises(ValueError, match="Ambiguous"):
        pair_team_matches(pd.concat([data, extra]))


def test_partial_season_is_excluded_with_reason():
    complete = team_rows()
    partial = complete.iloc[:2].copy()
    partial["season"] = "2021"
    partial["date"] = "2021-08-01"
    data = validate_team_matches(pd.concat([complete, partial]))
    totals, audit = complete_seasons(data, pair_team_matches(data), "TEST", 2)
    assert set(totals.season) == {"2020"}
    assert not audit.set_index("season").loc["2021", "included"]


def test_forecast_values_and_metrics_have_independent_expected_answer():
    data = validate_team_matches(team_rows())
    forecast = forecast_points(data, aggregate_seasons(data), cutoff=1).set_index("team")
    assert forecast.loc["A", "predicted_goals"] == pytest.approx(3 + 3*4/5)
    assert forecast.loc["B", "predicted_goals"] == pytest.approx(3/5)
    assert forecast.loc["A", "predicted_xg"] == pytest.approx(3 + 3*2.25/3.25)
    assert forecast.loc["A", "predicted_ppg"] == 6
    metrics = summarize_forecasts(forecast.reset_index())
    overall = metrics[metrics.season == "ALL"].set_index("model")
    assert overall.loc["goals", "mae"] == pytest.approx(2.4)
    assert overall.loc["goals", "bias"] == pytest.approx(0)
    assert overall.loc["ppg", "mae"] == 3


def test_forecast_does_not_leak_future_scores_xg_or_final_points():
    data = validate_team_matches(team_rows())
    before = forecast_points(data, aggregate_seasons(data), cutoff=1)
    changed = team_rows()
    # Reverse the future result, and change future xG, while preserving mirrors.
    changed.loc[2, ["scored", "missed", "xG", "xGA", "result", "wins", "loses", "pts"]] = [0, 4, .2, 4.0, "l", 0, 1, 0]
    changed.loc[3, ["scored", "missed", "xG", "xGA", "result", "wins", "loses", "pts"]] = [4, 0, 4.0, .2, "w", 1, 0, 3]
    changed = validate_team_matches(changed.sample(frac=1, random_state=42))
    after = forecast_points(changed, aggregate_seasons(changed), cutoff=1)
    columns = [c for c in before if c.startswith(("predicted_", "observed_"))] + ["cutoff_date"]
    pd.testing.assert_frame_equal(before[columns], after[columns])
    assert not before.actual_points.equals(after.actual_points)


def test_cutoff_at_end_of_season_is_rejected():
    data = validate_team_matches(team_rows())
    with pytest.raises(ValueError):
        forecast_points(data, aggregate_seasons(data), cutoff=2)


def test_full_counts_with_wrong_home_away_schedule_are_rejected():
    data = team_rows()
    data.loc[2, "home_away"] = "a"
    data.loc[3, "home_away"] = "h"
    data = validate_team_matches(data)
    with pytest.raises(ValueError, match="No complete seasons"):
        complete_seasons(data, pair_team_matches(data), "TEST", 2)
