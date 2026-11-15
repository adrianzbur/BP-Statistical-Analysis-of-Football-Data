"""Unit and integration tests for historical draw-adjusted forecasts."""

import pandas as pd
import pytest

from football_analysis.experiment_02 import (
    corrected_points, historical_draw_rate, run_experiment, summarize_predictions,
)
from football_analysis.experiment_02_reporting import compare_models
from football_analysis.understat_dataset import (
    complete_seasons, pair_team_matches, validate_team_matches,
)


def test_correction_changes_only_points_not_yet_earned():
    assert corrected_points(20, 50, 0.25) == pytest.approx(47.5)
    assert corrected_points(20, 50, 0) == pytest.approx(50)
    assert corrected_points(20, 50, 1) == pytest.approx(40)
    assert corrected_points(20, 20, 0.5) == pytest.approx(20)


@pytest.mark.parametrize("value", [-0.1, 1.1, float("nan"), float("inf")])
def test_invalid_draw_rate_is_rejected(value):
    with pytest.raises(ValueError, match="draw rate"):
        corrected_points(20, 50, value)


def test_adjustment_accepts_series():
    observed = pd.Series([10, 15])
    original = pd.Series([40, 45])
    result = corrected_points(observed, original, 0.2)
    pd.testing.assert_series_equal(result, pd.Series([38.0, 43.0]))


def test_historical_draw_rate_excludes_target_and_future_seasons():
    totals = pd.DataFrame({
        "season": ["2014", "2015", "2016"],
        "played": [20, 40, 40],
        "draws": [10, 10, 40],
    })
    assert historical_draw_rate(totals, "2015") == pytest.approx(0.5)
    assert historical_draw_rate(totals, "2016") == pytest.approx(20 / 60)
    with pytest.raises(ValueError, match="No completed season"):
        historical_draw_rate(totals, "2014")


def _toy_games(*, change_future: bool = False) -> pd.DataFrame:
    """Two complete seasons, two mirrored fixtures per season."""
    fixtures = [
        ("2019", "2019-08-01", "A", "B", 1, 1, 1.2, 1.1),
        ("2019", "2019-08-08", "B", "A", 0, 2, 0.5, 1.8),
        ("2020", "2020-08-01", "A", "B", 2, 1, 1.8, 0.9),
        ("2020", "2020-08-08", "B", "A", 1, 0, 1.1, 0.7),
    ]
    if change_future:
        fixtures[-1] = ("2020", "2020-08-08", "B", "A", 0, 4, 0.2, 3.5)
    rows = []
    for season, date, home, away, hg, ag, hx, ax in fixtures:
        for team, venue, gf, ga, xf, xa in (
            (home, "h", hg, ag, hx, ax), (away, "a", ag, hg, ax, hx),
        ):
            w, d, l = int(gf > ga), int(gf == ga), int(gf < ga)
            rows.append({
                "id": 1 if team == "A" else 2, "league": "TEST",
                "season": season, "club_name": team, "date": date,
                "home_away": venue, "scored": gf, "missed": ga,
                "xG": xf, "xGA": xa, "wins": w, "draws": d, "loses": l,
                "result": "w" if w else "d" if d else "l", "pts": 3*w + d,
            })
    return validate_team_matches(pd.DataFrame(rows))


def test_end_to_end_run_matches_independent_expected_values():
    games = _toy_games()
    totals, audit = complete_seasons(games, pair_team_matches(games), "TEST", 2)
    assert audit.included.all()
    predictions, metrics, calibration = run_experiment(games, totals, cutoff=1)
    assert set(predictions["season"]) == {"2020"}
    assert len(predictions) == 2
    assert calibration.loc[0, "historical_draw_rate"] == pytest.approx(0.5)
    assert calibration.loc[0, "training_matches"] == 2
    assert calibration.loc[0, "training_draws"] == 1
    a = predictions.set_index("team").loc["A"]
    assert a["observed_points"] == 3
    assert a["predicted_goals"] == pytest.approx(3 + 3 * 4 / 5)
    assert a["predicted_goals_draw"] == pytest.approx(3 + 2.5 * 4 / 5)
    assert a["predicted_xg_draw"] == pytest.approx(3 + 2.5 * 1.8**2 / (1.8**2 + .9**2))
    assert set(metrics["model"]) == {
        "goals_original", "xg_original", "goals_draw", "xg_draw", "ppg"
    }
    assert metrics.loc[metrics["season"] == "ALL", "teams"].eq(2).all()


def test_changing_test_season_future_scores_does_not_change_forecasts():
    before_games = _toy_games()
    after_games = _toy_games(change_future=True)
    before_totals, _ = complete_seasons(before_games, pair_team_matches(before_games), "TEST", 2)
    after_totals, _ = complete_seasons(after_games, pair_team_matches(after_games), "TEST", 2)
    before, _, first_cal = run_experiment(before_games, before_totals, cutoff=1)
    after, _, last_cal = run_experiment(after_games, after_totals, cutoff=1)
    columns = [c for c in before if c.startswith(("predicted_", "observed_"))]
    columns.extend(["historical_draw_rate", "points_per_match_factor", "cutoff_date"])
    pd.testing.assert_frame_equal(before[columns], after[columns])
    pd.testing.assert_frame_equal(first_cal, last_cal)
    assert not before["actual_points"].equals(after["actual_points"])


def test_two_seasons_are_required():
    games = _toy_games()
    totals, _ = complete_seasons(games, pair_team_matches(games), "TEST", 2)
    with pytest.raises(ValueError, match="At least two"):
        run_experiment(games, totals.loc[totals.season == "2020"], cutoff=1)


