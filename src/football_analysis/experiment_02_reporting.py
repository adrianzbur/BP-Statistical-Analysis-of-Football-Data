"""Tables and figures for Experiment 02, derived from saved evaluation metrics."""

from pathlib import Path

import pandas as pd


LABELS = {
    "goals_original": "Góly – pôvodný model",
    "xg_original": "xG – pôvodný model",
    "goals_draw": "Góly – korekcia remíz",
    "xg_draw": "xG – korekcia remíz",
    "ppg": "Bodový priemer (PPG)",
}
PAIRS = (("goals_draw", "goals_original"), ("xg_draw", "xg_original"), ("xg_draw", "ppg"))


def season_label(season: str) -> str:
    return f"{season}/{str(int(season) + 1)[-2:]}"


def compare_models(metrics: pd.DataFrame) -> pd.DataFrame:
    """Paired model differences; negative delta means lower candidate error."""
    rows = []
    for season, group in metrics.groupby("season", sort=False):
        indexed = group.set_index("model")
        if not indexed.index.is_unique:
            raise ValueError("Each season must contain each model exactly once")
        if indexed["teams"].nunique() != 1:
            raise ValueError("Comparison models must have equal observation counts")
        for candidate, reference in PAIRS:
            a, b = indexed.loc[candidate], indexed.loc[reference]
            rows.append({
                "season": season, "candidate": candidate, "reference": reference,
                "teams": int(a.teams), "delta_mae": a.mae - b.mae,
                "delta_rmse": a.rmse - b.rmse,
                "mae_reduction_percent": 100 * (b.mae - a.mae) / b.mae if b.mae else None,
            })
    return pd.DataFrame(rows)


