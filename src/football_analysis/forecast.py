"""End-of-season points forecasts at each team's kth completed match."""

import pandas as pd

from .metrics import mean_absolute_error, root_mean_squared_error
from .pythagorean import pythagorean_expectation
from .understat_dataset import aggregate_seasons


def forecast_points(matches: pd.DataFrame, totals: pd.DataFrame, *, cutoff: int = 19,
                    exponent: float = 2.0) -> pd.DataFrame:
    """Use prefix data only for features; final points are evaluation labels.

    Cutoffs are per team, not a shared calendar date or official matchweek.
    Target is points earned from results, before administrative deductions.
    """
    if cutoff < 1 or not totals.played.gt(cutoff).all():
        raise ValueError("Cutoff must be positive and before the season ends")
    keys = ["league", "season", "club_name"]
    selected = matches.merge(totals[["league", "season", "team"]].rename(columns={"team": "club_name"}),
                             on=keys, how="inner", validate="many_to_one")
    prefix = selected.sort_values(keys + ["date"]).groupby(keys, sort=False).head(cutoff)
    observed = aggregate_seasons(prefix)
    if len(observed) != len(totals) or not observed.played.eq(cutoff).all():
        raise ValueError("Not enough observed matches for every team")
    observed = observed.rename(columns={c: f"observed_{c}" for c in observed if c not in ("league", "season", "team")})
    dates = prefix.groupby(keys, as_index=False).date.max().rename(columns={"club_name": "team", "date": "cutoff_date"})
    predictions = observed.merge(dates, on=["league", "season", "team"], validate="one_to_one")
    labels = totals[["league", "season", "team", "played", "points"]].rename(
        columns={"played": "season_matches", "points": "actual_points"})
    predictions = predictions.merge(labels, on=["league", "season", "team"], validate="one_to_one")
    remaining = predictions.season_matches - cutoff
    for model, scored, conceded in (("goals", "goals_for", "goals_against"), ("xg", "xg_for", "xg_against")):
        shares = [pythagorean_expectation(gf, ga, exponent) for gf, ga in zip(
            predictions[f"observed_{scored}"], predictions[f"observed_{conceded}"])]
        predictions[f"predicted_{model}"] = predictions.observed_points + 3 * remaining * pd.Series(shares, index=predictions.index)
    predictions["predicted_ppg"] = predictions.observed_points * predictions.season_matches / cutoff
    predictions["exponent"] = exponent
    for model in ("goals", "xg", "ppg"):
        predictions[f"error_{model}"] = predictions[f"predicted_{model}"] - predictions.actual_points
    return predictions


def summarize_forecasts(predictions: pd.DataFrame) -> pd.DataFrame:
    rows = []
    groups = [(str(s), g) for s, g in predictions.groupby("season")] + [("ALL", predictions)]
    for season, group in groups:
        for model in ("goals", "xg", "ppg"):
            actual, predicted = group.actual_points, group[f"predicted_{model}"]
            rows.append({"season": season, "model": model, "teams": len(group),
                         "mae": mean_absolute_error(actual, predicted),
                         "rmse": root_mean_squared_error(actual, predicted),
                         "bias": float((predicted - actual).mean())})
    return pd.DataFrame(rows)
