# Datovy workflow: Premier League pilot

Tento postup pripravuje jednu spolocnu sezonu Premier League pre porovnanie
Understatu a football-data.co.uk. V repozitari nie su ziadne raw data ani
automaticke stahovanie.

## Odporucana pilotna konfiguracia

Ako prvy pilot pouzi jednu kompletne dostupnu sezonu, napr. `2022-23`.
Konkretnu sezonu treba potvrdit podla dostupnosti rovnakeho rozsahu v oboch
zdrojoch a zapisat do metadat analyzy. Liga sa v kode oznacuje ako `EPL`.

Odporucane nazvy lokalnych suborov:

```text
data/raw/understat_EPL_2022-23.csv
data/raw/football-data_EPL_2022-23.csv
```

Subory sa do Git repozitara nepridavaju. Adresar `data/raw` je urceny pre
lokalnu pracu a jeho obsah je ignorovany pomocou `.gitignore`.

## Manualne ziskanie suborov

1. Ziskaj Understat data pre Premier League a zvolenu sezonu sposobom, ktory
   povoluje zdroj a jeho podmienky pouzitia.
2. Ziskaj prislusny CSV subor z football-data.co.uk pre tu istu sezonu.
3. Neobchadzaj robots pravidla, rate limity, prihlasenie ani inu ochranu webu.
   Ak pri zdroji nie je jasne povolene programove stahovanie, pouzi rucne
   stiahnutie v prehliadaci alebo dostupny oficialny export.
4. Subory uloz do `data/raw` pod odporucanymi nazvami.
5. Zapis zdrojovu URL, datum stiahnutia, sezonu, verziu alebo popis suboru,
   licencne podmienky a kazdu vykonanu upravu.

Understat subor musi obsahovat datum, domaci a hostujuci tim, skore a
`home_xg`/`away_xg` (pripadne podporovane aliasy). Football-data subor musi
obsahovat `Date`, `HomeTeam`, `AwayTeam`, `FTHG` a `FTAG`. Podrobna schema je
v [`data_dictionary.md`](data_dictionary.md).

## Nacitanie a validacia

Po instalacii projektu spusti validaciu v kratkom Pythone skripte alebo
notebooku:

```python
from football_analysis import (
    load_football_data_matches,
    load_understat_matches,
    validate_common_season,
)

understat = load_understat_matches(
    "data/raw/understat_EPL_2022-23.csv",
    league="EPL",
    season="2022-23",
)
football_data = load_football_data_matches(
    "data/raw/football-data_EPL_2022-23.csv",
    league="EPL",
    season="2022-23",
)

report = validate_common_season(
    understat,
    football_data,
    league="EPL",
    season="2022-23",
)
report.raise_if_invalid()
print(report.match_count, report.team_count)
```

Validacia kontroluje:

- pritomnost canonicalnych stlpcov a ligy/sezony,
- duplicitne zapasy v kazdom zdroji,
- zhodu zapasov podla datumu, domaceho a hostujuceho timu,
- zhodu domaceho a hostujuceho skore,
- zhodu mnoziny timov,
- nepritomnost chybajucich Understat xG,
- to, ze benchmark z football-data.co.uk nema xG hodnoty.

Nazvy timov sa porovnavaju po odstraneni okrajovych medzier a bez rozlisenia
velkych a malych pismen. Ak zdroje pouzivaju ine nazvy, pridaj explicitne
`team_aliases` do volania validatora a tuto mapu zapis do dokumentacie.
Fuzzy matching ani automaticke tiche opravy sa nepouzivaju.

## Ocekavany vysledok

Validna sezona musi mat rovnaky pocet spolocnych zapasov, rovnake pary timov,
datum a skore. Understat musi mat xG pre kazdy zapas a football-data.co.uk
musi mat xG prazdne. Pri chybe sa validacia skonci s konkretnym zoznamom
problemov; data sa nemaju opravovat bez zaznamenania upravy.
