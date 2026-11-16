"""Experiment 03: five-fold season-blocked CV for the Pythagorean exponent.

Each of five folds holds out two entire seasons (10 complete seasons required).
The other eight seasons select a separate exponent for each of four models,
using training-set MAE only. The draw correction is calculated on those same
training seasons. The fifth fold (latest two seasons) also provides a proper
chronological holdout; the remaining folds are RETROSPECTIVE cross-validation,
not prospective forecasts, since they train on later seasons.

Run from the project root after pip install -e ".[dev,analysis]":
    python -m football_analysis.experiment_03
    python -m football_analysis.experiment_03 data/raw/understat/game_stats.csv
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import platform
from pathlib import Path

import numpy as np
import pandas as pd

from .experiment_02 import _source_csv
from .forecast import forecast_points
from .pythagorean import pythagorean_expectation
from .understat_dataset import complete_seasons, load_team_matches, pair_team_matches


MODEL_TYPES = ("goals_original", "xg_original", "goals_draw", "xg_draw")


def make_gamma_grid(start: float = .5, stop: float = 3.0, step: float = .1) -> tuple[float, ...]:
    if not all(math.isfinite(v) for v in (start, stop, step)) or start <= 0 or step <= 0 or stop < start:
        raise ValueError("Invalid exponent grid limits")
    n = int(math.floor((stop - start) / step + 1e-8)) + 1
    if n < 2 or n > 500:
        raise ValueError("Gamma grid needs 2 to 500 candidate exponents")
    return tuple(round(start + i * step, 8) for i in range(n))


def make_folds(seasons: list[str]) -> list[tuple[int, tuple[str, ...], tuple[str, ...]]]:
    ordered = sorted(str(s) for s in seasons)
    if len(ordered) != 10 or len(set(ordered)) != 10:
        raise ValueError("Exactly 10 distinct complete seasons are required for 5 x (8 train, 2 test) CV")
    result = []
    for i in range(5):
        test = tuple(ordered[2*i:2*i+2])
        train = tuple(s for s in ordered if s not in test)
        result.append((i + 1, train, test))
    return result


def training_draw_rate(totals: pd.DataFrame) -> float:
    played = float(totals.played.sum())
    draws = float(totals.draws.sum())
    if not math.isfinite(played) or not math.isfinite(draws) or played <= 0 or not 0 <= draws <= played:
        raise ValueError("Invalid training draw statistics")
    return draws / played


def model_predictions(rows: pd.DataFrame, kind: str, gamma: float, draw_rate: float) -> np.ndarray:
    if kind not in MODEL_TYPES:
        raise ValueError(f"Unknown model kind: {kind}")
    prefix = "xg" if kind.startswith("xg") else "goals"
    scores = rows[f"observed_{prefix}_for"].to_numpy(dtype=float)
    against = rows[f"observed_{prefix}_against"].to_numpy(dtype=float)
    pe = np.array([pythagorean_expectation(a, b, gamma) for a, b in zip(scores, against)])
    factor = (3.0 - draw_rate) if kind.endswith("_draw") else 3.0
    return rows.observed_points.to_numpy(dtype=float) + factor * (
        rows.season_matches.to_numpy(dtype=float) - rows.observed_played.to_numpy(dtype=float)
    ) * pe


def errors(actual, predicted) -> dict[str, float]:
    diff = np.asarray(predicted, dtype=float) - np.asarray(actual, dtype=float)
    if not diff.size or not np.isfinite(diff).all():
        raise ValueError("Predictions must be finite and nonempty")
    return {"mae": float(np.mean(np.abs(diff))), "rmse": float(np.sqrt(np.mean(diff**2))),
            "bias": float(np.mean(diff))}


def choose_gamma(rows: pd.DataFrame, kind: str, draw_rate: float,
                 gamma_grid: tuple[float, ...]) -> tuple[float, list[dict]]:
    actual = rows.actual_points.to_numpy(dtype=float)
    candidates = []
    for gamma in gamma_grid:
        score = errors(actual, model_predictions(rows, kind, gamma, draw_rate))
        candidates.append({"gamma": gamma, **score})
    # Selection uses TRAIN MAE only; smaller gamma breaks exact ties deterministically.
    best = min(candidates, key=lambda c: (c["mae"], c["gamma"]))
    return float(best["gamma"]), candidates


def add_ranks(predictions: pd.DataFrame) -> pd.DataFrame:
    """Points-only rankings; draws in points use average ranks, not official tie-breaks."""
    df = predictions.copy()
    by = ["fold", "season", "model"]
    df["actual_rank"] = df.groupby(by).actual_points.rank(method="average", ascending=False)
    df["predicted_rank"] = df.groupby(by).predicted_points.rank(method="average", ascending=False)
    df["absolute_rank_error"] = (df.predicted_rank - df.actual_rank).abs()
    return df



def _top_four_overlap(df: pd.DataFrame) -> float:
    """Symmetric Top-4 overlap, including teams tied at fourth place."""
    actual = set(
        df.loc[
            df.actual_points.rank(method="min", ascending=False) <= 4,
            "team"
        ]
    )
    pred = set(
        df.loc[
            df.predicted_points.rank(method="min", ascending=False) <= 4,
            "team"
        ]
    )

    denominator = max(len(actual), len(pred))

    if denominator == 0:
        return float("nan")

    return len(actual & pred) / denominator



def metric_row(df: pd.DataFrame) -> dict[str, float]:
    metric = errors(df.actual_points, df.predicted_points)
    metric["rank_mae"] = float(df.absolute_rank_error.mean())
    metric["top4_overlap"] = float(np.mean([_top_four_overlap(g) for _, g in df.groupby("season")]))
    metric["teams"] = len(df)
    return metric


def run_experiment(matches: pd.DataFrame, totals: pd.DataFrame, *, cutoff: int = 19,
                   gamma_grid: tuple[float, ...] | None = None) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Returns predictions, fold metrics, tuning grid, and season folds."""
    if totals.league.nunique() != 1:
        raise ValueError("Only one league per experiment")
    seasons = sorted(totals.season.astype(str).unique())
    folds = make_folds(seasons)
    gammas = gamma_grid if gamma_grid is not None else make_gamma_grid()
    if not gammas or any(not math.isfinite(g) or g <= 0 for g in gammas):
        raise ValueError("Positive finite gamma candidates are required")
    if not 2.0 in gammas:
        raise ValueError("Include 2.0 in gamma grid to compare with fixed-exponent baseline")
    # This function uses only prefix matches for features; final scores are labels.
    base = forecast_points(matches, totals, cutoff=cutoff, exponent=2.0)
    pred_parts, metric_parts, tuning_parts, fold_parts = [], [], [], []
    for fold, train_seasons, test_seasons in folds:
        train = base.loc[base.season.astype(str).isin(train_seasons)]
        test = base.loc[base.season.astype(str).isin(test_seasons)].copy()
        train_totals = totals.loc[totals.season.astype(str).isin(train_seasons)]
        draw_rate = training_draw_rate(train_totals)
        if train.empty or test.empty or len(train) + len(test) != len(base):
            raise ValueError("Incomplete split")
        fold_parts.append({"fold": fold, "train_seasons": ",".join(train_seasons),
                           "test_seasons": ",".join(test_seasons),
                           "train_team_seasons": len(train), "test_team_seasons": len(test),
                           "training_draw_rate": draw_rate,
                           "chronological_holdout": max(train_seasons) < min(test_seasons)})
        for kind in MODEL_TYPES:
            chosen, candidates = choose_gamma(train, kind, draw_rate, gammas)
            for c in candidates:
                tuning_parts.append({"fold": fold, "model": kind, **c,
                                     "selected": c["gamma"] == chosen, "train_rows": len(train)})
            for mode, gamma in (("tuned", chosen), ("fixed", 2.0)):
                name = f"{mode}_{kind}"
                output = test[["league", "season", "team", "observed_points", "actual_points",
                               "season_matches", "cutoff_date"]].copy()
                output["fold"] = fold
                output["model"] = name
                output["gamma"] = gamma
                output["training_draw_rate"] = draw_rate
                output["predicted_points"] = model_predictions(test, kind, gamma, draw_rate)
                pred_parts.append(output)
        ppg = test[["league", "season", "team", "observed_points", "actual_points",
                    "season_matches", "cutoff_date"]].copy()
        ppg["fold"], ppg["model"], ppg["gamma"], ppg["training_draw_rate"] = fold, "ppg", np.nan, draw_rate
        ppg["predicted_points"] = test.predicted_ppg.to_numpy(dtype=float)
        pred_parts.append(ppg)

    predictions = add_ranks(pd.concat(pred_parts, ignore_index=True))
    tuning = pd.DataFrame(tuning_parts)
    for (fold, name), g in predictions.groupby(["fold", "model"], sort=True):
        metric_parts.append({"fold": fold, "model": name, "gamma": float(g.gamma.iloc[0]),
                             "training_draw_rate": float(g.training_draw_rate.iloc[0]),
                             **metric_row(g)})
    fold_metrics = pd.DataFrame(metric_parts).sort_values(["model", "fold"]).reset_index(drop=True)
    folds_df = pd.DataFrame(fold_parts)
    # Critical invariants: each model gets each team-season once, no duplicates across folds.
    for _, group in predictions.groupby("model"):
        if len(group) != len(base) or group.duplicated(["league", "season", "team"]).any():
            raise ValueError("All models must predict each complete team-season exactly once")
    return predictions, fold_metrics, tuning, folds_df


