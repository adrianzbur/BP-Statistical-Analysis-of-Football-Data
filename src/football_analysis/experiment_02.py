"""Experiment 02: draw-adjusted Pythagorean forecasts of season-end points.

The draw-rate calibration is strictly historical: for a target season only
completed, earlier seasons in the same selected league are used. Experiment 01
is kept intact, and all comparison models use identical test team-seasons.

Usage from the project root (after ``pip install -e '.[dev,analysis]'``)::

    python -m football_analysis.experiment_02
    python -m football_analysis.experiment_02 data/raw/understat/game_stats.csv
    python -m football_analysis.experiment_02 data/raw/Understat-data.zip
"""

import argparse
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
import math
from pathlib import Path
import platform
import subprocess

import numpy as np
import pandas as pd

from .experiment_02_reporting import compare_models, draw_figures, markdown_report
from .forecast import forecast_points
from .metrics import mean_absolute_error, root_mean_squared_error
from .understat_dataset import complete_seasons, load_team_matches, pair_team_matches


MODEL_COLUMNS = {
    "goals_original": "predicted_goals",
    "xg_original": "predicted_xg",
    "goals_draw": "predicted_goals_draw",
    "xg_draw": "predicted_xg_draw",
    "ppg": "predicted_ppg",
}


def historical_draw_rate(totals: pd.DataFrame, season: str) -> float:
    """Return prior-season draw share (drawn team-games / all team-games).

    ``totals`` must contain complete seasons of one league. Each match has two
    team records; both numerator and denominator count team records, so the
    resulting share equals the fraction of matches ending in draws. A weighted
    ratio is used instead of an unweighted average of seasonal draw rates.
    """
    history = totals.loc[totals["season"].astype(str) < str(season)]
    if history.empty:
        raise ValueError(f"No completed season before {season} for draw calibration")
    played = float(history["played"].sum())
    draws = float(history["draws"].sum())
    if not (math.isfinite(played) and math.isfinite(draws) and played > 0
            and 0 <= draws <= played):
        raise ValueError("Invalid historical played/draw counts")
    return draws / played


def corrected_points(observed_points, original_prediction, draw_rate: float):
    """Replace 3 points/match scaling with (3 - historical_draw_share).

    The original prediction is ``observed_points + 3*remaining*PE``. Only the
    *future-points* component is adjusted; already earned points are unchanged.
    Inputs may be scalars or pandas Series for vectorized calculation.

    This is a simple league-average draw correction, NOT a separate estimate
    of each team's win and draw probabilities (as in Hamilton's model).
    """
    if not isinstance(draw_rate, (int, float)) or not math.isfinite(draw_rate) or not 0 <= draw_rate <= 1:
        raise ValueError("Historical draw rate must be a finite number in [0, 1]")
    return observed_points + (original_prediction - observed_points) * (3.0 - draw_rate) / 3.0


def summarize_predictions(predictions: pd.DataFrame) -> pd.DataFrame:
    """Calculate MAE, RMSE and signed bias on exactly the same test rows."""
    rows = []
    groups = [(str(season), group) for season, group in predictions.groupby("season")]
    groups.append(("ALL", predictions))
    for season, group in groups:
        for model, column in MODEL_COLUMNS.items():
            actual = group["actual_points"]
            predicted = group[column]
            rows.append({
                "season": season,
                "model": model,
                "teams": len(group),
                "mae": mean_absolute_error(actual, predicted),
                "rmse": root_mean_squared_error(actual, predicted),
                "bias": float((predicted - actual).mean()),
            })
    return pd.DataFrame(rows)


