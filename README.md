# BP Statistical Analysis of Football Data

## Prvý dokončený experiment

Pilot používa dataset Understat z Kaggle, **Premier League 2014/15–2023/24**,
3 800 zápasov a 200 tímových sezón. Exponent **2** je pevný pre góly aj xG.
Samostatne vyhodnocuje celosezónny opisný odhad a predikciu po prvých
19 zápasoch každého tímu. Cieľom sú body získané zo zápasov, pred bodovými trestami.

| Predikcia po 19 zápasoch | MAE (body) | RMSE (body) |
| --- | ---: | ---: |
| Pythagorejský model z gólov | 7.365 | 9.338 |
| Pythagorejský model z xG | 6.040 | 7.738 |
| Pokračovanie bodového priemeru | 6.040 | 7.537 |

xG znižuje MAE oproti gólovému modelu približne o 18 %, ale neprekonáva
referenčný bodový priemer. Toto je opisný záver z uvedeného historického testu.

- [Obsah a kvalita datasetu](reports/understat_dataset.md)
- [Metóda, výsledky po sezónach a grafy](reports/experiment_01/report.md)
- [Stav projektu a ďalšie kroky](reports/project_review.md)

Reprodukcia z koreňa projektu:

```text
python -m pip install -e ".[dev,analysis]"
python -m football_analysis.pilot data/raw/Understat-data.zip
python -m pytest
```

ZIP musí byť dostupný lokálne. Raw dáta sa neposielajú do Gitu.
Výsledky sú v `reports/experiment_01`, agregované vstupy v `data/processed`.

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

- **Understat cez Kaggle** je zdrojom gólov, xG a výsledkov prvého experimentu.
- **football-data.co.uk** je voliteľný nezávislý kontrolný zdroj výsledkov;
  jeho porovnanie zatiaľ nebolo vykonané a nie je podmienkou prvého pilotu.

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

2. Pre aktuálny Kaggle pilot postupovať podľa
   [`data_workflow.md`](data_workflow.md) a spustiť `football_analysis.pilot`.
3. Na voliteľné porovnanie dvoch zápasových zdrojov slúžia pôvodné loadery
   v `sources.py` a `validate_common_season` v `validation.py`.
   Kaggle `game_stats.csv` má vlastný adaptér `understat_dataset.py`.
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

Obsah dodaného ZIP bol overený, prvý experiment bol vykonaný a výsledky sú
uložené s metadátami a hashmi vstupov aj kódu. Licencia a číslo verzie Kaggle
nie sú v archíve a zatiaľ neboli potvrdené. Rozsah dát končí v septembri 2024.
Notebooky zostávajú prázdne; celý výpočet je reprodukovateľný cez Python CLI.
