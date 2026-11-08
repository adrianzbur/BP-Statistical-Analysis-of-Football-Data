"""Adapter for codytipton/understat-data game_stats.csv (one team per match)."""

from pathlib import Path

import numpy as np
import pandas as pd

from .experiment import prepare_totals


NUMERIC = ["scored", "missed", "xG", "xGA", "wins", "draws", "loses", "pts"]
KEY = ["league", "season", "club_name", "date"]


def load_team_matches(path: str | Path) -> pd.DataFrame:
    return validate_team_matches(pd.read_csv(path, dtype={"season": str}))


def validate_team_matches(data: pd.DataFrame) -> pd.DataFrame:
    """Reject duplicates, missing values, invalid scores and result indicators."""
    required = set(KEY + NUMERIC + ["id", "home_away", "result"])
    missing = required - set(data)
    if missing:
        raise ValueError(f"Missing game_stats columns: {sorted(missing)}")
    result = data.copy()
    if result.empty or result[list(required)].isna().any().any():
        raise ValueError("Empty table or missing required values")
    result["season"] = result.season.astype(str)
    result["date"] = pd.to_datetime(result.date, errors="raise")
    if result.date.isna().any():
        raise ValueError("Missing date")
    for column in ("league", "club_name", "season"):
        result[column] = result[column].astype(str).str.strip()
        if result[column].eq("").any():
            raise ValueError(f"Empty {column}")
    if result.duplicated(KEY).any():
        raise ValueError("Duplicate team-match key")
    result[NUMERIC] = result[NUMERIC].apply(pd.to_numeric, errors="raise")
    if not np.isfinite(result[NUMERIC].to_numpy(dtype=float)).all() or (result[NUMERIC] < 0).any().any():
        raise ValueError("Match statistics must be finite and non-negative")
    counts = [c for c in NUMERIC if c not in ("xG", "xGA")]
    if (result[counts] % 1 != 0).any().any():
        raise ValueError("Scores and result counts must be integers")
    expected = np.where(result.scored > result.missed, "w",
                        np.where(result.scored < result.missed, "l", "d"))
    if not np.array_equal(result.result, expected):
        raise ValueError("Result disagrees with score")
    for column, outcome in (("wins", "w"), ("draws", "d"), ("loses", "l")):
        if not result[column].eq((result.result == outcome).astype(int)).all():
            raise ValueError(f"Invalid {column} indicator")
    if not result.pts.eq(3 * result.wins + result.draws).all():
        raise ValueError("Match points disagree with result")
    if not result.home_away.isin(["h", "a"]).all():
        raise ValueError("Invalid home_away value")
    if result.groupby("id").club_name.nunique().gt(1).any():
        raise ValueError("Club ID maps to multiple names")
    return result.sort_values(KEY).reset_index(drop=True)


def pair_team_matches(data: pd.DataFrame) -> pd.DataFrame:
    """Reconstruct unique matches via exact mirrored score/xG and kickoff.

    This export has no match ID or opponent. Exact pairing is verified for
    this snapshot; ambiguity or unmatched rows fail instead of guessing.
    """
    keys = ["league", "season", "date", "scored", "missed", "xG", "xGA"]
    columns = keys + ["club_name"]
    home = data.loc[data.home_away == "h", columns]
    away = data.loc[data.home_away == "a", columns].rename(
        columns={"scored": "missed", "missed": "scored", "xG": "xGA", "xGA": "xG"})
    if home.duplicated(keys).any() or away.duplicated(keys).any():
        raise ValueError("Ambiguous mirrored match signature")
    matches = home.merge(away, on=keys, how="outer", validate="one_to_one",
                         suffixes=("_home", "_away"), indicator=True)
    if not matches._merge.eq("both").all():
        raise ValueError("Unmatched home/away rows")
    matches = matches.rename(columns={"club_name_home": "home_team", "club_name_away": "away_team",
                                      "scored": "home_goals", "missed": "away_goals",
                                      "xG": "home_xg", "xGA": "away_xg"}).drop(columns="_merge")
    if matches.home_team.eq(matches.away_team).any():
        raise ValueError("A team cannot play itself")
    matches["source"] = "kaggle/codytipton/understat-data"
    return matches.sort_values(["league", "season", "date", "home_team"]).reset_index(drop=True)


def aggregate_seasons(data: pd.DataFrame) -> pd.DataFrame:
    """Sum each team's own rows once; do not sum both sides as team totals."""
    return data.groupby(["league", "season", "club_name"], as_index=False).agg(
        played=("date", "size"), wins=("wins", "sum"), draws=("draws", "sum"),
        losses=("loses", "sum"), goals_for=("scored", "sum"), goals_against=("missed", "sum"),
        xg_for=("xG", "sum"), xg_against=("xGA", "sum"), points=("pts", "sum")
    ).rename(columns={"club_name": "team"})


def complete_seasons(data: pd.DataFrame, matches: pd.DataFrame, league: str,
                     expected_teams: int = 20) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Select complete double round-robin seasons and record every exclusion."""
    audit, selected = [], []
    for season, group in data.loc[data.league == league].groupby("season"):
        totals = aggregate_seasons(group)
        games = matches.loc[(matches.league == league) & (matches.season == season)]
        try:
            valid = prepare_totals(totals, league, [season], expected_teams)
            teams = set(valid.team)
            expected_pairs = {(a, b) for a in teams for b in teams if a != b}
            actual_pairs = list(zip(games.home_team, games.away_team))
            if len(actual_pairs) != len(expected_pairs) or set(actual_pairs) != expected_pairs:
                raise ValueError("Schedule is not a complete double round robin")
            selected.append(valid)
            reason = "included"
        except ValueError as error:
            reason = str(error)
        audit.append({"league": league, "season": season, "team_rows": len(group),
                      "matches": len(games), "teams": len(totals),
                      "min_played": int(totals.played.min()), "max_played": int(totals.played.max()),
                      "included": reason == "included", "reason": reason})
    if not selected:
        raise ValueError("No complete seasons for selected league")
    return pd.concat(selected, ignore_index=True), pd.DataFrame(audit)
