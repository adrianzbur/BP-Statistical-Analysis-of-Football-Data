# BP Statistical Analysis of Football Data

Projekt bakalarskej prace zamerany na statisticku analyzu futbalovych dat.

## Ciel projektu

Cielom je preskumat, ako dobre moze Pythagorejska ocakavanie odhadovat
uspesnost futbaloveho timu na zaklade streleneho a inkasovaneho poctu golov.
Rozsirena analyza porovna golovy model s expected goals (xG) pre vybrane top
ligy a sezony.

## Navrhovany smer vyskumnej prace

Zakladom analyzy bude Pythagorejska ocakavanie:

`ocakavany podiel vyhier = goly za^e / (goly za^e + goly proti^e)`

Exponent `e` bude zvoleny a vyhodnoteny transparentne. Projekt bude porovnavat
minimalne:

- ocakavany podiel vyhier z realneho poctu golov,
- skutocnu uspesnost timu v rovnakej sezone,
- pripadny model zalozeny na xG, ak data umoznia korektne porovnanie.

Projekt nebude predpokladat vlastnu definiciu xG ani doplnat chybajuce xG
hodnoty. xG bude pouzite iba vtedy, ked bude zdroj, definicia premennych a
agregacna uroven dostatocne zdokumentovana.

## Rozhodnutie o zdrojoch dat

- **Understat** bude zdrojom xG pre vybrane top ligy a sezony.
- **football-data.co.uk** bude goals-only benchmark a kontrolny zdroj
  vysledkov zapasov.

Oba zdroje sa budu pouzivat iba vo forme uz stiahnutych lokalnych suborov.
Repozitar neobsahuje scraper, automaticke stahovanie ani mechanizmus na
obchadzanie robots pravidiel, rate limitov, autentifikacie alebo inej ochrany
webu. Subory sa nebudu commitovat do Git repozitara.

Zdroj, datum stiahnutia, liga, sezona, pouzita URL alebo popis stranky a
pripadne upravy treba zapisat do metadat analyzy. Understat xG je zavisle od
definicie a pokrytia zdroja; football-data.co.uk poskytuje goly a vysledky,
nie xG. Licencne podmienky a podmienky pouzitia treba overit pre konkretne
stiahnute verzie a vysledky interpretovat s tymto obmedzenim.

## Pociatocny rozsah

V prvej faze bude podporovana analyza na urovni zapasu, timu a sezony.
Odporucany rozsah je jedna alebo dve vybrane top ligy a mala, explicitne
zdokumentovana mnozina kompletnych sezon, ktore su dostupne v oboch zdrojoch.
Zakladne premenne budu obsahovat datum, domaci a hostujuci tim, goly a pri
Understat aj home/away xG.

Mimo rozsahu prvej fazy su:

- automaticke stahovanie dat z neoverenych zdrojov,
- imputacia alebo simulacia chybajucich xG,
- kauzalne tvrdenia o kvalite timu,
- produkcne nasadenie modelu.

## Pozadovane data

Minimalny timovo-sezonny subor by mal byt tabulkovy format CSV alebo Parquet a
mal by obsahovat:

- `team` - nazov alebo stabilny identifikator timu,
- `season` - identifikator sezony,
- `goals_for` - strelene goly,
- `goals_against` - inkasovane goly.

Pre vyhodnotenie budu uzitocne aj `points`, `matches` alebo vysledky zapasov.
Minimalna schema zapasovych dat a mapovanie zdrojov su v
[`data_dictionary.md`](data_dictionary.md). Ak sa pouziju xG data, musi byt
uvedeny zdroj, licencia, definicia xG, casovy rozsah a sposob agregacie.

Data sa ukladaju podla fazy spracovania:

- `data/raw` - povodne data bez uprav,
- `data/interim` - docasne medzivysledky,
- `data/processed` - data pripravene na analyzu.

Samotne data sa do repozitara standardne nepridavaju; adresare su udrziavane
pomocou suborov `.gitkeep`.

## Reprodukovatelny workflow

1. Vytvorit virtualne prostredie a nainstalovat projekt:

   ```text
   python -m venv .venv
   .venv\Scripts\activate
   python -m pip install -e ".[dev]"
   ```

2. Pre Premier League pilot postupovat podla
   [`data_workflow.md`](data_workflow.md). Pouzit jednu spolocnu kompletne
   dostupnu sezonu, napr. `2022-23`, a ulozit lokalne subory do `data/raw`.
3. Pouzit `load_understat_matches` a `load_football_data_matches` z modulu
   `src/football_analysis/sources.py`, potom
   `validate_common_season` z `src/football_analysis/validation.py`.
4. Medzivysledky ulozit do `data/interim` alebo `data/processed`.
5. Experimenty a grafy udrziavat v `notebooks` a `reports/figures`.
6. Spustit testy:

   ```text
   python -m pytest
   ```

Kazdy vysledok analyzy by mal uvadzat pouzity vstup, exponent, obdobie,
filtre, verziu kodu a metriky. Notebooky maju obsahovat iba analyzu, nie
nezdokumentovane rucne upravy dat.

## Planovane vyhodnotenie

Vyhodnotenie bude oddelovat opisnu analyzu od predikcneho porovnania. Zakladne
metriky budu mean absolute error (MAE) a root mean squared error (RMSE) medzi
ocakavanym a pozorovanym ukazovatelom. Podla dostupnych cielovych premennych
moze byt doplnene porovnanie bodov, podielu vyhier alebo rozdielu golov.

Pri porovnavani sezon bude potrebne zohladnit rozdielny pocet zapasov,
zmeny pravidiel, rozdielne pokrytie a mozne zmeny definicie alebo revizie
zdrojov. Zapasy sa musia pred porovnanim zosuladit podla ligy, sezony, datumu
a nazvov timov. Vysledky budu obsahovat intervaly neistoty alebo aspon
upozornenie na obmedzenia, ak to rozsah dat dovoli.

## Struktura repozitara

```text
data/                  Vstupne, docasne a spracovane data
data_dictionary.md     Canonicalna schema a zdrojove mapovanie
data_workflow.md       Postup pre Premier League pilot
notebooks/              Experimenty a prieskumna analyza
reports/figures/        Exportovane grafy a obrazky
src/football_analysis/  Knihovna pre nacitanie a analyzu
tests/                  Automatizovane testy
```

## Stav

Repozitar obsahuje zaklad projektu a navrh lokalneho datoveho kroku. Konkretne
ligy, sezony, licencne overenie, volba exponentu a finalny plan statistickeho
vyhodnotenia budu doplnene po vybere a kontrole dat.
