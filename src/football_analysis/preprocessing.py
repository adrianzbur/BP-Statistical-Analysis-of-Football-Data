"""Validation and preparation of team-season data."""

from collections.abc import Iterable

import pandas as pd


DEFAULT_REQUIRED_COLUMNS = ("team", "season", "goals_for", "goals_against")


def preprocess_team_season_data(
    data: pd.DataFrame,
    required_columns: Iterable[str] = DEFAULT_REQUIRED_COLUMNS,
) -> pd.DataFrame:
    """Return a validated copy of team-season data.

    Numeric goal columns are converted with strict validation. No missing
    values are imputed and no xG values are created by this function.
    """
    required = tuple(required_columns)
    missing = [column for column in required if column not in data.columns]
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")

    result = data.copy()
    for column in ("goals_for", "goals_against"):
        if column in result.columns:
            result[column] = pd.to_numeric(result[column], errors="raise")
            if result[column].isna().any() or (result[column] < 0).any():
                raise ValueError(f"{column} must contain non-negative values")

    return result
