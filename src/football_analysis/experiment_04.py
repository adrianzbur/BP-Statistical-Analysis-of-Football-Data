"""Experiment 04: cross-league Pythagorean exponent comparison.

Five leagues with ten complete double-round-robin seasons each receive the
same season-blocked 5-fold (8 train / 2 test) validation as Experiment 03.
A sixth league, Ligue 1, is audited but not included in the like-for-like
comparison because the supplied snapshot contains only nine complete seasons
and changes from 20 to 18 teams in 2023/24.

All gamma tuning and draw calibration are performed on TRAIN seasons only;
folds 1-4 are retrospective, and fold 5 is the chronological holdout.

Run from project root after pip install -e ".[dev,analysis]":
    python -m football_analysis.experiment_04
    python -m football_analysis.experiment_04 data/raw/understat/game_stats.csv
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform

import numpy as np
import pandas as pd

from .experiment_02 import _source_csv
from .experiment_03 import make_gamma_grid, overall_metrics, run_experiment
from .understat_dataset import complete_seasons, load_team_matches, pair_team_matches


# Exact league identifiers from the supplied Understat export.
# The other league, 'Ligue 1', is audited separately due to historical changes.
LEAGUE_PROFILES = {
    "EPL": 20,
    "La liga": 20,
    "Serie A": 20,
    "Bundesliga": 18,
    "RFPL": 16,
}
PRIMARY_MODEL = "tuned_xg_draw"
BENCHMARK_MODEL = "ppg"
MODEL_TYPES = ("goals_original", "xg_original", "goals_draw", "xg_draw")


def half_season_cutoff(matches_per_team: int) -> int:
    """Use the same fraction of the season across leagues (19, 17, or 15)."""
    if matches_per_team < 2 or matches_per_team % 2:
        raise ValueError("A complete even-length double round-robin season is required")
    return matches_per_team // 2


def audit_snapshot(team_matches: pd.DataFrame, paired_matches: pd.DataFrame):
    """Audit all six leagues and return the five comparable full-season datasets.

    The complete_seasons validator verifies exact home-away pairs, not merely
    row counts. Ligue 1 is inspected separately with the known team-count change
    in 2023, but is deliberately excluded from 10-season five-fold CV.
    """
    audits = []
    totals_by_league = {}
    for league, teams in LEAGUE_PROFILES.items():
        valid, audit = complete_seasons(team_matches, paired_matches, league, expected_teams=teams)
        seasons = sorted(valid.season.astype(str).unique())
        if len(seasons) < 10:
            raise ValueError(f"{league} has only {len(seasons)} complete seasons; 10 required")
        selected = seasons[-10:]
        valid = valid.loc[valid.season.astype(str).isin(selected)].copy()
        if valid.played.nunique() != 1 or valid.played.iloc[0] != 2 * (teams - 1):
            raise ValueError(f"{league}: unexpected season length")
        audit["expected_teams"] = teams
        audit["selected_for_cv"] = audit.included & audit.season.astype(str).isin(selected)
        audit["cv_policy"] = "10 complete seasons; 5 x (8 training + 2 test)"
        audits.append(audit)
        totals_by_league[league] = valid

    # 2019/20 Ligue 1 was not completed, and 2023/24 has 18 teams.
    # Use both exact round-robin validators; do NOT silently treat 2023 as
    # incomplete merely because the competition changed its team count.
    l1_20, audit_20 = complete_seasons(team_matches, paired_matches, "Ligue 1", expected_teams=20)
    l1_18, audit_18 = complete_seasons(team_matches, paired_matches, "Ligue 1", expected_teams=18)
    _ = l1_20, l1_18
    other = []
    for _, row in audit_20.iterrows():
        season = str(row["season"])
        selected_profile = audit_18 if int(season) >= 2023 else audit_20
        picked = selected_profile.loc[selected_profile.season.astype(str) == season]
        if len(picked) != 1:
            raise ValueError(f"Missing Ligue 1 audit for {season}")
        item = picked.iloc[0].to_dict()
        item["expected_teams"] = 18 if int(season) >= 2023 else 20
        item["selected_for_cv"] = False
        item["cv_policy"] = "audited only; not comparable with 10-season 5-fold CV"
        other.append(item)
    audits.append(pd.DataFrame(other))
    audit_all = pd.concat(audits, ignore_index=True).sort_values(["league", "season"]).reset_index(drop=True)
    audit_all["season"] = audit_all.season.astype(str)
    audit_all["included"] = audit_all.included.astype(bool)
    audit_all["selected_for_cv"] = audit_all.selected_for_cv.astype(bool)
    return audit_all, totals_by_league


def run_league_cv(team_matches: pd.DataFrame, totals: pd.DataFrame, *, gamma_grid=None):
    """Run Experiment 03 logic for one homogeneous 10-season league."""
    if len(totals) == 0 or totals.league.nunique() != 1:
        raise ValueError("Exactly one nonempty league is required")
    if totals.played.nunique() != 1:
        raise ValueError("Within-league season lengths must match")
    seasons = sorted(totals.season.astype(str).unique())
    if len(seasons) != 10:
        raise ValueError("Exactly ten complete seasons are needed for 5-fold CV")
    cutoff = half_season_cutoff(int(totals.played.iloc[0]))
    league = str(totals.league.iloc[0])
    rows = team_matches.loc[team_matches.league == league]
    pred, fold_metrics, tuning, folds = run_experiment(
        rows, totals, cutoff=cutoff, gamma_grid=gamma_grid,
    )
    overall = overall_metrics(pred, fold_metrics)
    for df in (pred, fold_metrics, tuning, folds, overall):
        if "league" not in df.columns:
            df.insert(0, "league", league)
        df["cutoff"] = cutoff
    return pred, fold_metrics, tuning, folds, overall


def summarize_leagues(overall: pd.DataFrame, fold_metrics: pd.DataFrame):
    """Paired comparison of the predeclared xG+draws model against PPG.

    Report descriptive fold-level deltas, not p-values: training sets overlap.
    Models within a league are evaluated on identical test team-seasons.
    """
    summary, paired, gammas = [], [], []
    for league in LEAGUE_PROFILES:
        ov = overall.loc[overall.league == league].set_index("model")
        fm = fold_metrics.loc[fold_metrics.league == league]
        expected = {PRIMARY_MODEL, BENCHMARK_MODEL, "fixed_xg_draw"}
        if not expected.issubset(set(ov.index)):
            raise ValueError(f"{league}: missing evaluation models")
        primary, ppg = ov.loc[PRIMARY_MODEL], ov.loc[BENCHMARK_MODEL]
        for reference in (BENCHMARK_MODEL, "fixed_xg_draw"):
            ref = fm.loc[fm.model == reference].set_index("fold")
            candidate = fm.loc[fm.model == PRIMARY_MODEL].set_index("fold")
            if set(candidate.index) != set(range(1, 6)) or set(ref.index) != set(range(1, 6)):
                raise ValueError(f"{league}: five corresponding folds are required")
            for fold in range(1, 6):
                a, b = candidate.loc[fold], ref.loc[fold]
                if int(a.teams) != int(b.teams):
                    raise ValueError(f"{league}: paired samples differ")
                paired.append({"league": league, "fold": fold,
                               "candidate": PRIMARY_MODEL, "reference": reference,
                               "candidate_mae": float(a.mae), "reference_mae": float(b.mae),
                               "delta_mae": float(a.mae - b.mae),
                               "improvement_pct": 100 * (b.mae - a.mae) / b.mae if b.mae else np.nan})
        for kind in MODEL_TYPES:
            model = f"tuned_{kind}"
            model_folds = fm.loc[fm.model == model].sort_values("fold")
            if len(model_folds) != 5 or model_folds.gamma.isna().any():
                raise ValueError(f"{league}: missing gamma for {model}")
            gammas.append({"league": league, "model": model,
                           "gamma_mean": float(model_folds.gamma.mean()),
                           "gamma_sd": float(model_folds.gamma.std(ddof=1)),
                           "gamma_min": float(model_folds.gamma.min()),
                           "gamma_max": float(model_folds.gamma.max()),
                           "chronological_gamma": float(model_folds.loc[model_folds.fold == 5, "gamma"].iloc[0])})
        chron = fm.loc[(fm.fold == 5) & (fm.model == PRIMARY_MODEL)].iloc[0]
        ppg_chron = fm.loc[(fm.fold == 5) & (fm.model == BENCHMARK_MODEL)].iloc[0]
        summary.append({"league": league, "teams_per_season": int(round(primary.teams / 10)),
                        "season_matches": int(primary.cutoff * 2), "cutoff": int(primary.cutoff),
                        "test_team_seasons": int(primary.teams),
                        "primary_model": PRIMARY_MODEL,
                        "primary_mae": float(primary.mae),
                        "primary_rmse": float(primary.rmse),
                        "primary_rank_mae": float(primary.rank_mae),
                        "primary_top4_overlap": float(primary.top4_overlap),
                        "ppg_mae": float(ppg.mae),
                        "mae_improvement_pct": (100 * (ppg.mae-primary.mae) / ppg.mae),
                        "chrono_mae": float(chron.mae),
                        "chrono_ppg_mae": float(ppg_chron.mae),
                        "chrono_gamma": float(chron.gamma)})
    return (pd.DataFrame(summary), pd.DataFrame(paired), pd.DataFrame(gammas))


def draw_figures(summary: pd.DataFrame, gammas: pd.DataFrame, output: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    display = summary.set_index("league").loc[list(LEAGUE_PROFILES)]
    with plt.rc_context({"font.family": "DejaVu Sans", "font.size": 10}):
        fig, ax = plt.subplots(figsize=(10, 5.6), layout="constrained")
        x = np.arange(len(display))
        width = 0.36
        ax.bar(x-width/2, display.primary_mae, width, label="Optimalizované xG + remízy")
        ax.bar(x+width/2, display.ppg_mae, width, label="PPG")
        ax.set(xticks=x, xticklabels=list(display.index),
               ylabel="MAE (body / tímová sezóna)",
               title="Experiment 04 – porovnanie presnosti v piatich ligách")
        ax.set_ylim(0, max(display.primary_mae.max(), display.ppg_mae.max())*1.18)
        ax.grid(axis="y", alpha=.2)
        ax.set_axisbelow(True)
        ax.legend()
        fig.savefig(output / "mae_by_league.png", dpi=170)
        plt.close(fig)

        fig, ax = plt.subplots(figsize=(11, 5.8), layout="constrained")
        models = list(gammas.model.unique())
        x = np.arange(len(LEAGUE_PROFILES))
        for i, model in enumerate(models):
            values = gammas.loc[gammas.model == model].set_index("league").loc[list(LEAGUE_PROFILES)]
            offset = (i - (len(models)-1)/2) * .18
            ax.errorbar(x + offset, values.gamma_mean, yerr=values.gamma_sd,
                        fmt="o", capsize=4, label=model)
        ax.set(xticks=x, xticklabels=list(LEAGUE_PROFILES), ylabel="Optimalizované γ (priemer ± SD foldov)",
               title="Experiment 04 – optimalizovaný exponent podľa ligy")
        ax.grid(axis="y", alpha=.2)
        ax.legend(fontsize=8)
        fig.savefig(output / "gamma_by_league.png", dpi=170)
        plt.close(fig)


def markdown_report(summary: pd.DataFrame, gammas: pd.DataFrame, paired: pd.DataFrame,
                    audit: pd.DataFrame, *, candidates: tuple[float, ...]) -> str:
    lines = ["# Experiment 04 – optimalizácia Pytagorovho exponentu v rôznych ligách", "",
             "## Cieľ a metodika", "",
             "Rozšírenie Experimentu 03 na päť súťaží s **desiatimi kompletnými sezónami 2014/15–2023/24**.",
             "Každá liga sa kalibruje **samostatne**, bez miešania údajov medzi ligami.",
             "V každom z 5 foldov sa používajú **8 celých sezón na tréning a 2 na test**.",
             "Každá testovacia sezóna sa použije práve raz. Vstupy do predikcie tvoria",
             "prvé zápasy každého tímu: EPL/La Liga/Serie A **19 z 38**, Bundesliga **17 z 34**",
             "a RFPL **15 z 30**.",
             f"Pytagorov exponent γ sa pre každý variant optimalizuje pomocou tréningovej MAE na mriežke **{min(candidates):g}–{max(candidates):g}** (krok 0,1).",
             "Podiel remíz sa odhaduje iba z trénovacích sezón aktuálnej ligy a foldu.",
             "Hlavné vopred určené porovnanie: **optimalizovaný xG model s korekciou remíz proti PPG**.",
             "Všetky modely v jednej lige sa testujú na totožných tímových sezónach.",
             "", "**Časová interpretácia:** foldy 1–4 sú retrospektívna CV a môžu trénovať aj na novších sezónach",
             "než testované. **Iba fold 5** (test 2022/23 a 2023/24) je chronologický holdout.",
             "Výsledky nie sú prospektívnym nasadením ani dôkazom štatistickej významnosti.",
             "", "## Audit sezón a výber líg", "",
             "| Liga | Kompletné sezóny v zdroji | Zahrnuté do 5-fold CV | Poznámka |",
             "| --- | ---: | --- | --- |"]
    for league in [*LEAGUE_PROFILES, "Ligue 1"]:
        a = audit.loc[audit.league == league]
        complete = int(a.included.sum())
        ncv = int(a.selected_for_cv.sum())
        note = "10 homogénnych ročníkov" if ncv == 10 else "Ligue 1: neúplná 2019/20 a zmena počtu tímov na 18 v 2023/24"
        lines.append(f"| {league} | {complete} | {'Áno' if ncv == 10 else 'Nie'} | {note} |")
    lines += ["", "Podrobný výber, dôvody vylúčenia a počet zápasov sú v `league_audit.csv`.",
              "Ročník 2024/25 je v dodanom exporte neúplný a nie je hodnotený.",
              "Ligue 1 má v exporte **9 dokončených sezón**; preto na ňu nemožno použiť",
              "identický postup 5 × (8 tréningových + 2 testovacie) bez zmeny metodiky.",
              "", "## Hlavné výsledky – optimalizované xG + remízy vs. PPG", "",
              "| Liga | Tímy | Hranica | MAE xG+remízy | MAE PPG | Zlepšenie MAE | RMSE xG+remízy |",
              "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for r in summary.itertuples():
        lines.append(f"| {r.league} | {r.teams_per_season} | {r.cutoff} | {r.primary_mae:.3f} | {r.ppg_mae:.3f} | {r.mae_improvement_pct:+.2f} % | {r.primary_rmse:.3f} |")
    lines += ["", "![MAE podľa ligy](mae_by_league.png)",
              "", "Zlepšenie = 100 × (MAE_PPG − MAE_model) / MAE_PPG. Kladná hodnota znamená nižšiu chybu modelu.",
              "Rôzna dĺžka sezóny ovplyvňuje absolútnu MAE v bodoch; relatívne zlepšenie voči",
              "ligovému PPG benchmarku je preto užitočné doplnkové porovnanie.",
              "", "## Stabilita exponentu γ medzi ligami", "",
              "Priemer a smerodajná odchýlka z piatich samostatne kalibrovaných foldov:",
              "", "| Liga | Góly bez remíz | xG bez remíz | Góly + remízy | xG + remízy |",
              "| --- | ---: | ---: | ---: | ---: |"]
    by = {m: gammas.loc[gammas.model == f"tuned_{m}"].set_index("league")
          for m in MODEL_TYPES}
    for league in LEAGUE_PROFILES:
        vals = [f"{by[model].loc[league, 'gamma_mean']:.2f} ± {by[model].loc[league, 'gamma_sd']:.2f}" for model in MODEL_TYPES]
        lines.append(f"| {league} | " + " | ".join(vals) + " |")
    lines += ["", "![Optimálne exponenty podľa ligy](gamma_by_league.png)",
              "", "## Párové rozdiely podľa validačných foldov", "",
              "Rozdiel MAE (optimalizované xG+remízy mínus PPG) sa počíta na rovnakých testovacích sezónach.",
              "Záporný rozdiel znamená zlepšenie oproti PPG:",
              "", "| Liga | Priemer rozdielu MAE | SD rozdielu | Foldy s nižšou MAE |",
              "| --- | ---: | ---: | ---: |"]
    for league in LEAGUE_PROFILES:
        vals = paired.loc[(paired.league == league) & (paired.reference == BENCHMARK_MODEL), "delta_mae"]
        lines.append(f"| {league} | {vals.mean():+.3f} | {vals.std(ddof=1):.3f} | {int(vals.lt(0).sum())}/5 |")
    lines += ["", "Týchto päť výsledkov nie je nezávislých pri odhadovaní neistoty, pretože tréningové",
              "množiny sa prekrývajú a ročníky jednej ligy sa môžu podobať. Uvádzame len **opisnú štatistiku**",
              "bez testov významnosti alebo zavádzajúcich intervalov spoľahlivosti.",
              "", "## Chronologický holdout (fold 5)", "",
              "| Liga | γ (xG + remízy) | MAE modelu | MAE PPG |",
              "| --- | ---: | ---: | ---: |"]
    for r in summary.itertuples():
        lines.append(f"| {r.league} | {r.chrono_gamma:.1f} | {r.chrono_mae:.3f} | {r.chrono_ppg_mae:.3f} |")
    lines += ["", "## Obmedzenia", "",
              "- xG pochádza z historického exportu a mohlo byť dodatočne upravené.",
              "- Cieľové body predstavujú 3W + D, nie oficiálnu tabuľku po administratívnych odpočtoch.",
              "- Poradie a Top-4 sú odvodené iba z bodov (pri rovnosti bez oficiálnych pomocných kritérií).",
              "- Ligy sa líšia počtom zápasov; hodnotíme podiel sezóny, nie spoločný počet 19 zápasov.",
              "- Exponenty vybrané pomocou 5-fold CV môžu kolísať; rozdiely nepreukazujú kauzalitu.",
              "- Výber najlepšieho modelu podľa testovacej MAE by si vyžadoval ďalší nezávislý test;",
              "  preto ako hlavný porovnávame **vopred zvolený variant** z Experimentu 03.",
              "", "## Reprodukcia a súbory", "",
              "Spustenie: `python -m football_analysis.experiment_04` po inštalácii závislostí a dodaní",
              "`data/raw/understat/game_stats.csv`. Všetky výsledky sa generujú automaticky.",
              "", "- `league_audit.csv` – validácia kompletnosti všetkých šiestich líg.",
              "- `league_summary.csv` – hlavné medziligové výsledky.",
              "- `overall_metrics.csv`, `fold_metrics.csv` – modelové metriky a validačné foldy.",
              "- `gamma_by_league.csv`, `gamma_tuning.csv` – prehľad a mriežka exponentov.",
              "- `paired_fold_differences.csv` – párové rozdiely oproti PPG a fixnému xG modelu.",
              "- `predictions.csv`, `folds.csv` – jednotlivé predikcie a rozdelenie sezón.",
              "- `mae_by_league.png`, `gamma_by_league.png`, `metadata.json`, `report.md`.", ""]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", nargs="?", type=Path, default=Path("data/raw/understat/game_stats.csv"))
    parser.add_argument("--output", type=Path, default=Path("reports/experiment_04"))
    args = parser.parse_args()
    source = _source_csv(args.source)
    games = load_team_matches(source)
    paired = pair_team_matches(games)
    audit, totals_by_league = audit_snapshot(games, paired)
    grid = make_gamma_grid()
    all_outputs = [[], [], [], [], []]
    for league, totals in totals_by_league.items():
        result = run_league_cv(games, totals, gamma_grid=grid)
        for bucket, table in zip(all_outputs, result):
            bucket.append(table)
        print(f"{league}: {len(totals.season.unique())} seasons, "
              f"{int(totals.played.iloc[0])} matches/team, "
              f"cutoff {int(totals.played.iloc[0])//2}")
    predictions, fold_metrics, tuning, folds, overall = [
        pd.concat(bucket, ignore_index=True) for bucket in all_outputs
    ]
    summary, paired_differences, gammas = summarize_leagues(overall, fold_metrics)
    args.output.mkdir(parents=True, exist_ok=True)
    outputs = {
        "league_audit.csv": audit,
        "league_summary.csv": summary,
        "overall_metrics.csv": overall,
        "fold_metrics.csv": fold_metrics,
        "gamma_by_league.csv": gammas,
        "gamma_tuning.csv": tuning,
        "paired_fold_differences.csv": paired_differences,
        "predictions.csv": predictions,
        "folds.csv": folds,
    }
    for filename, df in outputs.items():
        df.to_csv(args.output / filename, index=False)
    draw_figures(summary, gammas, args.output)
    meta = {
        "experiment": "04", "source_csv": str(source),
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(), "pandas": pd.__version__, "numpy": np.__version__,
        "leagues": LEAGUE_PROFILES, "excluded_from_cv": ["Ligue 1"],
        "reason_excluded": "9 complete seasons, 2019/20 incomplete, 20-to-18 team change in 2023/24",
        "cutoff_rule": "half the completed season", "gamma_grid": grid,
        "validation": "5 season-blocked folds per league, 8 train seasons and 2 test seasons",
        "tuning": "train MAE only, independently for each league and model",
        "draw_calibration": "training seasons only in each league/fold",
        "chronological_holdout": "fold 5, 2022/23 and 2023/24",
        "main_comparison": "tuned_xg_draw versus PPG, designated before Experiment 04",
        "testing_scope": "retrospective cross-validation, folds 1-4 not chronological",
        "outputs": [*outputs, "mae_by_league.png", "gamma_by_league.png", "report.md", "metadata.json"],
    }
    (args.output / "metadata.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    (args.output / "report.md").write_text(
        markdown_report(summary, gammas, paired_differences, audit, candidates=grid), encoding="utf-8",
    )
    print("\nEXPERIMENT 04: five-league comparison")
    print(summary[["league", "primary_mae", "ppg_mae", "mae_improvement_pct", "chrono_gamma"]].to_string(index=False))
    print(f"\nOutputs: {args.output.resolve()}")


if __name__ == "__main__":
    main()
