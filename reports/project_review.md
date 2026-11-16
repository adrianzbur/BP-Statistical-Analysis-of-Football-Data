# Kontrola projektu a aktuálny stav bakalárskej práce

**Stav k 16. 11. 2026:** Experimenty 01, 02 a 03 sú dokončené a ich kód, testy, reporty a výsledky sú uložené v pracovnom GitHub repozitári. Doterajšie experimenty sa týkajú **anglickej Premier League (EPL)**.

## 1. Splnenie pôvodných úloh

| Zadanie | Stav | Výstup |
| --- | --- | --- |
| Oboznámiť sa s Understat datasetom a identifikovať použiteľné údaje | Splnené | [Analýza datasetu](understat_dataset.md), `data_dictionary.md` |
| Predikovať konečné body pomocou pevného Pytagorovho exponentu z gólov a xG | Splnené | [Experiment 01](experiment_01/report.md), γ = 2 |
| Vyhodnotiť metódu na jednej lige počas viacerých sezón | Splnené | EPL 2014/15–2023/24, 10 sezón, 200 tímových sezón |
| Zohľadniť remízy v predikcii bodov | Splnené ako rozšírenie | [Experiment 02](experiment_02/report.md) |
| Optimalizovať exponent a použiť 5-násobnú validáciu 8 + 2 sezóny | Splnené pre EPL | [Experiment 03](experiment_03/report.md) |
| Porovnať predikované a skutočné poradie tímov | Splnené v základnej verzii | `rank_mae`, symetrické `top4_overlap` |
| Porovnať optimálne exponenty medzi viacerými ligami | Zatiaľ nesplnené | Nasledujúci experiment |

## 2. Použitý dataset a spracovanie

