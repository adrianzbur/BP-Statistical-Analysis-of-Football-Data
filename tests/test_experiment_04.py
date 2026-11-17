"""Tests of Experiment 04 cross-league analysis (no external dataset needed)."""

import numpy as np
import pandas as pd
import pytest

from football_analysis.experiment_04 import (
    half_season_cutoff, run_league_cv, summarize_leagues,
    draw_figures, markdown_report, LEAGUE_PROFILES,
)
from football_analysis.understat_dataset import (
    validate_team_matches, pair_team_matches, complete_seasons,
)


def _toy_seasons(change_future: bool = False):
    """Ten complete two-team seasons with two home/away fixtures per year."""
    data = []
    for year in range(2014, 2024):
        fixtures = [
            ("A", "B", 2 + year % 3, 1),
            ("B", "A", 1, 1 + year % 2),
        ]
        if change_future and year == 2022:
            fixtures[-1] = ("B", "A", 4, 0)
        for ix, (home, away, hg, ag) in enumerate(fixtures):
            for team, venue, scored, missed, xgf, xga in (
                (home, "h", hg, ag, float(hg) + .8, float(ag) + .7),
                (away, "a", ag, hg, float(ag) + .7, float(hg) + .8),
            ):
                won, drawn, lost = int(scored > missed), int(scored == missed), int(scored < missed)
                data.append({
                    "id": 1 if team == "A" else 2, "league": "TEST", "season": str(year),
                    "club_name": team, "date": f"{year}-{8 + ix:02d}-05",
                    "home_away": venue, "scored": scored, "missed": missed,
                    "xG": xgf, "xGA": xga, "wins": won, "draws": drawn, "loses": lost,
                    "result": "w" if won else "d" if drawn else "l", "pts": 3 * won + drawn,
                })
    games = validate_team_matches(pd.DataFrame(data))
    totals, audit = complete_seasons(games, pair_team_matches(games), "TEST", expected_teams=2)
    assert audit.included.all()
    return games, totals


@pytest.mark.parametrize("games,cutoff", [(38, 19), (34, 17), (30, 15), (2, 1)])
def test_cutoff_is_half_of_complete_season(games, cutoff):
    assert half_season_cutoff(games) == cutoff


@pytest.mark.parametrize("invalid", [0, -10, 1, 19, 35])
def test_invalid_season_length_rejected(invalid):
    with pytest.raises(ValueError):
        half_season_cutoff(invalid)


def test_run_league_cv_retains_same_samples_and_training_only_tuning(monkeypatch):
    games, totals = _toy_seasons()
    pred, fm, tuning, folds, overall = run_league_cv(games, totals, gamma_grid=(1., 2.))
    assert len(pred) == 10 * 2 * 9
    assert len(fm) == 5 * 9
    assert len(tuning) == 5 * 4 * 2
    assert len(folds) == 5
    assert folds.train_team_seasons.eq(16).all()
    assert folds.test_team_seasons.eq(4).all()
    assert folds.loc[folds.fold == 5, "chronological_holdout"].all()
    assert len(overall) == 9
    assert overall.teams.eq(20).all()
    assert pred.groupby("model").size().eq(20).all()
    assert all(not g.duplicated(["season", "team"]).any()
               for _, g in pred.groupby("model"))
    assert set(tuning.loc[tuning.selected, "fold"]) == {1, 2, 3, 4, 5}
    assert tuning.loc[tuning.selected].groupby(["fold", "model"]).size().eq(1).all()
    for (fold, model), frame in tuning.groupby(["fold", "model"]):
        best = frame.loc[frame.selected].iloc[0]
        assert best.mae == pytest.approx(frame.mae.min())