def draw_figures(metrics: pd.DataFrame, calibration: pd.DataFrame, output: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    models = list(LABELS)
    colors = ["#93b9df", "#edb17b", "#2563a6", "#c86b22", "#39846b"]
    overall = metrics.loc[metrics.season == "ALL"].set_index("model").loc[models]
    seasons = calibration.season.astype(str).tolist()
    period = f"{season_label(seasons[0])} – {season_label(seasons[-1])}"
    with plt.rc_context({"font.family": "DejaVu Sans", "font.size": 10,
                         "axes.spines.top": False, "axes.spines.right": False}):
        fig, axes = plt.subplots(1, 3, figsize=(13.8, 5.3), layout="constrained", sharey=True)
        for ax, metric, title in zip(axes, ("mae", "rmse", "bias"),
                                    ("MAE · nižšie je lepšie", "RMSE · nižšie je lepšie", "Bias · bližšie k nule je lepšie")):
            values = overall[metric].to_numpy()
            bars = ax.barh(range(len(models)), values, color=colors, height=0.62)
            ax.set_yticks(range(len(models)), [LABELS[m] for m in models])
            ax.bar_label(bars, labels=[f"{v:+.3f}" if metric == "bias" else f"{v:.3f}" for v in values], padding=5)
            ax.set(title=title, xlabel="Body")
            ax.axvline(0, color="#68727c", linewidth=0.8)
            ax.grid(axis="x", alpha=0.15)
            ax.set_axisbelow(True)
            if metric == "bias":
                ax.set_xlim(min(0, min(values)) - .9, max(0, max(values)) + .9)
            else:
                ax.set_xlim(0, max(values) * 1.25)
        axes[0].invert_yaxis()
        fig.suptitle(f"Experiment 02 · EPL {period}\nRovnakých {int(overall.teams.iloc[0])} tímových sezón pre všetky modely", fontsize=14)
        fig.savefig(output / "model_comparison.png", dpi=170)
        plt.close(fig)

        fig, axes = plt.subplots(1, 2, figsize=(13, 5.6), layout="constrained", sharey=True)
        for ax, feature, color, title in zip(axes, ("goals", "xg"), ("#2563a6", "#c86b22"), ("Model z gólov", "Model z xG")):
            for model, style, line_color, label in (
                (f"{feature}_original", "--", color, "Pôvodný model"),
                (f"{feature}_draw", "-", color, "Korekcia remíz"),
                ("ppg", "-", "#39846b", "Bodový priemer (PPG)"),
            ):
                group = metrics.loc[(metrics.model == model) & (metrics.season != "ALL")].sort_values("season")
                ax.plot([season_label(str(s)) for s in group.season], group.mae, linestyle=style,
                        color=line_color, marker="o", markersize=4, label=label)
            ax.set(title=title, ylabel="MAE v bodoch", ylim=(0, None))
            ax.tick_params(axis="x", rotation=45)
            ax.grid(axis="y", alpha=0.2)
            ax.legend(fontsize=9, loc="lower left")
        fig.suptitle("Experiment 02 · Vplyv korekcie remíz podľa sezóny", fontsize=14)
        fig.savefig(output / "mae_by_season.png", dpi=170)
        plt.close(fig)


def markdown_report(metrics: pd.DataFrame, calibration: pd.DataFrame,
                    comparisons: pd.DataFrame, selection: pd.DataFrame,
                    *, cutoff: int, exponent: float) -> str:
    overall = metrics.loc[metrics.season == "ALL"].set_index("model")
    seasons = sorted(calibration.season.astype(str))
    first_training = str(calibration.iloc[0].training_first_season)
    teams = int(overall.teams.iloc[0])
    table = ["| Model | MAE (body) | RMSE (body) | Bias (body) |", "| --- | ---: | ---: | ---: |"]
    for model, label in LABELS.items():
        row = overall.loc[model]
        table.append(f"| {label} | {row.mae:.3f} | {row.rmse:.3f} | {row.bias:+.3f} |")

    by_season = metrics.loc[metrics.season != "ALL"].pivot(index="season", columns="model", values="mae")
    season_table = ["| Sezóna | Góly pôvodné | Góly s korekciou | xG pôvodné | xG s korekciou | PPG |",
                    "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for season, row in by_season.iterrows():
        season_table.append(f"| {season_label(str(season))} | {row.goals_original:.3f} | {row.goals_draw:.3f} | {row.xg_original:.3f} | {row.xg_draw:.3f} | {row.ppg:.3f} |")

    comparison_table = ["| Model oproti referencii | Zmena MAE | Zmena RMSE | Zníženie MAE | Sezóny s nižšou MAE |",
                        "| --- | ---: | ---: | ---: | ---: |"]
    for candidate, reference in PAIRS:
        rows = comparisons.loc[(comparisons.candidate == candidate) & (comparisons.reference == reference)]
        total = rows.loc[rows.season == "ALL"].iloc[0]
        wins = int(rows.loc[rows.season != "ALL", "delta_mae"].lt(0).sum())
        comparison_table.append(f"| {LABELS[candidate]} oproti {LABELS[reference]} | {total.delta_mae:+.3f} | {total.delta_rmse:+.3f} | {total.mae_reduction_percent:.2f} % | {wins}/{len(seasons)} |")

    cal_table = ["| Hodnotená sezóna | Historické sezóny | Zápasy | Remízy | d_hist | Faktor 3 − d_hist |",
                 "| --- | --- | ---: | ---: | ---: | ---: |"]
    for row in calibration.itertuples():
        cal_table.append(f"| {season_label(str(row.season))} | {row.training_first_season}–{row.training_last_season} | {row.training_matches} | {row.training_draws} | {row.historical_draw_rate:.4f} | {row.points_per_match_factor:.4f} |")
    excluded = ", ".join(season_label(str(s)) for s in selection.loc[~selection.included, "season"])
    xg_vs_ppg = comparisons.loc[(comparisons.season == "ALL") & (comparisons.candidate == "xg_draw") & (comparisons.reference == "ppg")].iloc[0]
    return f"""# Experiment 02: korekcia remíz v Pythagorejskom modeli

## Cieľ a rozsah

Overiť, či historický podiel remíz zlepší predikciu bodov pri pevnom exponente
**{exponent:g}**. Použitý je rovnaký lokálny Understat export ako v Experimente 01:
https://www.kaggle.com/datasets/codytipton/understat-data .

Hodnotíme **EPL {season_label(seasons[0])} – {season_label(seasons[-1])}**:
{len(seasons)} úplných sezón, **{teams} tímových sezón**, vždy 20 tímov a 38 zápasov.
Ročník **{season_label(first_training)}** je iba prvá kalibrácia. Vylúčené neúplné
ročníky: **{excluded or 'žiadne'}**. Presné zaradenie je v `season_selection.csv`.
Pri neskorších predikciách sa kalibrácia rozširuje o všetky už ukončené sezóny.

**Všetkých päť modelov používa identické hodnotené riadky.** Pôvodné modely
z Experimentu 01 sú prepočítané na tejto menšej vzorke. Ich výsledky nemožno
priamo porovnávať s pôvodným súhrnom za 200 tímových sezón.

## Metodika

Z prvých **{cutoff}** zápasov každého tímu spočítame góly/xG a získané body.
`N` je známy počet zápasov sezóny (38), `k` počet už odohraných zápasov.
Predikujeme konečný počet bodov:

```text
PE = GF^gamma / (GF^gamma + GA^gamma)
P_original = P_observed + 3 * (N - k) * PE
P_draw = P_observed + (3 - d_hist) * (N - k) * PE
P_PPG = N * P_observed / k
```

Pre xG model nahradíme GF/GA hodnotami xGF/xGA. Exponent `gamma = {exponent:g}`
sa v tomto experimente neladí. PPG pri 19 z 38 zápasov jednoducho zdvojnásobí
už získané body; predpokladá rovnaké bodové tempo v zostávajúcej časti sezóny.
Korekcia mení iba odhad budúcich bodov, už získané body ostávajú nezmenené.

`d_hist = sum(draws) / sum(played)` používame iba z úplných predchádzajúcich
sezón EPL. Dva tímové pohľady na každý zápas sa v pomere vykrátia.
Pri remíze sa rozdelia 2 body, pri rozhodnutom zápase 3, teda historický
priemer celkových rozdelených bodov je `3 - d_hist`.
Násobenie týmto faktorom je **empirická ligová korekcia**. Nie je to samostatný
pravdepodobnostný model výhier a remíz a nevynucuje presný ligový súčet bodov.

## Ochrana pred použitím budúcich informácií

- Kalibrácia používa len predchádzajúce ročníky; podiel remíz hodnotenej sezóny
  do nej nevstupuje. Posledný kalibračný zápas musí byť pred dátumom každej predikcie.
- Góly, xG a body tímu pochádzajú iba z prvých `k` chronologických zápasov.
- Konečné body sú len cieľom vyhodnotenia. Testy menia budúce výsledky a
  overujú, že skoršie predikcie a ich kalibrácia ostanú rovnaké.
- Každý tím má vlastný `cutoff_date`; nejde o spoločný deň alebo oficiálne kolo.

**Cieľ = body zo zápasov (3W + D), pred administratívnymi odpočtami.**
Dataset neobsahuje históriu sankcií ani oficiálnu konečnú tabuľku po odpočtoch.

## Celkové výsledky

{chr(10).join(table)}

Nižšie MAE a RMSE sú lepšie. Bias je priemer (predikcia − skutočnosť):
kladný znamená nadhodnotenie, záporný podhodnotenie. Metriky sú v bodoch.
Súhrn počíta chyby zo všetkých {teams} riadkov; celkové RMSE nie je aritmetický
priemer sezónnych RMSE. Predikcie sa pred výpočtom metrík nezaokrúhľujú.

![Porovnanie modelov](model_comparison.png)

## Zmena oproti pôvodným modelom a PPG

{chr(10).join(comparison_table)}

Zmena = korigovaný model mínus referencia; záporná zmena znamená zlepšenie.
xG s korekciou má oproti PPG o **{xg_vs_ppg.mae_reduction_percent:.2f} % nižšiu
MAE** v súhrne. Výhoda však nie je rovnaká v každej sezóne.
Kladný pôvodný bias sa po korekcii mení na mierne podhodnocovanie; korekcia
teda systematickú chybu úplne neodstraňuje.

## MAE po sezónach

{chr(10).join(season_table)}

RMSE a bias po sezónach sú tiež uložené v `metrics.csv`.

![MAE po sezónach](mae_by_season.png)

## Historická kalibrácia

{chr(10).join(cal_table)}

`calibration.csv` uvádza aj dátum posledného historického zápasu a najskorší
dátum predikcie v cieľovej sezóne, aby bolo možné skontrolovať časové oddelenie.

## Interpretácia a obmedzenia

Korekcia zlepšuje zvolený historický benchmark. Zatiaľ ide o **opisné
výsledky jednej ligy**, bez tvrdenia štatistickej významnosti alebo kauzality.
Tímové sezóny nie sú nezávislé pozorovania a máme len {len(seasons)} hodnotených
ročníkov. Model explicitne nezohľadňuje zostávajúcich súperov, domáce prostredie
ani rozdielnu náchylnosť tímov na remízy. Historický export xG môže zahŕňať revízie,
ktoré v deň pôvodnej predikcie ešte neboli dostupné.

Experiment 02 je samostatný test korekcie pri pevnom exponente. Nasledujúci
Experiment 03 podľa pokynov konzultanta má optimalizovať exponent po ligách,
použiť validáciu po celých sezónach (pri desiatich úplných ročníkoch 5 behov
8 tréningových + 2 testovacie) a porovnať predikované poradie tímov s realitou.
Táto 5-násobná validácia nie je automaticky chronologická predikcia; pri jej
príprave treba presne oddeliť kalibráciu parametrov od testovacích sezón.

## Reprodukcia a výstupy

Z koreňa projektu, vo virtuálnom prostredí:

```text
python -m pip install -e ".[dev,analysis]"
python -m football_analysis.experiment_02
python -m pytest
```

CLI prijíma aj cestu k CSV, jeho priečinku alebo pôvodnému ZIP.
Výstupy sú v `reports/experiment_02`:

- `predictions.csv`: jednotlivé odhady, skutočné body, chyby a historický faktor.
- `metrics.csv`: MAE/RMSE/bias za každý model a sezónu aj súhrnne.
- `comparisons.csv`: rozdiely chýb a percentuálne zmeny na rovnakej vzorke.
- `calibration.csv`, `season_selection.csv`: história kalibrácie a výber sezón.
- `model_comparison.png`, `mae_by_season.png`: grafy odvodené z rovnakých metrík.
- `metadata.json`: hash vstupu a modulov, parametre, verzie knižníc a Git revízia.

Originálne dáta ostávajú lokálne; do commitu patria kód, testy, dokumentácia
a kompaktné výsledky experimentu. Výsledky Experimentu 01 sa nemenia.
"""
