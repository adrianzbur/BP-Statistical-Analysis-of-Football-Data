import pandas as pd

from football_analysis.sources import (
    load_football_data_matches,
    load_understat_matches,
)


def test_load_understat_matches_normalizes_local_csv(tmp_path) -> None:
    path = tmp_path / "understat.csv"
    pd.DataFrame(
        [
            {
                "date": "2022-08-05",
                "h_team": "Team A",
                "a_team": "Team B",
                "h_goals": 2,
                "a_goals": 1,
                "h_xg": 1.4,
                "a_xg": 0.8,
            }
        ]
    ).to_csv(path, index=False)

    result = load_understat_matches(path, league="EPL", season="2022-23")

    assert result.loc[0, "home_team"] == "Team A"
    assert result.loc[0, "home_xg"] == 1.4
    assert result.loc[0, "source"] == "understat"


def test_load_football_data_matches_leaves_xg_missing(tmp_path) -> None:
    path = tmp_path / "football-data.csv"
    pd.DataFrame(
        [
            {
                "Date": "05/08/2022",
                "HomeTeam": "Team A",
                "AwayTeam": "Team B",
                "FTHG": 2,
                "FTAG": 1,
            }
        ]
    ).to_csv(path, index=False)

    result = load_football_data_matches(path, league="EPL", season="2022-23")

    assert result.loc[0, "home_goals"] == 2
    assert pd.isna(result.loc[0, "home_xg"])
    assert result.loc[0, "source"] == "football-data.co.uk"
