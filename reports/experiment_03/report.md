# Experiment 03 – optimalizácia Pytagorovho exponentu (EPL)

## Cieľ a metodika

Predikcia konečných bodov po prvých **19** zápasoch pomocou gólov a xG.
Päťnásobná validácia je rozdelená **po celých sezónach**: vždy 8 sezón na
optimalizáciu exponentu a odhad historického podielu remíz, 2 sezóny na hodnotenie.
Mriežka exponentov: **0.5–3**, spolu 26 kandidátov.
Exponent sa vyberá výhradne podľa **MAE na tréningových sezónach**.
Samostatne optimalizujeme štyri varianty: góly/xG × bez korekcie/s korekciou remíz.
Na testoch porovnávame optimalizované modely, pevné γ = 2 a PPG.

**Dôležité:** Toto je retrospektívna 5-fold CV, nie 5 nezávislých budúcich predikcií.
V prvých 4 foldoch trénovanie obsahuje aj sezóny neskoršie než testovacie.
Iba fold 5 (posledné dve sezóny) je chronologický holdout vhodný ako
reálnejšie vyhodnotenie časovej generalizácie. Predikčné vstupy pre tím
obsahujú len jeho prvých k zápasov; výstupy za celú sezónu sú iba cieľové hodnoty.

## Výsledky naprieč všetkými piatimi foldmi

| Model | MAE | RMSE | Bias | MAE priemer foldov ± SD | MAE poradia |
| --- | ---: | ---: | ---: | ---: | ---: |
| tuned_xg_draw | 4.952 | 6.210 | -0.422 | 4.952 ± 0.730 | 1.790 |
| tuned_xg_original | 5.203 | 6.458 | +1.806 | 5.203 ± 0.632 | 1.800 |
| tuned_goals_draw | 5.328 | 6.633 | -0.398 | 5.328 ± 0.646 | 1.910 |
| fixed_xg_draw | 5.531 | 7.132 | -0.695 | 5.531 ± 0.781 | 1.825 |
| tuned_goals_original | 5.613 | 6.890 | +1.803 | 5.613 ± 0.665 | 1.920 |
| ppg | 6.040 | 7.537 | -0.110 | 6.040 ± 0.513 | 1.980 |
| fixed_xg_original | 6.040 | 7.738 | +1.466 | 6.040 ± 0.715 | 1.835 |
| fixed_goals_draw | 6.820 | 8.625 | -0.924 | 6.820 ± 0.710 | 1.950 |
| fixed_goals_original | 7.365 | 9.338 | +1.218 | 7.365 ± 0.545 | 1.960 |

## Rozdelenie sezón

| Fold | Tréningové sezóny | Testovacie sezóny | Podiel remíz z tréningu | Chronologický holdout |
| --- | --- | --- | ---: | --- |
| 1 | 2016,2017,2018,2019,2020,2021,2022,2023 | 2014,2015 | 0.2257 | Nie |
| 2 | 2014,2015,2018,2019,2020,2021,2022,2023 | 2016,2017 | 0.2313 | Nie |
| 3 | 2014,2015,2016,2017,2020,2021,2022,2023 | 2018,2019 | 0.2378 | Nie |
| 4 | 2014,2015,2016,2017,2018,2019,2022,2023 | 2020,2021 | 0.2352 | Nie |
| 5 | 2014,2015,2016,2017,2018,2019,2020,2021 | 2022,2023 | 0.2359 | Áno |

## Chronologický holdout (fold 5)

| Model | γ | MAE | RMSE |
| --- | ---: | ---: | ---: |
| tuned_xg_draw | 1.2 | 5.272 | 6.404 |
| fixed_xg_draw | 2.0 | 5.430 | 6.741 |
| tuned_xg_original | 1.2 | 5.581 | 6.648 |
| fixed_xg_original | 2.0 | 5.795 | 7.357 |
| tuned_goals_draw | 1.0 | 5.862 | 7.019 |
| ppg | — | 6.025 | 7.425 |
| tuned_goals_original | 0.9 | 6.179 | 7.286 |
| fixed_goals_draw | 2.0 | 6.882 | 8.160 |
| fixed_goals_original | 2.0 | 7.396 | 8.822 |

## Obmedzenia

- xG je historický export a nebolo overené, že hodnoty neprešli revíziami.
- Poradie je určené **len bodmi**, remízy v počte bodov dostanú priemerné poradie;
  to nemusí zodpovedať oficiálnej tabuľke s kritériami skóre/vzájomných zápasov.
- Top-4 prekrytie zohľadňuje aj remízy v bodoch na hranici 4. miesta.
- Používa symetrickú metriku: prienik Top-4 množín delený veľkosťou väčšej množiny.
- Foldové výsledky nie sú nezávislé (prekrývajúce sa tréningové množiny).
- Fixný γ=2 v tomto experimente vyhodnocujeme na všetkých 10 sezónach, preto jeho
  metriky nemožno priamo stotožniť s výsledkami Experimentu 02 (9 sezón).

## Výstupy

`predictions.csv`, `fold_metrics.csv`, `overall_metrics.csv`,
`gamma_tuning.csv`, `folds.csv`, `metadata.json`, `report.md`,
`mae_comparison.png`, `gamma_by_fold.png`.

Spustenie: `python -m football_analysis.experiment_03`.
