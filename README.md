# BP – Štatistická analýza futbalových dát

Bakalárska práca zameraná na štatistickú analýzu futbalových dát a predikciu konečného počtu bodov tímov. Projekt porovnáva **Pytagorov model z gólov**, jeho variant s **expected goals (xG)** a referenčný model založený na **bodovom priemere (PPG)**. Nadväzujúce experimenty skúmajú korekciu remíz a optimalizáciu Pytagorovho exponentu.

## Aktuálny stav

**Experimenty 01, 02 a 03 sú dokončené pre anglickú Premier League (EPL).**

| Experiment | Metóda a cieľ | Hodnotené obdobie | Stav |
| --- | --- | --- | --- |
| [01 – Pevný exponent](reports/experiment_01/report.md) | Góly vs. xG, pevné γ = 2; predikcia bodov po 19 zápasoch | 2014/15–2023/24 (200 tímových sezón) | Dokončený |
| [02 – Korekcia remíz](reports/experiment_02/report.md) | Historický podiel remíz pri pevnom γ = 2 | 2015/16–2023/24 (180 tímových sezón) | Dokončený |
| [03 – Optimalizácia exponentu](reports/experiment_03/report.md) | Hľadanie γ pomocou 5-násobnej validácie po sezónach, porovnanie poradia | 2014/15–2023/24 (200 tímových sezón) | Dokončený |

Pre všetky experimenty sa predikujú body získané zo zápasov (`3 × výhry + remízy`), **bez administratívnych bodových odpočtov**. Vstupné štatistiky sa počítajú z prvých 19 chronologických zápasov každého tímu; jednotlivé tímy preto nemusia mať rovnaký dátum predikcie.

### Súhrn výsledkov

Nižšia hodnota MAE a RMSE znamená presnejší odhad konečného počtu bodov. Každý experiment má vlastnú vyhodnocovaciu vzorku, preto sa výsledky naprieč experimentmi nesmú bez upozornenia priamo porovnávať.

| Experiment | Model | MAE (body) | RMSE (body) |
| --- | --- | ---: | ---: |
| 01 | Góly, γ = 2 | 7.365 | 9.338 |
| 01 | xG, γ = 2 | 6.040 | 7.738 |
| 01 | PPG | 6.040 | 7.537 |
| 02 | xG, γ = 2, s korekciou remíz | **5.454** | **7.113** |
| 02 | PPG na rovnakej vzorke | 5.983 | 7.470 |
| 03 | Optimalizované xG s korekciou remíz | **4.952** | **6.210** |
| 03 | PPG na rovnakej vzorke | 6.040 | 7.537 |

Podrobné výsledky, metriky, predikcie a grafy sú uložené v `reports/experiment_01/`, `reports/experiment_02/` a `reports/experiment_03/`.

## Cieľ a metodika

Základom je Pytagorov očakávaný podiel:

```text
PE = GF^γ / (GF^γ + GA^γ)
```

Kde `GF` a `GA` predstavujú strelené a inkasované góly; variant xG používa `xGF` a `xGA`. Model predpovedá body za zostávajúce zápasy a pripočíta už získané body.

Používané predikcie:

```text
P_original = P_observed + 3 × (N − k) × PE
P_draw     = P_observed + (3 − d_hist) × (N − k) × PE
P_PPG      = N × P_observed / k
```

- `N` – počet zápasov v kompletnej sezóne (pre EPL 38).
- `k` – počet už odohraných zápasov (štandardne 19).
- `d_hist` – podiel remíz vypočítaný z povolených historických/tréningových sezón.
- `γ` – Pytagorov exponent; v experimentoch 01 a 02 pevný, v experimente 03 optimalizovaný.

Korekcia `3 − d_hist` je jednoduchá empirická úprava priemerného počtu bodov rozdelených za zápas. **Nie je to samostatný model pravdepodobnosti výhry a remízy.**

### Experiment 01 – pevný exponent

- Zdroj: Understat; 10 kompletných sezón EPL 2014/15–2023/24, 3 800 zápasov a 200 tímových sezón.
- Porovnanie gólového a xG modelu pri `γ = 2` s PPG; samostatne sa vyhodnocuje retrospektívny celosezónny odhad.
- Pri predikcii po 19 zápasoch má xG nižšiu MAE než góly, ale prakticky rovnakú MAE ako PPG.

[Podrobný report Experimentu 01](reports/experiment_01/report.md) · [Analýza Understat datasetu](reports/understat_dataset.md)

### Experiment 02 – korekcia remíz

- Pevné `γ = 2`, rovnaké vstupy z prvých 19 zápasov, s odhadom podielu remíz z **predchádzajúcich ukončených sezón**.
- Sezóna 2014/15 slúži na úvodnú kalibráciu; vyhodnocuje sa 9 sezón (2015/16–2023/24), teda 180 tímových sezón.
- xG model s korekciou dosahuje MAE **5.454** oproti **5.983** pre PPG na tej istej vzorke.

[Podrobný report Experimentu 02](reports/experiment_02/report.md) · [Graf modelov](reports/experiment_02/model_comparison.png) · [MAE po sezónach](reports/experiment_02/mae_by_season.png)

### Experiment 03 – optimalizácia exponentu

- **5-násobná krížová validácia po celých sezónach:** v každom folde 8 sezón na optimalizáciu, 2 na vyhodnotenie; každá z 10 sezón je testovaná práve raz.
- Exponent `γ` sa vyberá na tréningových dátach minimalizáciou MAE z mriežky **0.5 až 3.0** s krokom **0.1**.
- Samostatne sa ladia štyri varianty: góly/xG × bez korekcie/s korekciou remíz. Historický podiel remíz sa **odhaduje z tréningových sezón**, nie je to ďalší optimalizovaný parameter.
- Na rovnakých testovacích sezónach sa porovnávajú optimalizované modely, pevné `γ = 2` a PPG.
- Doplnkové metriky zahŕňajú chybu poradia (`rank_mae`) a symetrické prekrytie Top-4, ktoré pri rovnosti bodov povoľuje viacero tímov na hranici štvrtého miesta.