def test_future_match_does_not_change_chronological_holdout_predictions(monkeypatch):
    before_games, before_totals = _toy_seasons()
    after_games, after_totals = _toy_seasons(change_future=True)
    before = run_league_cv(before_games, before_totals, gamma_grid=(1., 2.))
    after = run_league_cv(after_games, after_totals, gamma_grid=(1., 2.))
    for field in ("gamma", "predicted_points", "training_draw_rate"):
        b = before[0].loc[before[0].fold == 5].sort_values(["model", "season", "team"])[field]
        a = after[0].loc[after[0].fold == 5].sort_values(["model", "season", "team"])[field]
        pd.testing.assert_series_equal(b.reset_index(drop=True), a.reset_index(drop=True))
    b_true = before[0].loc[before[0].fold == 5].actual_points.reset_index(drop=True)
    a_true = after[0].loc[after[0].fold == 5].actual_points.reset_index(drop=True)
    assert not b_true.equals(a_true)


def test_run_league_rejects_mixed_season_lengths(monkeypatch):
    games, totals = _toy_seasons()
    totals.loc[0, "played"] = 3
    with pytest.raises(ValueError, match="season lengths must match"):
        run_league_cv(games, totals, gamma_grid=(1., 2.))


def test_summary_uses_paired_folds_and_relative_improvement(monkeypatch):
    import football_analysis.experiment_04 as m
    monkeypatch.setattr(m, "LEAGUE_PROFILES", {"TEST": 2})
    overall = pd.DataFrame([
        {"league": "TEST", "model": "tuned_xg_draw", "mae": 4., "rmse": 5., "rank_mae": 1., "top4_overlap": .8, "teams": 20, "cutoff": 1},
        {"league": "TEST", "model": "fixed_xg_draw", "mae": 5., "rmse": 6., "rank_mae": 2., "top4_overlap": .7, "teams": 20, "cutoff": 1},
        {"league": "TEST", "model": "ppg", "mae": 8., "rmse": 9., "rank_mae": 2., "top4_overlap": .6, "teams": 20, "cutoff": 1},
    ])
    fm = []
    for fold in range(1, 6):
        for name in ["tuned_xg_draw", "fixed_xg_draw", "ppg", *[f"tuned_{x}" for x in m.MODEL_TYPES if x != "xg_draw"]]:
            fm.append({"league": "TEST", "model": name, "fold": fold, "mae": 4. if name == "tuned_xg_draw" else (8. if name == "ppg" else 5.),
                       "gamma": 1.2 if name.startswith("tuned_") else (2. if name == "fixed_xg_draw" else np.nan),
                       "teams": 4})
    summary, paired, gamma = summarize_leagues(overall, pd.DataFrame(fm))
    row = summary.iloc[0]
    assert row.mae_improvement_pct == pytest.approx(50.)
    assert len(paired) == 10  # 5 folds x 2 references
    assert paired.loc[paired.reference == "ppg", "delta_mae"].eq(-4.).all()
    assert len(gamma) == 4
    assert gamma.gamma_mean.eq(1.2).all()


def test_graphs_and_report_write_properly(monkeypatch, tmp_path):
    import football_analysis.experiment_04 as m
    monkeypatch.setattr(m, "LEAGUE_PROFILES", {"TEST": 2})
    summary = pd.DataFrame([{"league": "TEST", "teams_per_season": 2, "cutoff": 1,
                             "primary_mae": 4., "primary_rmse": 5., "ppg_mae": 8.,
                             "mae_improvement_pct": 50., "chrono_gamma": 1.2,
                             "chrono_mae": 4., "chrono_ppg_mae": 8.}])
    gamma = pd.DataFrame([{"league": "TEST", "model": f"tuned_{m}",
                           "gamma_mean": 1.2, "gamma_sd": .1} for m in m.MODEL_TYPES])
    paired = pd.DataFrame([{"league": "TEST", "reference": "ppg", "delta_mae": -4.}] * 5)
    audit = pd.DataFrame([{"league": "TEST", "included": True, "selected_for_cv": True}] * 10
                         + [{"league": "Ligue 1", "included": False, "selected_for_cv": False}])
    draw_figures(summary, gamma, tmp_path)
    assert (tmp_path / "mae_by_league.png").stat().st_size > 1000
    assert (tmp_path / "gamma_by_league.png").stat().st_size > 1000
    text = markdown_report(summary, gamma, paired, audit, candidates=(1., 2.))
    assert "TEST" in text and "50.00 %" in text and "Ligue 1" in text