Zdroj: [Understat dataset na Kaggle](https://www.kaggle.com/datasets/codytipton/understat-data). Pôvodný archív obsahuje súbory `game_stats.csv`, `player_stats.csv` a `understat.db`. Dostupné údaje zahŕňajú góly, xG, výsledky a informácie o zápasoch.

Export `game_stats.csv` ukladá jeden záznam za tím a zápas, nie jeden riadok za celý zápas. Preto bol vytvorený adaptér `understat_dataset.py`, ktorý validuje tímové záznamy, páruje domáce a hosťujúce pohľady a overuje úplnosť súťažného rozpisu.

Dataset zahŕňa šesť líg; doteraz sa experimenty vyhodnocovali iba na EPL. Použiteľných je 10 úplných ročníkov 2014/15–2023/24. Neúplné sezóny sa vylučujú podľa zdokumentovaných pravidiel.

Raw dáta zostávajú lokálne a nie sú súčasťou Git repozitára. Zdroj a rozsah sú popísané v [analýze datasetu](understat_dataset.md) a v `data_workflow.md`.

## 3. Experiment 01 – pevný exponent

**Stav:** dokončený.

- Pevný exponent `γ = 2` pre góly aj xG.
- 10 sezón EPL, 3 800 zápasov, 200 tímových sezón.
- Samostatne sa vyhodnocuje opisný odhad z celej sezóny a predikcia konečných bodov po prvých 19 zápasoch každého tímu.
- Referencia: pokračovanie aktuálneho bodového priemeru (PPG).

### Predikcia po 19 zápasoch

| Model | MAE | RMSE |
| --- | ---: | ---: |
| Góly, γ = 2 | 7.365 | 9.338 |
| xG, γ = 2 | 6.040 | 7.738 |
| PPG | 6.040 | 7.537 |

xG znižuje MAE približne o 18 % oproti gólovému modelu, ale pri danom nastavení neprekonáva PPG. Opisný celosezónny odhad používa viac informácií než predikcia v polovici sezóny a nemožno ho interpretovať ako rovnakú úlohu.

[Report Experimentu 01](experiment_01/report.md)

## 4. Experiment 02 – korekcia remíz

**Stav:** dokončený a commitnutý.

- Pevné `γ = 2`; zmenený je iba koeficient pre očakávané budúce body.
- Použitý faktor `3 − d_hist`, kde `d_hist` vychádza výlučne z predchádzajúcich úplných sezón.
- Sezóna 2014/15 slúži ako počiatočná kalibrácia; hodnotí sa 2015/16–2023/24, teda 180 tímových sezón.
- Všetkých päť porovnávaných modelov používa identickú testovaciu vzorku.

### Výsledky

| Model | MAE | RMSE |
| --- | ---: | ---: |
| Pôvodné góly | 7.317 | 9.294 |
| Góly s korekciou remíz | 6.715 | 8.549 |
| Pôvodné xG | 6.023 | 7.756 |
| **xG s korekciou remíz** | **5.454** | **7.113** |
| PPG | 5.983 | 7.470 |

Korekcia znižuje chybu xG modelu oproti pôvodnému variantu. Historická kalibrácia nevyužíva podiel remíz hodnotenej sezóny. Výstupy zahŕňajú predikcie, kalibračnú tabuľku, metriky, porovnania, grafy a dokumentáciu.

**Dôležité:** Ide o empirickú korekciu na úrovni ligy, nie o explicitný odhad pravdepodobnosti remízy pre jednotlivé tímy. Experiment 02 pracuje s 9 hodnotenými sezónami, takže jeho agregované MAE nemožno bez upozornenia porovnávať s metrikami Experimentov 01 a 03 na 10 sezónach.

[Report Experimentu 02](experiment_02/report.md)

## 5. Experiment 03 – optimalizácia exponentu a poradie tímov

**Stav:** dokončený a commitnutý.

Podľa odporúčania konzultanta bola implementovaná **5-násobná krížová validácia po celých sezónach**. Pre 10 úplných sezón EPL má každý fold 8 tréningových a 2 testovacie sezóny. Každá sezóna je v testovacej množine presne raz.

### Metodika

- Exponent sa optimalizuje samostatne pre štyri varianty: góly/xG × bez korekcie/s korekciou remíz.
- Mriežka `γ = 0.5, 0.6, …, 3.0` obsahuje 26 kandidátov.
- Výber optimálnej hodnoty je založený na **MAE tréningových sezón**, nie na MAE testovacích sezón.
- Historický podiel remíz sa počíta iba z **tréningových sezón príslušného foldu**; nie je optimalizovaný ako ďalší nezávislý parameter.
- Výsledky sa porovnávajú s fixným exponentom `γ = 2` a s PPG benchmarkom.
- Predikuje sa bodový zisk po prvých 19 zápasoch tímu; konečné body sa používajú iba pri vyhodnotení.

### Hlavné výsledky

| Model | MAE | RMSE | MAE poradia |
| --- | ---: | ---: | ---: |
| **Optimalizované xG s korekciou remíz** | **4.952** | **6.210** | **1.790** |
| Optimalizované xG bez korekcie | 5.203 | 6.458 | 1.800 |
| Optimalizované góly s korekciou remíz | 5.328 | 6.633 | 1.910 |
| Fixné xG s korekciou remíz | 5.531 | 7.132 | 1.825 |
| PPG | 6.040 | 7.537 | 1.980 |

Najlepší model podľa MAE je optimalizované xG s korekciou remíz. Dosiahol symetrické prekrytie Top-4 **88,0 %**, kým PPG dosahuje **86,5 %**. Symetrická Top-4 metrika je definovaná ako počet spoločných členov predikovanej a skutočnej Top-4 množiny delený veľkosťou väčšej z nich; pri rovnosti bodov na hranici štvrtého miesta môže množina obsahovať viac než štyri tímy.

Hodnotenie poradia vychádza **iba z bodov** a pri rovnosti používa priemerné poradie. Nejde teda o presnú simuláciu oficiálnej ligovej tabuľky vrátane všetkých pomocných kritérií.

### Časová interpretácia validácie

Validácia je primárne **retrospektívna**: foldy 1 až 4 môžu používať na optimalizáciu sezóny novšie než samotné testované sezóny. To neznamená, že sa testované sezóny používajú pri optimalizácii parametrov, ale výsledok nemožno prezentovať ako päť chronologických predpovedí budúcnosti.

Iba **fold 5** predstavuje chronologický holdout: tréning 2014/15–2021/22 a test 2022/23–2023/24. V ňom dosiahol optimalizovaný xG model s korekciou remíz `γ = 1.2`, MAE **5.272** a RMSE **6.404**, oproti PPG s MAE **6.025**.

Výsledky zahŕňajú `folds.csv`, `gamma_tuning.csv`, `fold_metrics.csv`, `overall_metrics.csv`, `predictions.csv`, grafy a report.

[Report Experimentu 03](experiment_03/report.md)

## 6. Implementácia a overenie

Hlavné moduly:

| Súbor | Účel |
| --- | --- |
| `src/football_analysis/understat_dataset.py` | Validácia dát, párovanie tímových záznamov, výber úplných sezón |
| `src/football_analysis/forecast.py` | Predikcia konečných bodov po zvolenom počte zápasov |
| `src/football_analysis/pythagorean.py` | Výpočet Pytagorovho podielu |
| `src/football_analysis/pilot.py` | Experiment 01 a výstupný audit |
| `src/football_analysis/experiment_02.py` | Korekcia remíz a vyhodnotenie |
| `src/football_analysis/experiment_02_reporting.py` | Reportovanie a grafy Experimentu 02 |
| `src/football_analysis/experiment_03.py` | Optimalizácia exponentu, validácia a metriky poradia |

Testy sú v `tests/` vrátane `test_experiment_02.py` a `test_experiment_03.py`. Kontrolujú výpočty, výber sezón, oddelenie tréningových a testovacích dát, spracovanie remíz, zmeny budúcich výsledkov a opravenú metriku Top-4.

Používateľ už úspešne spustil lokálne testy a Experiment 03 vo VS Code. **Na GitHube zatiaľ nie je nakonfigurované automatické spúšťanie testov (GitHub Actions)**; úspech testov preto nevyplýva priamo zo stavu commitu.

Reprodukcia z koreňa projektu:

```powershell
python -m pip install -e ".[dev,analysis]"
python -m pytest -v
python -m football_analysis.experiment_02
python -m football_analysis.experiment_03
```

Pre Experiment 01: `python -m football_analysis.pilot data/raw/Understat-data.zip`. Potrebné raw dáta musia byť dostupné lokálne.

## 7. Metodické obmedzenia

- Cieľom je súčet bodov získaných zo zápasov (`3W + D`), nie oficiálna tabuľka po prípadných administratívnych odpočtoch.
- Vstupné góly, xG a získané body pochádzajú iba z prvých 19 zápasov tímu; tento okamih nie je spoločný kalendárny dátum.
- Predikcie nezohľadňujú silu zostávajúcich súperov, prestupy ani priebežné zmeny formy.
- Historický export xG mohol prejsť revíziami.
- Päť foldov používa prekrývajúce sa tréningové dáta a nepredstavuje päť nezávislých dôkazov. Priemery a smerodajné odchýlky sú zatiaľ opisné; štatistická významnosť rozdielov nebola samostatne potvrdená.
- Licenčné podmienky a presná verzia použitého Kaggle exportu zostávajú neoverené.
- Dataset obsahuje šesť líg, ale výsledky zatiaľ pochádzajú len z EPL.

## 8. Ďalší postup podľa konzultanta

1. **Rozšíriť optimalizáciu exponentu na ďalšie ligy.** Pri každej lige overiť počet tímov, dĺžku sezóny a dostupnosť 10 úplných ročníkov; ak taká vzorka nie je, transparentne upraviť validačný plán.
2. **Doplniť štatistické vyhodnotenie rozdielov modelov.** Porovnať párové chyby na rovnakých sezónach/foldoch, doplniť vhodné miery neistoty a odlíšiť opisné výsledky od štatisticky podložených tvrdení.
3. **Rozšíriť porovnanie poradia**, ak bude cieľom oficiálna konečná tabuľka, o pravidlá pri rovnosti bodov a prípadné administratívne odpočty.
4. Voliteľne otestovať ďalšie predikčné okamihy (napr. po 10 a 28 zápasoch) a nezávisle overiť výsledky z druhého zdroja, napr. `football-data.co.uk`.

**Najbližší experiment:** porovnanie optimálnych exponentov medzi viacerými ligami na základe metodiky Experimentu 03. Pred jeho začatím je vhodné overiť, ktoré ligy poskytujú dostatočný počet kompletných sezón.
