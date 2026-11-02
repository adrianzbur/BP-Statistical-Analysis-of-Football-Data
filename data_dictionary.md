# Datovy slovnik

Projekt pracuje s tabulkami na urovni zapasov. Zdrojove subory sa stahuju
samostatne a ukladaju lokalne do `data/raw`; velke zdrojove datasety sa
necommit-uju do Git repozitara.

## Canonicalna schema zapasu

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
