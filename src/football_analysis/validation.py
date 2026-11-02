"""Validation of a common season loaded from two football data sources."""

from dataclasses import dataclass
import re
from collections.abc import Mapping

import pandas as pd


@dataclass(frozen=True)
class CommonSeasonValidation:
    """Validation result for two canonical match tables."""

    is_valid: bool
    errors: tuple[str, ...]
    match_count: int
    team_count: int

    def raise_if_invalid(self) -> None:
        """Raise a concise error when the validation result is not valid."""
        if not self.is_valid:
            raise ValueError("Common season validation failed: " + "; ".join(self.errors))


def _normalise_team_name(name: object) -> str:
    value = str(name).strip().casefold()
    return re.sub(r"\s+", " ", value)


def _with_team_aliases(
    name: object,
    team_aliases: Mapping[str, str],
) -> str:
    normalised = _normalise_team_name(name)
    aliases = {
        _normalise_team_name(source): _normalise_team_name(target)
        for source, target in team_aliases.items()
    }
    return aliases.get(normalised, normalised)


def _match_keys(
    matches: pd.DataFrame,
    team_aliases: Mapping[str, str],
) -> pd.Series:
    return (
        matches["date"].dt.normalize().astype(str)
        + "|"
        + matches["home_team"].map(
            lambda value: _with_team_aliases(value, team_aliases)
        )
        + "|"
        + matches["away_team"].map(
            lambda value: _with_team_aliases(value, team_aliases)
        )
    )


def _team_pair_keys(
    matches: pd.DataFrame,
    team_aliases: Mapping[str, str],
) -> pd.Series:
    return (
        matches["home_team"].map(
            lambda value: _with_team_aliases(value, team_aliases)
        )
        + "|"
        + matches["away_team"].map(
            lambda value: _with_team_aliases(value, team_aliases)
        )
    )


def validate_common_season(
    understat_matches: pd.DataFrame,
    football_data_matches: pd.DataFrame,
    *,
    league: str = "EPL",
    season: str | None = None,
    team_aliases: Mapping[str, str] | None = None,
) -> CommonSeasonValidation:
    """Check that Understat and football-data rows describe one season.

    The comparison is strict on normalized date, home team, away team and
    final score. Team aliases are opt-in and should be documented for each
    dataset; no fuzzy matching is performed.
    """
    aliases = team_aliases or {}
    errors: list[str] = []
    required = {
        "date",
        "league",
        "season",
        "home_team",
        "away_team",
        "home_goals",
        "away_goals",
    }
    for label, matches in (
        ("Understat", understat_matches),
        ("football-data.co.uk", football_data_matches),
    ):
        missing = sorted(required - set(matches.columns))
        if missing:
            errors.append(f"{label} missing columns: {', '.join(missing)}")
    for label, matches in (("Understat", understat_matches),):
        missing_xg = sorted({"home_xg", "away_xg"} - set(matches.columns))
        if missing_xg:
            errors.append(f"{label} missing columns: {', '.join(missing_xg)}")
    for label, matches in (("football-data.co.uk", football_data_matches),):
        missing_xg = sorted({"home_xg", "away_xg"} - set(matches.columns))
        if missing_xg:
            errors.append(f"{label} missing columns: {', '.join(missing_xg)}")

    if errors:
        return CommonSeasonValidation(False, tuple(errors), 0, 0)

    if not (understat_matches["league"] == league).all():
        errors.append("Understat contains rows outside the requested league")
    if not (football_data_matches["league"] == league).all():
        errors.append("football-data.co.uk contains rows outside the requested league")
    if season is not None:
        if not (understat_matches["season"] == season).all():
            errors.append("Understat contains rows outside the requested season")
        if not (football_data_matches["season"] == season).all():
            errors.append("football-data.co.uk contains rows outside the requested season")

    understat = understat_matches.copy()
    football_data = football_data_matches.copy()
    try:
        for matches in (understat, football_data):
            matches["date"] = pd.to_datetime(matches["date"], errors="raise")
    except (TypeError, ValueError) as error:
        errors.append(f"Invalid match date: {error}")
        return CommonSeasonValidation(False, tuple(errors), 0, 0)

    understat_keys = _match_keys(understat, aliases)
    football_data_keys = _match_keys(football_data, aliases)
    if understat_keys.duplicated().any():
        errors.append("Understat contains duplicate match keys")
    if football_data_keys.duplicated().any():
        errors.append("football-data.co.uk contains duplicate match keys")

    understat_key_set = set(understat_keys)
    football_data_key_set = set(football_data_keys)
    missing_in_football = understat_key_set - football_data_key_set
    missing_in_understat = football_data_key_set - understat_key_set
    if missing_in_football:
        errors.append(
            f"{len(missing_in_football)} Understat matches are missing in football-data.co.uk"
        )
    if missing_in_understat:
        errors.append(
            f"{len(missing_in_understat)} football-data.co.uk matches are missing in Understat"
        )

    understat_by_key = understat.assign(_match_key=understat_keys).set_index("_match_key")
    football_by_key = football_data.assign(_match_key=football_data_keys).set_index("_match_key")
    common_keys = understat_key_set & football_data_key_set
    if not understat_keys.duplicated().any() and not football_data_keys.duplicated().any():
        for key in common_keys:
            understat_score = (
                understat_by_key.loc[key, "home_goals"],
                understat_by_key.loc[key, "away_goals"],
            )
            football_score = (
                football_by_key.loc[key, "home_goals"],
                football_by_key.loc[key, "away_goals"],
            )
            if understat_score != football_score:
                errors.append(f"Score mismatch for match key {key}")

    understat_pairs = _team_pair_keys(understat, aliases)
    football_pairs = _team_pair_keys(football_data, aliases)
    common_pairs = set(understat_pairs) & set(football_pairs)
    if common_pairs:
        understat_pair_dates = (
            understat.assign(_pair_key=understat_pairs)
            .groupby("_pair_key")["date"]
            .apply(lambda values: set(values.dt.normalize()))
        )
        football_pair_dates = (
            football_data.assign(_pair_key=football_pairs)
            .groupby("_pair_key")["date"]
            .apply(lambda values: set(values.dt.normalize()))
        )
        for pair in common_pairs:
            if understat_pair_dates[pair] != football_pair_dates[pair]:
                errors.append(f"Date mismatch for team pair {pair}")

    if understat["home_xg"].isna().any() or understat["away_xg"].isna().any():
        errors.append("Understat contains missing xG values")
    if football_data["home_xg"].notna().any() or football_data["away_xg"].notna().any():
        errors.append("football-data.co.uk must not provide xG values in the benchmark")

    teams = set(understat_keys.str.split("|").str[1]) | set(
        understat_keys.str.split("|").str[2]
    )
    return CommonSeasonValidation(
        is_valid=not errors,
        errors=tuple(errors),
        match_count=len(common_keys),
        team_count=len(teams),
    )