def test_metrics_report_zero_error_on_exact_predictions():
    predictions = pd.DataFrame({
        "season": ["2020"], "actual_points": [20],
        "predicted_goals": [20], "predicted_xg": [20],
        "predicted_goals_draw": [20], "predicted_xg_draw": [20],
        "predicted_ppg": [20],
    })
    metrics = summarize_predictions(predictions)
    assert metrics["mae"].eq(0).all()
    assert metrics["rmse"].eq(0).all()
    assert metrics["bias"].eq(0).all()


def test_future_draw_in_target_season_does_not_change_calibration():
    before_games = _toy_games()
    changed = before_games.copy()
    future = changed.season.eq("2020") & changed.date.eq(pd.Timestamp("2020-08-08"))
    changed.loc[future, ["scored", "missed", "wins", "draws", "loses", "pts"]] = [1, 1, 0, 1, 0, 1]
    changed.loc[future, "result"] = "d"
    changed = validate_team_matches(changed)
    before_totals, _ = complete_seasons(before_games, pair_team_matches(before_games), "TEST", 2)
    after_totals, _ = complete_seasons(changed, pair_team_matches(changed), "TEST", 2)
    before, _, first_cal = run_experiment(before_games, before_totals, cutoff=1)
    after, _, last_cal = run_experiment(changed, after_totals, cutoff=1)
    prediction_columns = [c for c in before if c.startswith("predicted_")]
    pd.testing.assert_frame_equal(before[prediction_columns], after[prediction_columns])
    pd.testing.assert_frame_equal(first_cal, last_cal)
    assert not before.actual_points.equals(after.actual_points)


def test_adding_later_season_does_not_change_earlier_predictions():
    games = _toy_games()
    totals, _ = complete_seasons(games, pair_team_matches(games), "TEST", 2)
    before, _, original_calibration = run_experiment(games, totals, cutoff=1)
    future = games.loc[games.season == "2020"].copy()
    future["season"] = "2021"
    future["date"] += pd.Timedelta(days=365)
    future[["scored", "missed", "wins", "draws", "loses", "pts"]] = [1, 1, 0, 1, 0, 1]
    future["result"] = "d"
    extended = validate_team_matches(pd.concat([games, future], ignore_index=True).sample(frac=1, random_state=7))
    extended_totals, _ = complete_seasons(extended, pair_team_matches(extended), "TEST", 2)
    after, _, calibration = run_experiment(extended, extended_totals, cutoff=1)
    pd.testing.assert_frame_equal(before, after.loc[after.season == "2020"].reset_index(drop=True))
    pd.testing.assert_frame_equal(original_calibration, calibration.loc[calibration.season == "2020"].reset_index(drop=True))
    assert calibration.set_index("season").loc["2021", "historical_draw_rate"] == pytest.approx(.25)


def test_historical_match_after_forecast_cutoff_is_rejected():
    games = _toy_games()
    games.loc[games.season == "2019", "date"] += pd.Timedelta(days=400)
    totals, _ = complete_seasons(games, pair_team_matches(games), "TEST", 2)
    with pytest.raises(ValueError, match="before every forecast cutoff"):
        run_experiment(games, totals, cutoff=1)


def test_mixed_leagues_are_rejected():
    games = _toy_games()
    totals, _ = complete_seasons(games, pair_team_matches(games), "TEST", 2)
    totals.loc[0, "league"] = "OTHER"
    with pytest.raises(ValueError, match="exactly one league"):
        run_experiment(games, totals, cutoff=1)


def test_non_year_season_labels_are_rejected():
    games = _toy_games()
    totals, _ = complete_seasons(games, pair_team_matches(games), "TEST", 2)
    totals.loc[totals.season == "2019", "season"] = "2019-20"
    with pytest.raises(ValueError, match="four-digit"):
        run_experiment(games, totals, cutoff=1)


def test_model_comparison_sign_and_percent_reduction():
    # Two teams with known errors. Candidate MAE=1, original MAE=3, PPG MAE=2.
    rows = pd.DataFrame({
        "season": ["2020", "2020"], "actual_points": [10, 20],
        "predicted_goals": [12, 24], "predicted_xg": [12, 24],
        "predicted_goals_draw": [11, 19], "predicted_xg_draw": [11, 19],
        "predicted_ppg": [12, 18],
    })
    comparison = compare_models(summarize_predictions(rows))
    overall = comparison.loc[comparison.season == "ALL"].set_index(["candidate", "reference"])
    against_original = overall.loc[("xg_draw", "xg_original")]
    assert against_original.delta_mae == pytest.approx(-2)
    assert against_original.mae_reduction_percent == pytest.approx(100*2/3)
    assert against_original.delta_rmse == pytest.approx(1 - 10**.5)
    assert overall.loc[("xg_draw", "ppg"), "delta_mae"] == pytest.approx(-1)


def test_comparison_handles_zero_reference_without_division_by_zero():
    metrics = pd.DataFrame({
        "season": ["ALL"]*5, "teams": [2]*5,
        "model": ["goals_original", "xg_original", "goals_draw", "xg_draw", "ppg"],
        "mae": [0.0]*5, "rmse": [0.0]*5,
    })
    comparison = compare_models(metrics)
    assert comparison.delta_mae.eq(0).all()
    assert comparison.mae_reduction_percent.isna().all()


def test_comparison_rejects_different_sample_sizes():
    metrics = pd.DataFrame({
        "season": ["ALL"]*5, "teams": [20, 20, 20, 20, 18],
        "model": ["goals_original", "xg_original", "goals_draw", "xg_draw", "ppg"],
        "mae": [1.0]*5, "rmse": [1.0]*5,
    })
    with pytest.raises(ValueError, match="equal observation counts"):
        compare_models(metrics)
