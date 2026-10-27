# BP Statistical Analysis of Football Data

Projekt bakalarskej prace zamerany na statisticku analyzu futbalovych dat.

## Ciel projektu

Cielom je preskumat, ako dobre moze Pythagorejska ocakavanie odhadovat
uspesnost futbaloveho timu na zaklade streleneho a inkasovaneho poctu golov.
V dalsom kroku bude model porovnany s metrikami zalozenymi na expected goals
(xG), ak budu dostupne spolahlive a jasne zdokumentovane data.

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

## Pociatocny rozsah

V prvej faze bude podporovana analyza na urovni timu a sezony. Zakladne
premenne budu obsahovat identifikator sezony, identifikator timu, strelene
goly a inkasovane goly. Neskor je mozne pridat body, zapasy, vysledky zapasov
a xG pre tim alebo zapas.

Mimo rozsahu prvej fazy su:

- automaticke stahovanie dat z neoverenych zdrojov,
- imputacia alebo simulacia chybajucich xG,
- kauzalne tvrdenia o kvalite timu,
- produkcne nasadenie modelu.

## Pozadovane data

Minimalny vstupny subor by mal byt tabulkovy format CSV alebo Parquet a mal by
obsahovat:

- `team` - nazov alebo stabilny identifikator timu,
- `season` - identifikator sezony,
- `goals_for` - strelene goly,
- `goals_against` - inkasovane goly.

Pre vyhodnotenie budu uzitocne aj `points`, `matches` alebo vysledky zapasov.
Ak sa pouziju xG data, musi byt uvedeny zdroj, licencia, definicia xG,
casovy rozsah a sposob agregacie.

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

2. Vlozit zdrojove data do `data/raw` a zdokumentovat ich zdroj.
3. Pouzit funkcie v `src/football_analysis` na nacitanie a validaciu dat.
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
zmeny pravidiel a rozne zdroje dat. Vysledky budu obsahovat intervaly
neistoty alebo aspon upozornenie na obmedzenia, ak to rozsah dat dovoli.

## Struktura repozitara

```text
data/                  Vstupne, docasne a spracovane data
notebooks/              Experimenty a prieskumna analyza
reports/figures/        Exportovane grafy a obrazky
src/football_analysis/  Knihovna pre nacitanie a analyzu
tests/                  Automatizovane testy
```

## Stav

Repozitar obsahuje zaklad projektu. Konkretne datove zdroje, rozsah sezon,
volba exponentu a finalny plan statistickeho vyhodnotenia budu doplnene po
vybere a kontrole dat.
