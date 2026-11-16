"""Five-fold season-blocked CV tests (no dataset required)."""

import numpy as np
import pandas as pd
import pytest

from football_analysis.experiment_03 import (
    add_ranks, choose_gamma, make_folds, make_gamma_grid,
    model_predictions, overall_metrics, run_experiment, training_draw_rate,
)
from football_analysis.understat_dataset import (
    validate_team_matches, pair_team_matches, complete_seasons,
)


def toy_seasons(change_test_future=False):
    rows = []
    for year in range(2014, 2024):
        season = str(year)
        # Each team plays twice, one home and one away. Different years vary in scores.
        home_scores = [(2 + (year % 3), 1), (1, 1 + (year % 2))]
        if change_test_future and year == 2022:
            home_scores[1] = (4, 0)
        for j, (hg, ag) in enumerate(home_scores):
            home, away = (("A", "B") if j == 0 else ("B", "A"))
            for club, venue, gf, ga, xgf, xga in (
                (home, "h", hg, ag, float(hg) + .8, float(ag) + .7),
                (away, "a", ag, hg, float(ag) + .7, float(hg) + .8),
            ):
                won, drawn, lost = int(gf > ga), int(gf == ga), int(gf < ga)
                rows.append({
                    "id": 1 if club == "A" else 2, "league": "TEST", "season": season,
                    "club_name": club, "date": f"{year}-{8+j:02d}-05",
                    "home_away": venue, "scored": gf, "missed": ga,
                    "xG": xgf, "xGA": xga, "wins": won, "draws": drawn,
                    "loses": lost, "result": "w" if won else "d" if drawn else "l",
                    "pts": 3*won+drawn,
                })
    matches = validate_team_matches(pd.DataFrame(rows))
    totals, audit = complete_seasons(matches, pair_team_matches(matches), "TEST", 2)
    assert audit.included.all()
    return matches, totals


def test_folds_have_eight_train_and_two_test_without_overlap():
    result = make_folds([str(y) for y in range(2014, 2024)])
    assert len(result) == 5
    assert all(len(train) == 8 and len(test) == 2 and not set(train) & set(test)
               for _, train, test in result)
    assert {y for _, _, test in result for y in test} == {str(y) for y in range(2014, 2024)}
    assert result[-1][2] == ("2022", "2023")
    with pytest.raises(ValueError, match="Exactly 10"):
        make_folds([str(y) for y in range(2015, 2024)])


def test_gamma_grid_contains_expected_reference_exponents():
    grid = make_gamma_grid()
    assert 1.2 in grid and 1.7 in grid and 2.0 in grid
    assert grid[0] == 0.5 and grid[-1] == 3.0
    with pytest.raises(ValueError):
        make_gamma_grid(0, 2.0, .1)


def test_training_draws_not_affected_by_test_totals():
    train = pd.DataFrame({"played": [38, 38], "draws": [10, 20]})
    assert training_draw_rate(train) == pytest.approx(30 / 76)
    with pytest.raises(ValueError):
        training_draw_rate(pd.DataFrame({"played": [0], "draws": [0]}))


def test_model_prediction_known_values():
    x = pd.DataFrame({"observed_points": [15], "observed_played": [19],
                      "season_matches": [38], "observed_goals_for": [20],
                      "observed_goals_against": [10], "observed_xg_for": [16],
                      "observed_xg_against": [16]})
    assert model_predictions(x, "goals_original", 2, .25)[0] == pytest.approx(15 + 3*19*.8)
    assert model_predictions(x, "xg_draw", 2, .25)[0] == pytest.approx(15 + 2.75*19*.5)


def test_gamma_tuning_ignores_test_labels():
    matches, totals = toy_seasons()
    predictions, fold_metrics, grid, folds = run_experiment(matches, totals, cutoff=1, gamma_grid=(1.0, 2.0))
    assert len(predictions) == 10*2*9
    assert len(fold_metrics) == 5*9
    assert len(grid) == 5*4*2
    assert len(folds) == 5
    assert folds.loc[folds.fold == 5, "chronological_holdout"].item()
    for _, g in predictions.groupby("model"):
        assert g.groupby("season").team.nunique().eq(2).all()
        assert len(g) == 20
    assert np.isfinite(predictions.predicted_points).all()
    assert set(predictions.model).issuperset({"tuned_xg_draw", "fixed_xg_draw", "ppg"})
    overall = overall_metrics(predictions, fold_metrics)
    assert overall.teams.eq(20).all()
    assert overall.mae.ge(0).all()

    # Alter only 2022's *future* match. Fold 5 training (2014..2021) is unchanged.
    altered_matches, altered_totals = toy_seasons(change_test_future=True)
    altered_pred, altered_fold, altered_grid, altered_folds = run_experiment(
        altered_matches, altered_totals, cutoff=1, gamma_grid=(1.0, 2.0))
    original_fold5 = predictions.loc[predictions.fold == 5].sort_values(["model", "season", "team"])
    changed_fold5 = altered_pred.loc[altered_pred.fold == 5].sort_values(["model", "season", "team"])
    pd.testing.assert_series_equal(original_fold5.gamma.reset_index(drop=True),
                                   changed_fold5.gamma.reset_index(drop=True))
    pd.testing.assert_series_equal(original_fold5.predicted_points.reset_index(drop=True),
                                   changed_fold5.predicted_points.reset_index(drop=True))
    pd.testing.assert_frame_equal(grid.loc[grid.fold == 5].reset_index(drop=True),
                                  altered_grid.loc[altered_grid.fold == 5].reset_index(drop=True))
    assert not original_fold5.actual_points.reset_index(drop=True).equals(
        changed_fold5.actual_points.reset_index(drop=True))


def test_ranks_do_not_use_future_goal_difference():
    x = pd.DataFrame({"fold": [1, 1], "season": ["2022", "2022"],
                      "model": ["m", "m"], "team": ["A", "B"],
                      "actual_points": [60, 60], "predicted_points": [64., 55.]})
    ranked = add_ranks(x)
    assert ranked.actual_rank.tolist() == [1.5, 1.5]
    assert ranked.predicted_rank.tolist() == [1.0, 2.0]


def test_top_four_overlap_handles_ties():
    from football_analysis.experiment_03 import _top_four_overlap

    data = pd.DataFrame({
        "team": ["A", "B", "C", "D", "E"],
        "actual_points": [80, 70, 60, 50, 40],
        "predicted_points": [80, 70, 60, 50, 50],
    })

    result = _top_four_overlap(data)

    assert result == pytest.approx(4 / 5)
