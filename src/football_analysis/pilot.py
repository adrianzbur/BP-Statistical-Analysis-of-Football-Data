"""Reproduce dataset audit, fixed-exponent experiment and figures from a ZIP."""

import argparse
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import platform
import sqlite3
import subprocess
import zipfile

import numpy as np
import pandas as pd

from .experiment import evaluate
from .forecast import forecast_points, summarize_forecasts
from .understat_dataset import load_team_matches, pair_team_matches, complete_seasons


SOURCE = "https://www.kaggle.com/datasets/codytipton/understat-data"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def extract_inputs(archive: Path) -> Path:
    destination = archive.parent / "understat"
    destination.mkdir(exist_ok=True)
    with zipfile.ZipFile(archive) as bundle:
        for name in ("game_stats.csv", "player_stats.csv", "understat.db"):
            # Fixed member names avoid writing archive-supplied paths.
            payload = bundle.read(name)
            path = destination / name
            if path.exists() and path.read_bytes() != payload:
                raise ValueError(f"Existing extracted file differs: {path}")
            if not path.exists():
                path.write_bytes(payload)
    return destination


def audit_dataset(directory: Path, games: pd.DataFrame, paired: pd.DataFrame,
                  output: Path) -> dict:
    players = pd.read_csv(directory / "player_stats.csv")
    raw_games = pd.read_csv(directory / "game_stats.csv")
    database_equal = {}
    with sqlite3.connect(f"{(directory / 'understat.db').resolve().as_uri()}?mode=ro", uri=True) as connection:
        for name, frame in (("game_stats", raw_games), ("player_stats", players)):
            from_database = pd.read_sql_query(f"SELECT * FROM {name}", connection)
            pd.testing.assert_frame_equal(frame, from_database, check_exact=False, rtol=1e-12, atol=1e-12)
            database_equal[name] = True
    coverage = games.groupby(["league", "season"], as_index=False).agg(
        team_rows=("id", "size"), teams=("club_name", "nunique"),
        first_date=("date", "min"), last_date=("date", "max"))
    counts = games.groupby(["league", "season", "club_name"]).size().groupby(["league", "season"]).agg(
        min_played="min", max_played="max").reset_index()
    coverage = coverage.merge(counts, on=["league", "season"])
    coverage["matches"] = coverage.team_rows // 2
    coverage.to_csv(output / "dataset_coverage.csv", index=False)
    profiles = []
    for name, frame in (("game_stats", raw_games), ("player_stats", players)):
        for column in frame:
            values = frame[column]
            numeric = pd.api.types.is_numeric_dtype(values)
            profiles.append({"table": name, "column": column, "dtype": str(values.dtype),
                             "missing": int(values.isna().sum()), "unique": int(values.nunique()),
                             "min": values.min() if numeric else None,
                             "max": values.max() if numeric else None,
                             "nonfinite": int((~np.isfinite(values)).sum()) if numeric else None})
    pd.DataFrame(profiles).to_csv(output / "column_profile.csv", index=False)
    audit = {"game_rows": len(games), "unique_matches": len(paired), "player_rows": len(players),
             "leagues": sorted(games.league.unique().tolist()),
             "season_labels": sorted(games.season.unique().tolist()),
             "first_match": str(games.date.min()), "last_match": str(games.date.max()),
             "missing_game_values": int(raw_games.isna().sum().sum()),
             "missing_player_values": int(players.isna().sum().sum()),
             "duplicate_team_match_keys": int(games.duplicated(["league", "season", "club_name", "date"]).sum()),
             "duplicate_player_season_keys": int(players.duplicated(["player_id", "season"]).sum()),
             "duplicate_player_season_team_keys": int(players.duplicated(["player_id", "season", "team"]).sum()),
             "exact_player_duplicates": int(players.duplicated().sum()),
             "all_matches_paired_unambiguously": True, "database_matches_csv": database_equal}
    (output / "dataset_audit.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
    return audit


def season_label(value: str) -> str:
    return f"{value}/{str(int(value) + 1)[-2:]}"


def draw_figures(retrospective: pd.DataFrame, forecast: pd.DataFrame,
                 full_metrics: pd.DataFrame, future_metrics: pd.DataFrame, output: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    colors = {"goals": "#2563a6", "xg": "#ce7027", "ppg": "#35846b"}
    labels = {"goals": "Góly, e = 2", "xg": "xG, e = 2", "ppg": "Bodový priemer (PPG)"}
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11,
                         "axes.spines.top": False, "axes.spines.right": False,
                         "axes.titlesize": 13, "figure.facecolor": "white"})
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.6), layout="constrained")
    for ax, data, target, title in zip(axes, (retrospective, forecast), ("points", "actual_points"),
                                      ("Odhad z celej sezóny", "Predikcia po 19 zápasoch tímu")):
        for model in ("goals", "xg"):
            ax.scatter(data[target], data[f"predicted_{model}"], s=23, alpha=0.55,
                       color=colors[model], label=labels[model], edgecolors="none")
        ax.plot([0, 114], [0, 114], color="#777777", lw=1, linestyle="--", label="Presný odhad")
        ax.set(xlim=(0, 114), ylim=(0, 114), xlabel="Skutočne získané body", ylabel="Odhad konečných bodov", title=title)
        ax.grid(alpha=0.15)
        ax.legend(loc="upper left", fontsize=9)
    fig.suptitle("Premier League 2014/15 – 2023/24 | 200 tímových sezón", fontsize=15)
    fig.savefig(output / "predicted_vs_actual.png", dpi=170)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(13, 5.5), layout="constrained", sharey=True)
    for ax, table, title in zip(axes, (full_metrics, future_metrics),
                                ("Odhad z celej sezóny", "Predikcia po 19 zápasoch tímu")):
        for model, group in table.loc[table.season != "ALL"].groupby("model"):
            group = group.sort_values("season")
            ax.plot([season_label(s) for s in group.season], group.mae, marker="o", markersize=4,
                    color=colors[model], label=labels[model])
        ax.set(ylabel="MAE v bodoch (nižšie je lepšie)", title=title, ylim=(0, None))
        ax.tick_params(axis="x", rotation=45)
        ax.grid(axis="y", alpha=0.2)
        ax.legend(fontsize=9)
    fig.suptitle("Chyba odhadu podľa sezóny", fontsize=15)
    fig.savefig(output / "mae_by_season.png", dpi=170)
    plt.close(fig)


