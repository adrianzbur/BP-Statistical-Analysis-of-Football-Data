# Data dictionary

The project works with match-level tables. Source files are downloaded
separately and kept locally under `data/raw`; large source datasets are not
committed to Git.

## Canonical match schema

The loaders in `src/football_analysis/sources.py` return these columns:

| Column | Type | Meaning |
| --- | --- | --- |
| `date` | datetime | Match date as supplied by the source |
| `league` | string | Competition identifier, for example `EPL` |
| `season` | string | Season identifier, for example `2022-23` |
| `home_team` | string | Home team name or source identifier |
| `away_team` | string | Away team name or source identifier |
| `home_goals` | non-negative numeric | Final home-team goals |
| `away_goals` | non-negative numeric | Final away-team goals |
| `home_xg` | non-negative numeric or missing | Understat home expected goals |
| `away_xg` | non-negative numeric or missing | Understat away expected goals |
| `source` | string | Loader/source label |

`home_xg` and `away_xg` are intentionally missing for football-data.co.uk
benchmark rows. They must not be imputed or interpreted as zero.

## Source-specific input formats

### Understat

Use a locally downloaded CSV or Parquet file with at least:

```text
date,home_team,away_team,home_goals,away_goals,home_xg,away_xg
```

The loader also accepts common aliases such as `h_xg`, `a_xg`, `h_team`,
`a_team`, `h_goals` and `a_goals`.

### football-data.co.uk

Use the downloaded CSV with the standard columns:

```text
Date,HomeTeam,AwayTeam,FTHG,FTAG
```

Other columns from the source may remain in the input, but they are not
required by the goals-only benchmark loader. The `Date` field is interpreted
with day-first parsing because that is the standard format in these files.

## File naming and metadata

Recommended local names are:

```text
data/raw/understat_<league>_<season>.csv
data/raw/football-data_<league>_<season>.csv
```

For every downloaded file, record the source URL, download date, league,
season, source version or page description, and any transformations. The
repository contains no downloader and does not bypass robots rules,
rate limits, authentication, or other web protections.

## Scope and limitations

Understat is the xG source for selected top leagues and seasons. Its xG
definition, historical availability, team naming and terms of use must be
checked for the exact data used. football-data.co.uk is the goals-only
benchmark and a control source for match results; it is not an xG source.

The recommended initial scope is one or two selected top leagues and a
small, explicitly documented set of complete seasons available in both
sources. Comparisons must align dates, team names, league and season before
calculating metrics. Differences in coverage, revisions, definitions,
licensing and source quality must be reported rather than silently corrected.