def run_experiment(matches: pd.DataFrame, totals: pd.DataFrame, *, cutoff: int = 19,
                   exponent: float = 2.0) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Forecast every season after the earliest historical training season.

    ``matches`` are validated team-match rows and ``totals`` are the validated
    complete seasons produced by ``complete_seasons`` for one league.
    """
    if totals["league"].nunique() != 1:
        raise ValueError("Experiment 02 expects complete seasons of exactly one league")
    if not totals["season"].astype(str).str.fullmatch(r"\d{4}").all():
        raise ValueError("Season labels must be four-digit start years")
    seasons = sorted(totals["season"].astype(str).unique())
    if len(seasons) < 2:
        raise ValueError("At least two complete seasons are needed (train and test)")

    predictions, calibration = [], []
    for season in seasons[1:]:
        history = totals.loc[totals["season"].astype(str) < season]
        draw_rate = historical_draw_rate(totals, season)
        season_totals = totals.loc[totals["season"].astype(str) == season]
        current = forecast_points(matches, season_totals, cutoff=cutoff, exponent=exponent)
        historical_matches = matches.loc[
            matches["league"].eq(totals["league"].iloc[0])
            & matches["season"].astype(str).isin(history["season"].astype(str))
        ]
        history_end = pd.to_datetime(historical_matches["date"]).max()
        earliest_cutoff = current["cutoff_date"].min()
        if pd.isna(history_end) or history_end >= earliest_cutoff:
            raise ValueError("Historical calibration must finish before every forecast cutoff")
        current["historical_draw_rate"] = draw_rate
        current["points_per_match_factor"] = 3.0 - draw_rate
        for model in ("goals", "xg"):
            current[f"predicted_{model}_draw"] = corrected_points(
                current["observed_points"], current[f"predicted_{model}"], draw_rate
            )
            current[f"error_{model}_draw"] = current[f"predicted_{model}_draw"] - current["actual_points"]
        predictions.append(current)
        calibration.append({
            "season": season,
            "training_first_season": seasons[0],
            "training_last_season": str(history["season"].max()),
            "training_seasons": len(history["season"].unique()),
            "training_matches": int(history["played"].sum() / 2),
            "training_draws": int(history["draws"].sum() / 2),
            "training_last_match_date": history_end,
            "earliest_forecast_date": earliest_cutoff,
            "historical_draw_rate": draw_rate,
            "points_per_match_factor": 3.0 - draw_rate,
        })

    result = pd.concat(predictions, ignore_index=True)
    return result, summarize_predictions(result), pd.DataFrame(calibration)


def _source_csv(source: Path) -> Path:
    if source.is_dir():
        csv = source / "game_stats.csv"
    elif source.suffix.lower() == ".zip":
        # Compatible with the original archive used by Experiment 01.
        from .pilot import extract_inputs
        csv = extract_inputs(source) / "game_stats.csv"
    else:
        csv = source
    if not csv.is_file():
        raise FileNotFoundError(f"Cannot find game_stats.csv: {csv}")
    return csv


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", nargs="?", type=Path,
                        default=Path("data/raw/understat/game_stats.csv"),
                        help="Existing game_stats.csv, its directory or original Understat ZIP")
    parser.add_argument("--cutoff", type=int, default=19)
    parser.add_argument("--exponent", type=float, default=2.0)
    parser.add_argument("--output", type=Path, default=Path("reports/experiment_02"))
    args = parser.parse_args()

    csv = _source_csv(args.source)
    games = load_team_matches(csv)
    paired = pair_team_matches(games)
    totals, selection = complete_seasons(games, paired, "EPL", expected_teams=20)
    predictions, metrics, calibration = run_experiment(
        games, totals, cutoff=args.cutoff, exponent=args.exponent
    )
    comparisons = compare_models(metrics)
    selection["role"] = "excluded"
    selection.loc[selection["included"], "role"] = "calibration_only"
    selection.loc[selection["season"].isin(calibration["season"]), "role"] = "evaluation"
    args.output.mkdir(parents=True, exist_ok=True)
    predictions.to_csv(args.output / "predictions.csv", index=False)
    metrics.to_csv(args.output / "metrics.csv", index=False)
    calibration.to_csv(args.output / "calibration.csv", index=False)
    selection.to_csv(args.output / "season_selection.csv", index=False)
    comparisons.to_csv(args.output / "comparisons.csv", index=False)
    draw_figures(metrics, calibration, args.output)

    try:
        revision = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
        dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], text=True).strip())
    except (OSError, subprocess.CalledProcessError):
        revision, dirty = None, None

    metadata = {
        "experiment": "02", "method": "historical draw-adjusted Pythagorean share",
        "source_csv": str(csv),
        "source_csv_sha256": hashlib.sha256(csv.read_bytes()).hexdigest(),
        "code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "module_sha256": {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(Path(__file__).parent.glob("*.py"))
        },
        "git_revision": revision, "git_dirty": dirty,
        "python": platform.python_version(), "pandas": pd.__version__,
        "numpy": np.__version__, "matplotlib": version("matplotlib"),
        "source_url": "https://www.kaggle.com/datasets/codytipton/understat-data",
        "analysis_utc": datetime.now(timezone.utc).isoformat(),
        "league": "EPL", "exponent": args.exponent, "cutoff": args.cutoff,
        "training_first_season": str(calibration.iloc[0].training_first_season),
        "test_seasons": calibration["season"].astype(str).tolist(),
        "team_seasons_tested": len(predictions),
        "draw_rate_formula": "sum(prior season draws) / sum(prior season played)",
        "draw_adjustment": "observed + (3 - d_hist) * (season_matches - cutoff) * PE",
        "original_formula": "observed + 3 * (season_matches - cutoff) * PE",
        "point_target": "points earned from results (3W + D), no administrative deductions",
        "selection_rule": "complete 20-team double round-robin EPL seasons",
        "leakage_prevention": "draw rate based on prior completed seasons only; features from first cutoff matches per team",
        "calendar_check": "last calibration match strictly precedes every forecast cutoff",
        "comparison_rule": "all five models evaluated on identical team-seasons; no full Experiment 01 aggregate comparison",
        "uncertainty": "descriptive results only; no claim of statistical significance",
        "outputs": ["predictions.csv", "metrics.csv", "calibration.csv", "comparisons.csv",
                    "season_selection.csv", "model_comparison.png", "mae_by_season.png", "report.md", "metadata.json"],
    }
    (args.output / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (args.output / "report.md").write_text(
        markdown_report(metrics, calibration, comparisons, selection, cutoff=args.cutoff, exponent=args.exponent),
        encoding="utf-8"
    )
    print("EXPERIMENT 02: draw correction (same test set for all models)")
    print(metrics.loc[metrics["season"] == "ALL"].to_string(index=False))
    print(f"\nOutputs: {args.output.resolve()}")


if __name__ == "__main__":
    main()