Najlepší variant podľa celkovej MAE je **optimalizované xG s korekciou remíz**: MAE **4.952**, RMSE **6.210**, priemerná absolútna chyba poradia **1.790** a Top-4 prekrytie **88 %**. PPG dosahuje MAE **6.040** a Top-4 prekrytie **86,5 %**.

**Metodické obmedzenie:** prvé štyri foldy sú retrospektívne a ich tréningová množina môže obsahovať sezóny novšie než testovacia. **Iba piaty fold** (test 2022/23 a 2023/24) je chronologickým holdoutom. Jeho výsledky treba interpretovať oddelene od celkového priemeru.

[Podrobný report Experimentu 03](reports/experiment_03/report.md) · [Porovnanie MAE](reports/experiment_03/mae_comparison.png) · [Exponenty podľa foldov](reports/experiment_03/gamma_by_fold.png)

## Dáta a ich spracovanie

Hlavný zdroj: [Understat dataset na Kaggle](https://www.kaggle.com/datasets/codytipton/understat-data).

Pôvodný archív obsahuje `game_stats.csv`, `player_stats.csv` a `understat.db`. Výpočty na úrovni zápasov a tímov používajú najmä `game_stats.csv`, kde jeden riadok reprezentuje pohľad jedného tímu na zápas. Adaptér `understat_dataset.py` kontroluje údaje, páruje domáce a hosťujúce záznamy a vyberá úplné sezóny.

Dataset pokrýva šesť líg, ale doterajšie tri experimenty sú vyhodnotené **iba na EPL**. Neúplné sezóny sú z analýzy vylúčené.

Dáta sa organizujú do `data/raw/` (pôvodné), `data/interim/` (medzivýsledky) a `data/processed/` (spracované). Pôvodné dátové súbory sú ignorované Gitom a musia byť dostupné lokálne.

Dokumentácia: [Dátový slovník](data_dictionary.md), [Pracovný postup s dátami](data_workflow.md), [Analýza datasetu](reports/understat_dataset.md).

`football-data.co.uk` zostáva voliteľným nezávislým kontrolným zdrojom výsledkov; vzájomné porovnanie zatiaľ nebolo vykonané. Licenčné podmienky a presná verzia získaného Kaggle archívu zatiaľ nie sú potvrdené.

## Spustenie projektu

Príkazy spúšťaj z koreňového priečinka repozitára. Na Windows v PowerShelli:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev,analysis]"
```

Pôvodný dataset môžeš mať rozbalený v `data/raw/understat/game_stats.csv`. Experimenty 02 a 03 túto cestu používajú štandardne; prípadne im môžeš zadať inú cestu k CSV alebo pôvodnému ZIP-u.

```powershell
# Experiment 01 – pôvodný archív
python -m football_analysis.pilot data/raw/Understat-data.zip

# Experiment 02 – korekcia remíz
python -m football_analysis.experiment_02

# Experiment 03 – 5-fold validácia a optimalizácia exponentu
python -m football_analysis.experiment_03

# Automatizované testy
python -m pytest -v
```

Ak máš archív alebo CSV na inom mieste, uprav cestu v príkaze. Spustenie `pytest` overuje implementované testy; samo osebe **nespúšťa všetky experimenty nad celým datasetom**.

Výstupy sa ukladajú do príslušných priečinkov `reports/experiment_01/`, `reports/experiment_02/` a `reports/experiment_03/`. Reporty, tabuľky a grafy sú verzované v repozitári.

## Štruktúra repozitára

```text
data/
  raw/                    Lokálne pôvodné dáta (ignorované Gitom)
  interim/                Lokálne medzivýsledky
  processed/              Lokálne spracované dáta
notebooks/                Priestor na ďalšiu prieskumnú analýzu
reports/
  experiment_01/          Výsledky pevného exponentu
  experiment_02/          Výsledky korekcie remíz
  experiment_03/          Výsledky 5-fold optimalizácie
  figures/                Priestor na ďalšie grafy
  project_review.md       Prehľad aktuálneho stavu a ďalších úloh
src/football_analysis/   Načítanie dát, metódy a experimenty
tests/                    Automatizované testy
data_dictionary.md        Schéma a mapovanie údajov
data_workflow.md          Postup práce s datasetom
pyproject.toml            Konfigurácia Python projektu
```

## Obmedzenia a ďalší postup

- Historické xG údaje mohli prejsť revíziami a nemusia zodpovedať presným hodnotám dostupným v deň pôvodnej predikcie.
- Bodové predikcie nezohľadňujú administratívne odpočty, silu zostávajúcich súperov ani dynamické zmeny formy.
- Poradie v Experimente 03 vzniká **iba z bodov**. Rovnosť bodov sa nevyhodnocuje podľa všetkých oficiálnych pravidiel ligovej tabuľky.
- Výsledky zatiaľ platia pre jednu ligu; rozdiely medzi modelmi nemajú samostatne potvrdenú štatistickú významnosť.

Nasledujúce úlohy: **(1)** rozšíriť optimalizáciu exponentu na ďalšie ligy s kontrolou úplnosti sezón, **(2)** štatisticky posúdiť párové rozdiely medzi modelmi a neistotu výsledkov, **(3)** prípadne preveriť iné hranice predikcie (napr. po 10 a 28 zápasoch) a oficiálne pravidlá určovania poradia.

Podrobnejší prehľad: [Stav projektu a ďalšie kroky](reports/project_review.md).
