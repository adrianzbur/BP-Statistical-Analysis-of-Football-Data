"""Fixed-exponent retrospective points baseline; accepts season TOTALS only.

Run with python -m football_analysis.experiment --help.
No network access, imputation, exponent fitting or inferred aggregation.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess

import numpy as np
import pandas as pd

from .metrics import mean_absolute_error, root_mean_squared_error
from .pythagorean import pythagorean_expectation


ALIASES = {"year": "season", "scored": "goals_for", "missed": "goals_against",
           "xG": "xg_for", "xGA": "xg_against", "pts": "points",
           "matches": "played", "loses": "losses"}
REQUIRED = ("league", "season", "team", "played", "wins", "draws", "losses",
            "goals_for", "goals_against", "xg_for", "xg_against", "points")


def prepare_totals(data: pd.DataFrame, league: str, seasons: list[str],
                   expected_teams: int = 20) -> pd.DataFrame:
    """Validate explicit team-season totals for a double round-robin league.

    Match rows and per-match averages must be aggregated/converted explicitly
    before using this function. 'year' is preserved as a season start label.
    """
    if expected_teams < 2 or not seasons or len(set(seasons)) != len(seasons):
        raise ValueError("Specify at least two teams and distinct season labels")
    for source, target in ALIASES.items():
        if source in data and target in data:
            raise ValueError(f"Ambiguous columns: {source}, {target}")
    result = data.rename(columns=ALIASES).copy()
    missing = set(REQUIRED) - set(result.columns)
    if missing:
        raise ValueError(f"Missing season-total columns: {sorted(missing)}")
    result["season"] = result["season"].astype(str)
    result = result.loc[(result.league == league) & result.season.isin(seasons)].copy()
    if set(result.season) != set(seasons):
        raise ValueError("Some requested seasons are absent; inspect league/season labels")
    if result.team.isna().any() or result.team.astype(str).str.strip().eq("").any():
        raise ValueError("Team names must be present")
    result["team"] = result.team.astype(str).str.strip()
    if result.duplicated(["league", "season", "team"]).any():
        raise ValueError("Duplicate team-season rows; input must contain season totals")
    numeric = list(REQUIRED[3:])
    result[numeric] = result[numeric].apply(pd.to_numeric, errors="raise")
    if not np.isfinite(result[numeric].to_numpy(dtype=float)).all() or (result[numeric] < 0).any().any():
        raise ValueError("Totals must be finite, non-negative and non-missing")
    integers = [c for c in numeric if c not in ("xg_for", "xg_against")]
    if (result[integers] % 1 != 0).any().any():
        raise ValueError("Counts must be integers; per-game averages are not totals")
    if not result.played.eq(2 * (expected_teams - 1)).all():
        raise ValueError("Incomplete season or wrong expected team count")
    if not (result.wins + result.draws + result.losses).eq(result.played).all():
        raise ValueError("W + D + L must equal played")
    if not (3 * result.wins + result.draws).eq(result.points).all():
        raise ValueError("Points differ from 3W+D; document deductions before analysis")
    for season, group in result.groupby("season"):
        if len(group) != expected_teams:
            raise ValueError(f"{season}: incomplete set of teams")
        if group.wins.sum() != group.losses.sum() or group.draws.sum() % 2:
            raise ValueError(f"{season}: inconsistent league results")
        for scored, conceded in (("goals_for", "goals_against"), ("xg_for", "xg_against")):
            if not math.isclose(group[scored].sum(), group[conceded].sum(), abs_tol=0.05):
                raise ValueError(f"{season}: league {scored}/{conceded} do not balance")
    return result.sort_values(["season", "team"]).reset_index(drop=True)


def evaluate(data: pd.DataFrame, exponent: float = 2.0) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Evaluate naive 3*N*share points mapping, identically for goals and xG.

    This intentionally simple baseline does not model draws. Full-season
    inputs explain that same season; they are not a forward forecast.
    """
    predictions = data.copy()
    summaries = []
    for model, scored, conceded in (("goals", "goals_for", "goals_against"),
                                     ("xg", "xg_for", "xg_against")):
        predictions[f"predicted_{model}"] = [
            3 * n * pythagorean_expectation(gf, ga, exponent)
            for n, gf, ga in zip(data.played, data[scored], data[conceded])]
        predictions[f"error_{model}"] = predictions[f"predicted_{model}"] - data.points
        groups = [(str(s), g) for s, g in predictions.groupby("season")]
        groups.append(("ALL", predictions))
        for season, group in groups:
            actual, predicted = group.points, group[f"predicted_{model}"]
            summaries.append({"season": season, "model": model, "exponent": exponent,
                              "teams": len(group), "mae": mean_absolute_error(actual, predicted),
                              "rmse": root_mean_squared_error(actual, predicted),
                              "bias": float((predicted - actual).mean())})
    return predictions, pd.DataFrame(summaries)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--league", required=True)
    parser.add_argument("--seasons", nargs="+", required=True)
    parser.add_argument("--expected-teams", type=int, default=20)
    parser.add_argument("--exponent", type=float, default=2.0)
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--downloaded-at", required=True, help="Recorded source download date")
    parser.add_argument("--output", type=Path, default=Path("reports/experiment_01"))
    args = parser.parse_args()
    raw = pd.read_csv(args.input, dtype={"year": str, "season": str})
    data = prepare_totals(raw, args.league, args.seasons, args.expected_teams)
    predictions, metrics = evaluate(data, args.exponent)
    try:
        revision = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
        dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], text=True).strip())
    except (OSError, subprocess.CalledProcessError):
        revision, dirty = None, None
    metadata = {"input": str(args.input), "sha256": hashlib.sha256(args.input.read_bytes()).hexdigest(),
                "source_url": args.source_url, "downloaded_at": args.downloaded_at,
                "league": args.league, "seasons": args.seasons, "exponent": args.exponent,
                "expected_teams": args.expected_teams, "git_revision": revision, "git_dirty": dirty,
                "evaluation": "retrospective full-season; not a forward forecast",
                "points_formula": "3 * played * GF^e / (GF^e + GA^e); xG substituted identically",
                "draws": "not modelled; inspect positive bias", "input_columns": list(raw.columns)}
    args.output.mkdir(parents=True, exist_ok=True)
    predictions.to_csv(args.output / "predictions.csv", index=False)
    metrics.to_csv(args.output / "metrics.csv", index=False)
    (args.output / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(metrics.to_string(index=False))


if __name__ == "__main__":
    main()
