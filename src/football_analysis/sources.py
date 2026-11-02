"""Load locally downloaded Understat and football-data.co.uk files.

This module intentionally performs no network access. The caller must provide
files that were downloaded separately and must record their source metadata.
"""

from pathlib import Path

import pandas as pd

from .io import load_tabular_data


_CANONICAL_COLUMNS = [
    "date",
    "league",
    "season",
    "home_team",
    "away_team",
    "home_goals",
    "away_goals",
    "home_xg",
    "away_xg",
    "source",
]


def _rename_columns(
    data: pd.DataFrame,
    aliases: dict[str, tuple[str, ...]],
) -> pd.DataFrame:
    """Rename the first matching source column to each canonical name."""
    result = data.copy()
    rename_map: dict[str, str] = {}
    for canonical, candidates in aliases.items():
        match = next(
            (candidate for candidate in candidates if candidate in result.columns),
            None,
        )
        if match is not None:
            rename_map[match] = canonical
    return result.rename(columns=rename_map)


def _validate_match_columns(
    data: pd.DataFrame,
    required: tuple[str, ...],
) -> None:
    missing = [column for column in required if column not in data.columns]
    if missing:
        raise ValueError(f"Missing required match columns: {', '.join(missing)}")


def _finalize_matches(
    data: pd.DataFrame,
    *,
    source: str,
    league: str,
    season: str,
    date_day_first: bool = False,
) -> pd.DataFrame:
    result = data.copy()
    result["date"] = pd.to_datetime(
        result["date"],
        dayfirst=date_day_first,
        errors="raise",
    )
    for column in ("home_goals", "away_goals", "home_xg", "away_xg"):
        if column in result.columns:
            result[column] = pd.to_numeric(result[column], errors="raise")
            if result[column].isna().any() or (result[column] < 0).any():
                raise ValueError(f"{column} must contain non-negative values")

    result["league"] = league
    result["season"] = season
    result["source"] = source
    for column in _CANONICAL_COLUMNS:
        if column not in result.columns:
            result[column] = pd.NA
    return result[_CANONICAL_COLUMNS]


def load_understat_matches(
    path: str | Path,
    *,
    league: str,
    season: str,
) -> pd.DataFrame:
    """Load a locally downloaded Understat match table.

    Expected fields are date, home/away teams, goals and home/away xG. Common
    aliases such as ``h_xg`` and ``a_xg`` are accepted.
    """
    data = _rename_columns(
        load_tabular_data(path),
        {
            "date": ("date", "Date"),
            "home_team": ("home_team", "HomeTeam", "h_team"),
            "away_team": ("away_team", "AwayTeam", "a_team"),
            "home_goals": ("home_goals", "HomeGoals", "h_goals"),
            "away_goals": ("away_goals", "AwayGoals", "a_goals"),
            "home_xg": ("home_xg", "HomeXG", "h_xg"),
            "away_xg": ("away_xg", "AwayXG", "a_xg"),
        },
    )
    _validate_match_columns(
        data,
        (
            "date",
            "home_team",
            "away_team",
            "home_goals",
            "away_goals",
            "home_xg",
            "away_xg",
        ),
    )
    return _finalize_matches(
        data,
        source="understat",
        league=league,
        season=season,
    )


def load_football_data_matches(
    path: str | Path,
    *,
    league: str,
    season: str,
) -> pd.DataFrame:
    """Load a locally downloaded football-data.co.uk results table.

    The loader uses the standard ``Date``, ``HomeTeam``, ``AwayTeam``,
    ``FTHG`` and ``FTAG`` fields and returns a goals-only benchmark table.
    """
    data = _rename_columns(
        load_tabular_data(path),
        {
            "date": ("date", "Date"),
            "home_team": ("home_team", "HomeTeam"),
            "away_team": ("away_team", "AwayTeam"),
            "home_goals": ("home_goals", "FTHG"),
            "away_goals": ("away_goals", "FTAG"),
        },
    )
    _validate_match_columns(
        data,
        ("date", "home_team", "away_team", "home_goals", "away_goals"),
    )
    return _finalize_matches(
        data,
        source="football-data.co.uk",
        league=league,
        season=season,
        date_day_first=True,
    )
