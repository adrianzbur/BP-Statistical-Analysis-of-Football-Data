# Datovy slovnik

## Overený Kaggle export a mapovanie

Aktuálny experiment používa `data/raw/understat/game_stats.csv` z dodaného
archívu `Understat-data.zip`. Jeden riadok je **tím v zápase**, nie celý zápas.
Všetkých 23 zápasových aj 19 hráčskych stĺpcov, ich účel a kvalita sú popísané
v [`reports/understat_dataset.md`](reports/understat_dataset.md).

| Zdrojový stĺpec | Sezónny výstup | Spracovanie |
| --- | --- | --- |
| `league`, `season` | `league`, `season` | Zachovať; sezóna je začiatkový rok |
| `club_name` | `team` | Názov tímu |
| `id` | — | Klubové ID, nepoužiť ako kľúč zápasu |
| `date` | `played` | Počet vlastných riadkov tímu |
| `scored`, `missed` | `goals_for`, `goals_against` | Súčet |
| `xG`, `xGA` | `xg_for`, `xg_against` | Súčet |
| `wins`, `draws`, `loses` | `wins`, `draws`, `losses` | Súčet indikátorov |
| `pts` | `points` | Súčet; kontrola 3W + D |

Adaptér je v `understat_dataset.py`. Predikčný modul `forecast.py` vytvára
`observed_*` iba z prvých 19 zápasov; `actual_points` je hodnotený konečný
súčet. `cutoff_date` dokumentuje dátum posledného použitého zápasu.
Výstupy `predicted_goals`, `predicted_xg`, `predicted_ppg` sú odhady konečných
bodov; `error_*` znamená odhad mínus skutočnosť.

Body nezahŕňajú administratívne odpočty. Hráčske riadky nie sú zdrojom
tímových zápasových súčtov. Nasledujúca kanonická schéma je určená pre
rekonštruované celé zápasy a pre pôvodné všeobecné loadery.

Projekt pracuje s tabulkami na urovni zapasov. Zdrojove subory sa stahuju
samostatne a ukladaju lokalne do `data/raw`; velke zdrojove datasety sa
necommit-uju do Git repozitara.

## Kanonicka schema zapasu

Loadery v `src/football_analysis/sources.py` vracaju tieto stlpce:

| Stlpec | Typ | Vyklad |
| --- | --- | --- |
| `date` | datetime | Datum zapasu podla zdrojovych dat |
| `league` | string | Identifikator sutaze, napr. `EPL` |
| `season` | string | Identifikator sezony, napr. `2022-23` |
| `home_team` | string | Nazov alebo identifikator domaceho timu |
| `away_team` | string | Nazov alebo identifikator hostujuceho timu |
| `home_goals` | nezaporne cislo | Konecny pocet golov domaceho timu |
| `away_goals` | nezaporne cislo | Konecny pocet golov hostujuceho timu |
| `home_xg` | nezaporne cislo alebo prazdne | Expected goals domaceho timu z Understat |
| `away_xg` | nezaporne cislo alebo prazdne | Expected goals hostujuceho timu z Understat |
| `source` | string | Oznacenie pouziteho loadera alebo zdroja |

`home_xg` a `away_xg` su pri benchmarkovych riadkoch z football-data.co.uk
umyselne prazdne. Nesmie sa do nich doplnat hodnota ani interpretovat prazdna
hodnota ako nula.

## Format vstupnych suborov podla zdroja

### Understat

Pouzi lokalne stiahnuty CSV alebo Parquet subor, ktory obsahuje minimalne:

```text
date,home_team,away_team,home_goals,away_goals,home_xg,away_xg
```

Loader akceptuje aj bezne alternativne nazvy, napriklad `h_xg`, `a_xg`,
`h_team`, `a_team`, `h_goals` a `a_goals`.

### football-data.co.uk

Pouzi stiahnuty CSV subor so standardnymi stlpcami:

```text
Date,HomeTeam,AwayTeam,FTHG,FTAG
```

Vstup moze obsahovat aj dalsie zdrojove stlpce, ale goals-only benchmark
loader ich nepotrebuje. Stlpec `Date` sa interpretuje s poradim den-mesiac-rok,
pretoze ide o standardny format tychto suborov.

## Nazvy suborov a metadata

Odporucane lokalne nazvy suborov su:

```text
data/raw/understat_<league>_<season>.csv
data/raw/football-data_<league>_<season>.csv
```

Pri kazdom stiahnutom subore zaznamenaj zdrojovu URL, datum stiahnutia, ligu,
sezonu, verziu zdroja alebo popis stranky a vsetky vykonane upravy.
Repozitar neobsahuje downloader a neobchadza pravidla robots.txt, rychlostne
limity, autentifikaciu ani inu ochranu webu.

## Rozsah a obmedzenia

Understat je zdrojom xG pre vybrane top ligy a sezony. Pre konkretne pouzite
data treba overit definiciu xG, historicku dostupnost, nazvy timov a podmienky
pouzitia. football-data.co.uk je goals-only benchmark a kontrolny zdroj
vysledkov zapasov; nejde o zdroj xG.

Odporucany pociatocny rozsah je jedna alebo dve vybrane top ligy a mala,
jednoznacne zdokumentovana mnozina kompletnych sezon, ktore su dostupne
v oboch zdrojoch. Pred vypoctom metrik je potrebne zosuladit datum, nazvy
timov, ligu a sezonu. Rozdiely v pokryti, reviziach, definiciach, licencii
a kvalite zdrojov treba uviest vo vysledkoch, nie ich potichu opravovat.

## Premier League pilot

Prvym pilotnym datasetom je Premier League (`EPL`). Vyber jedna spolocna
kompletna sezona, napr. `2022-23`, musi byt potvrdeny dostupnostou v oboch
zdrojoch. Validacia vyzaduje zhodu zapasov, timov, datumov a skore. Understat
nesmie mat chybajuce `home_xg` alebo `away_xg`; benchmark z
football-data.co.uk xG hodnoty nema.
