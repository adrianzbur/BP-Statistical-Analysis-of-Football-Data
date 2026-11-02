import pandas as pd
import pytest

from football_analysis.validation import validate_common_season


def _matches(*, score=(2, 1), xg=(1.4, 0.8)) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "date": pd.Timestamp("2022-08-05"),
                "league": "EPL",
                "season": "2022-23",
                "home_team": "Team A",
                "away_team": "Team B",
                "home_goals": score[0],
                "away_goals": score[1],
                "home_xg": xg[0],
                "away_xg": xg[1],
                "source": "fixture",
            }
        ]
    )


def test_common_season_validation_accepts_matching_sources() -> None:
    understat = _matches()
    football_data = _matches(xg=(pd.NA, pd.NA))

    result = validate_common_season(understat, football_data)

    assert result.is_valid
    assert result.match_count == 1
    assert result.team_count == 2


@pytest.mark.parametrize(
    "change, expected_error",
    [
        ("date", "missing in football-data.co.uk"),
        ("score", "Score mismatch"),
        ("xg", "missing xG"),
    ],
)
def test_common_season_validation_reports_mismatches(
    change: str,
    expected_error: str,
) -> None:
    understat = _matches()
    football_data = _matches(xg=(pd.NA, pd.NA))
    if change == "date":
        football_data.loc[0, "date"] = pd.Timestamp("2022-08-06")
    elif change == "score":
        football_data.loc[0, "home_goals"] = 1
    else:
        understat.loc[0, "home_xg"] = pd.NA

    result = validate_common_season(understat, football_data)

    assert not result.is_valid
    assert any(expected_error in error for error in result.errors)


def test_common_season_validation_supports_explicit_team_aliases() -> None:
    understat = _matches()
    football_data = _matches(xg=(pd.NA, pd.NA))
    football_data.loc[0, "home_team"] = "Team A FC"

    result = validate_common_season(
        understat,
        football_data,
        team_aliases={"Team A FC": "Team A"},
    )

    assert result.is_valid