def metrics_table(table: pd.DataFrame) -> str:
    lines = ["| Model | MAE | RMSE | Bias |", "| --- | ---: | ---: | ---: |"]
    names = {"goals": "Góly, e = 2", "xg": "xG, e = 2", "ppg": "Bodový priemer (PPG)"}
    for row in table.loc[table.season == "ALL"].itertuples():
        lines.append(f"| {names[row.model]} | {row.mae:.3f} | {row.rmse:.3f} | {row.bias:+.3f} |")
    return "\n".join(lines)


def write_report(totals: pd.DataFrame, full: pd.DataFrame, future: pd.DataFrame,
                 audit: dict, cutoff: int, output: Path) -> None:
    seasons = sorted(totals.season.unique())
    seasonal = future.pivot(index="season", columns="model", values="mae").drop(index="ALL")
    lines = ["| Sezóna | Góly MAE | xG MAE | PPG MAE |", "| --- | ---: | ---: | ---: |"]
    for season, row in seasonal.iterrows():
        lines.append(f"| {season_label(season)} | {row['goals']:.3f} | {row['xg']:.3f} | {row['ppg']:.3f} |")
    overall = future.loc[future.season == "ALL"].set_index("model")
    relative_change = 100 * (overall.loc["goals", "mae"] - overall.loc["xg", "mae"]) / overall.loc["goals", "mae"]
    xg_better_seasons = int((seasonal.xg < seasonal.goals).sum())
    xg_minus_ppg = overall.loc["xg", "mae"] - overall.loc["ppg", "mae"]
    report = f"""# Experiment 01: pevný Pythagorejský exponent

## Dáta a výber

Zdroj: [{SOURCE}]({SOURCE}), používateľom dodaný archív `Understat-data.zip`.
Archív obsahuje {audit['game_rows']:,} riadkov tím–zápas, {audit['unique_matches']:,}
jedinečných zápasov a {audit['player_rows']:,} hráčskych záznamov.
Overené obdobie zápasov: {audit['first_match']} až {audit['last_match']}.

Experiment používa EPL, {len(seasons)} kompletných sezón
{season_label(seasons[0])} – {season_label(seasons[-1])}, {len(totals)} tímových sezón
a {int(totals.played.sum() / 2)} zápasov. Každý tím má 38 zápasov.
Výber závisí od úplnosti rozpisu, nie od výsledku modelu.
Neúplné sezóny aj dôvody vylúčenia sú v `season_selection.csv`.

## Metóda

Exponent **e = 2** je pevný pre oba modely a všetky sezóny. Neladí sa na dátach.
Pythagorejský podiel: `s = GF^2 / (GF^2 + GA^2)`; xG model nahrádza GF/GA za xG/xGA.
Pri nulovom GF aj GA sa výpočet zastaví; v použitých agregátoch taký prípad nenastal.

1. Retrospektívny odhad: `3 × 38 × s`, so vstupmi z celej sezóny.
2. Predikcia po {cutoff} zápasoch tímu: `body_doteraz + 3 × (38 − {cutoff}) × s_doteraz`.
3. Referenčný model PPG: `38 × body_doteraz / {cutoff}`.

Pri predikcii sa góly, xG a už získané body počítajú iba z prvých {cutoff}
chronologických zápasov daného tímu. Dátum hranice je uložený pre každý tím.
Nejde o spoločný kalendárny dátum ani o oficiálne {cutoff}. kolo.
Konečné body vstupujú iba do vyhodnotenia. Počet 38 je známy rozpis sezóny.

**Cieľ sú body získané zo zápasov (3W + D), pred administratívnymi odpočtami.**
Dataset neobsahuje oficiálnu konečnú tabuľku ani históriu bodových trestov.
Preto výsledky neoznačujeme za predikciu oficiálneho bodového stavu po sankciách.

## Výsledky: retrospektívny odhad

{metrics_table(full)}

## Výsledky: predikcia po {cutoff} zápasoch

{metrics_table(future)}

Metriky sú v bodoch na tím. MAE je priemerná absolútna chyba; RMSE viac
penalizuje veľké chyby. Bias je priemer (odhad − skutočnosť).
Súhrn používa všetkých {len(totals)} tímových sezón, bez zaokrúhľovania odhadov.

{chr(10).join(lines)}

![Skutočné a odhadnuté body](predicted_vs_actual.png)

![MAE podľa sezóny](mae_by_season.png)

## Interpretácia a obmedzenia

Pri predikcii má xG oproti gólom o {relative_change:.1f} % nižšiu celkovú MAE
a nižšiu MAE v {xg_better_seasons} z {len(seasons)} sezón.
Rozdiel MAE (xG − PPG) je {xg_minus_ppg:+.6f} bodu; kladná hodnota znamená
vyššiu chybu xG. RMSE je {overall.loc['xg', 'rmse']:.3f} pri xG a
{overall.loc['ppg', 'rmse']:.3f} pri PPG. Zlepšenie voči gólovému modelu teda
samo osebe neznamená zlepšenie voči bodovému priemeru.

Celosezónny odhad je opisný; jeho úspešnosť nedokazuje schopnosť predvídať
budúcnosť. Na tú slúži samostatné vyhodnotenie po {cutoff} zápasoch.
PPG je dôležitá referencia: Pythagorejský model má zmysel posudzovať aj voči nemu,
nie iba porovnávať góly s xG navzájom.

Násobenie podielu tromi nemodeluje remízy a môže nadhodnocovať počet bodov.
Toto je jednoduchý benchmark, nie úplný futbalový model pravdepodobností.
Nerieši silu zostávajúcich súperov, domáce prostredie, prestupy ani zmenu formy.
Opakované tímy a sezóny nie sú nezávislé pozorovania. Rozdiely metrík sú opisné,
bez tvrdenia štatistickej významnosti alebo automatickej platnosti pre iné ligy.
Historická verzia xG nemusí byť totožná s hodnotami dostupnými v deň predikcie.

Ďalší experiment: explicitne zohľadniť remízy s parametrami z predchádzajúcich
sezón a zachovať chronologické testovanie. Až potom samostatne skúmať exponent.

## Reprodukcia

Z koreňa repozitára po inštalácii `python -m pip install -e ".[dev,analysis]"`:

```text
python -m football_analysis.pilot data/raw/Understat-data.zip
```

Audit je v `dataset_audit.json`, pokrytie v `dataset_coverage.csv`, profil
stĺpcov v `column_profile.csv`. `retrospective_predictions.csv` a
`forecast_predictions.csv` obsahujú všetky tímové odhady a chyby.
Parametre, SHA-256 vstupov a kódu, verzie knižníc a Git revízia sú v `metadata.json`.
Licencia/verzia Kaggle nie je pribalená v archíve; zatiaľ nebola potvrdená.
Zdrojové súbory zostávajú mimo Gitu podľa `.gitignore`.
"""
    (output / "report.md").write_text(report, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--output", type=Path, default=Path("reports/experiment_01"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    directory = extract_inputs(args.archive)
    games = load_team_matches(directory / "game_stats.csv")
    paired = pair_team_matches(games)
    audit = audit_dataset(directory, games, paired, args.output)
    totals, selection = complete_seasons(games, paired, "EPL", expected_teams=20)
    selection.to_csv(args.output / "season_selection.csv", index=False)
    processed = Path("data/processed")
    processed.mkdir(parents=True, exist_ok=True)
    totals.to_csv(processed / "understat_EPL_totals.csv", index=False)
    predictions, metrics = evaluate(totals, exponent=2.0)
    forecast = forecast_points(games, totals, cutoff=19, exponent=2.0)
    future_metrics = summarize_forecasts(forecast)
    for name, frame in (("retrospective_predictions", predictions), ("retrospective_metrics", metrics),
                        ("forecast_predictions", forecast), ("forecast_metrics", future_metrics)):
        frame.to_csv(args.output / f"{name}.csv", index=False)
    draw_figures(predictions, forecast, metrics, future_metrics, args.output)
    write_report(totals, metrics, future_metrics, audit, 19, args.output)
    try:
        revision = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
        dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], text=True).strip())
    except (OSError, subprocess.CalledProcessError):
        revision, dirty = None, None
    metadata = {"source_url": SOURCE, "source_attribution": "user-supplied ZIP; Kaggle version/license unconfirmed",
                "downloaded_at": None, "analysis_utc": datetime.now(timezone.utc).isoformat(),
                "archive_sha256": sha256(args.archive),
                "input_sha256": {p.name: sha256(p) for p in sorted(directory.iterdir()) if p.is_file()},
                "code_sha256": {p.name: sha256(p) for p in sorted(Path(__file__).parent.glob('*.py'))},
                "git_revision": revision, "git_dirty": dirty, "python": platform.python_version(),
                "pandas": pd.__version__, "numpy": np.__version__, "matplotlib": version("matplotlib"), "league": "EPL",
                "seasons": sorted(totals.season.unique().tolist()), "exponent": 2.0, "cutoff_matches": 19,
                "target": "points earned on pitch (3W+D), no administrative deductions",
                "zero_for_and_against_policy": "raise ValueError",
                "selection_rule": "20 teams; every ordered home-away pair exactly once; 38 matches per team",
                "draw_handling": "no draw correction; 3 * Pythagorean share mapping",
                "forecast_formula": "observed_points + 3 * remaining_matches * observed_share",
                "baseline_formula": "38 * observed_points / 19"}
    (args.output / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print("RETROSPECTIVE\n" + metrics.loc[metrics.season == "ALL"].to_string(index=False))
    print("FORECAST\n" + future_metrics.loc[future_metrics.season == "ALL"].to_string(index=False))
    print("SELECTION\n" + selection.to_string(index=False))


if __name__ == "__main__":
    main()