def overall_metrics(predictions: pd.DataFrame, fold_metrics: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for name, group in predictions.groupby("model", sort=True):
        fold = fold_metrics.loc[fold_metrics.model == name]
        rows.append({"model": name, **metric_row(group),
                     "fold_mae_mean": float(fold.mae.mean()),
                     "fold_mae_sd": float(fold.mae.std(ddof=1)),
                     "fold_rmse_mean": float(fold.rmse.mean())})
    return pd.DataFrame(rows).sort_values("mae").reset_index(drop=True)


def markdown_report(metrics: pd.DataFrame, fold_metrics: pd.DataFrame,
                    folds: pd.DataFrame, *, league: str, cutoff: int, gamma_grid: tuple[float, ...]) -> str:
    lines = [f"# Experiment 03 – optimalizácia Pytagorovho exponentu ({league})", "",
             "## Cieľ a metodika", "",
             f"Predikcia konečných bodov po prvých **{cutoff}** zápasoch pomocou gólov a xG.",
             "Päťnásobná validácia je rozdelená **po celých sezónach**: vždy 8 sezón na",
             "optimalizáciu exponentu a odhad historického podielu remíz, 2 sezóny na hodnotenie.",
             f"Mriežka exponentov: **{min(gamma_grid):g}–{max(gamma_grid):g}**, spolu {len(gamma_grid)} kandidátov.",
             "Exponent sa vyberá výhradne podľa **MAE na tréningových sezónach**.",
             "Samostatne optimalizujeme štyri varianty: góly/xG × bez korekcie/s korekciou remíz.",
             "Na testoch porovnávame optimalizované modely, pevné γ = 2 a PPG.",
             "", "**Dôležité:** Toto je retrospektívna 5-fold CV, nie 5 nezávislých budúcich predikcií.",
             "V prvých 4 foldoch trénovanie obsahuje aj sezóny neskoršie než testovacie.",
             "Iba fold 5 (posledné dve sezóny) je chronologický holdout vhodný ako",
             "reálnejšie vyhodnotenie časovej generalizácie. Predikčné vstupy pre tím",
             "obsahujú len jeho prvých k zápasov; výstupy za celú sezónu sú iba cieľové hodnoty.",
             "", "## Výsledky naprieč všetkými piatimi foldmi", "",
             "| Model | MAE | RMSE | Bias | MAE priemer foldov ± SD | MAE poradia |",
             "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for r in metrics.itertuples():
        lines.append(f"| {r.model} | {r.mae:.3f} | {r.rmse:.3f} | {r.bias:+.3f} | {r.fold_mae_mean:.3f} ± {r.fold_mae_sd:.3f} | {r.rank_mae:.3f} |")
    lines += ["", "## Rozdelenie sezón", "", "| Fold | Tréningové sezóny | Testovacie sezóny | Podiel remíz z tréningu | Chronologický holdout |",
              "| --- | --- | --- | ---: | --- |"]
    for f in folds.itertuples():
        lines.append(f"| {f.fold} | {f.train_seasons} | {f.test_seasons} | {f.training_draw_rate:.4f} | {'Áno' if f.chronological_holdout else 'Nie'} |")
    lines += ["", "## Chronologický holdout (fold 5)", "",
              "| Model | γ | MAE | RMSE |", "| --- | ---: | ---: | ---: |"]
    for r in fold_metrics.loc[fold_metrics.fold == 5].sort_values("mae").itertuples():
        lines.append(f"| {r.model} | {r.gamma if math.isfinite(r.gamma) else '—'} | {r.mae:.3f} | {r.rmse:.3f} |")
    lines += ["", "## Obmedzenia", "",
              "- xG je historický export a nebolo overené, že hodnoty neprešli revíziami.",
              "- Poradie je určené **len bodmi**, remízy v počte bodov dostanú priemerné poradie;",
              "  to nemusí zodpovedať oficiálnej tabuľke s kritériami skóre/vzájomných zápasov.",
              "- Top-4 prekrytie zohľadňuje aj remízy v bodoch na hranici 4. miesta.",
              "- Používa symetrickú metriku: prienik Top-4 množín delený veľkosťou väčšej množiny.",
              "- Foldové výsledky nie sú nezávislé (prekrývajúce sa tréningové množiny).",
              "- Fixný γ=2 v tomto experimente vyhodnocujeme na všetkých 10 sezónach, preto jeho",
              "  metriky nemožno priamo stotožniť s výsledkami Experimentu 02 (9 sezón).",
              "", "## Výstupy", "", "`predictions.csv`, `fold_metrics.csv`, `overall_metrics.csv`,",
              "`gamma_tuning.csv`, `folds.csv`, `metadata.json`, `report.md`,",
              "`mae_comparison.png`, `gamma_by_fold.png`.",
              "", "Spustenie: `python -m football_analysis.experiment_03`."]
    return "\n".join(lines) + "\n"



def draw_figures(overall: pd.DataFrame, fold_metrics: pd.DataFrame, output: Path) -> None:
    """Save comparison and gamma-stability charts without changing numeric results."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    with plt.rc_context({"font.family": "DejaVu Sans", "font.size": 10}):
        fig, ax = plt.subplots(figsize=(10, 5.8), layout="constrained")
        display = overall.sort_values("mae", ascending=False)
        bars = ax.barh(display.model, display.mae)
        ax.bar_label(bars, labels=[f"{n:.3f}" for n in display.mae], padding=4)
        ax.set(xlabel="MAE (body, nižšie = lepšie)", title="Experiment 03 – 5-fold CV: porovnanie predikčných modelov")
        ax.grid(axis="x", alpha=.2)
        ax.set_axisbelow(True)
        ax.set_xlim(0, float(display.mae.max()) * 1.15)
        fig.savefig(output / "mae_comparison.png", dpi=160)
        plt.close(fig)

        fig, ax = plt.subplots(figsize=(10, 5.3), layout="constrained")
        for model in MODEL_TYPES:
            group = fold_metrics.loc[fold_metrics.model == f"tuned_{model}"].sort_values("fold")
            ax.plot(group.fold, group.gamma, marker="o", label=model)
        ax.set(xlabel="Fold (1–4: retrospektívne, 5: chronologický holdout)",
               ylabel="Zvolený exponent γ", title="Experiment 03 – optimalizovaný exponent podľa foldu",
               xticks=(1, 2, 3, 4, 5))
        ax.grid(alpha=.2)
        ax.legend(fontsize=9)
        fig.savefig(output / "gamma_by_fold.png", dpi=160)
        plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", nargs="?", type=Path, default=Path("data/raw/understat/game_stats.csv"))
    parser.add_argument("--league", default="EPL")
    parser.add_argument("--teams", type=int, default=20)
    parser.add_argument("--cutoff", type=int, default=19)
    parser.add_argument("--output", type=Path, default=Path("reports/experiment_03"))
    args = parser.parse_args()
    csv = _source_csv(args.source)
    matches = load_team_matches(csv)
    paired = pair_team_matches(matches)
    totals, selection = complete_seasons(matches, paired, args.league, expected_teams=args.teams)
    gamma_grid = make_gamma_grid()
    predictions, folds_metrics, tuning, folds = run_experiment(matches, totals,
                                                              cutoff=args.cutoff, gamma_grid=gamma_grid)
    overall = overall_metrics(predictions, folds_metrics)
    args.output.mkdir(exist_ok=True, parents=True)
    predictions.to_csv(args.output / "predictions.csv", index=False)
    folds_metrics.to_csv(args.output / "fold_metrics.csv", index=False)
    tuning.to_csv(args.output / "gamma_tuning.csv", index=False)
    folds.to_csv(args.output / "folds.csv", index=False)
    overall.to_csv(args.output / "overall_metrics.csv", index=False)
    selection.to_csv(args.output / "season_selection.csv", index=False)
    draw_figures(overall, folds_metrics, args.output)
    metadata = {"experiment": "03", "league": args.league, "teams_expected": args.teams,
                "source_csv_sha256": hashlib.sha256(csv.read_bytes()).hexdigest(),
                "experiment_03_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "run_utc": datetime.now(timezone.utc).isoformat(),
                "python": platform.python_version(), "pandas": pd.__version__, "numpy": np.__version__,
                "cutoff": args.cutoff, "gamma_candidates": gamma_grid,
                "selection_objective": "train MAE", "validation": "5-fold blocked by season, 8 train / 2 test",
                "calibration": "draw share from TRAIN seasons only in each fold",
                "calendar_note": "folds 1-4 may train on seasons after held-out seasons (retrospective CV)",
                "real_future_holdout": "fold 5 (last 2 seasons)",
                "rank_definition": "points-only, average rank for ties", "source_csv": str(csv)}
    (args.output / "metadata.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    (args.output / "report.md").write_text(markdown_report(overall, folds_metrics, folds, league=args.league,
                                           cutoff=args.cutoff, gamma_grid=gamma_grid), encoding="utf-8")
    print("Experiment 03 – five-fold season-blocked validation")
    print(overall[["model", "mae", "rmse", "bias", "rank_mae"]].to_string(index=False))
    print(f"Outputs: {args.output.resolve()}")


if __name__ == "__main__":
    main()
