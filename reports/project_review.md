# Kontrola projektu a stav prvých úloh

## Aktuálny stav: experiment 02 pred commitom

Experiment 02 je samostatná korekcia remíz pri pevnom exponente 2. Používa
historický podiel remíz z predchádzajúcich sezón a predikciu po 19 zápasoch
tímu. Prvá sezóna 2014/15 je kalibračná; hodnotí sa 180 tímových sezón EPL
2015/16–2023/24. Porovnávať treba všetkých päť modelov na tých istých riadkoch.

Overené výsledky: góly s korekciou MAE/RMSE 6,715/8,549, xG s korekciou
5,454/7,113, PPG 5,983/7,470. Detailný [report experimentu 02](experiment_02/report.md)
obsahuje aj výsledky pôvodných modelov, sezónne porovnanie a kalibráciu.

Doplnené pred commitom: dva reprodukovateľné grafy, rozdiely metrík a sezónne
tabuľky, dátumová kontrola kalibrácie, testy zmeny budúcich remíz/pridania
neskorších sezón, metadáta vstupov a všetkých modulov a návody na spustenie.
Celá sada má 55 prechádzajúcich testov. Nezávislý prepočet zo zdrojového CSV
overil všetkých 900 odhadov (180 riadkov × 5 modelov), historické podiely
remíz a všetkých 50 riadkov metrík. Skontrolované boli aj grafy a hashe.
Výsledky experimentu 01 sa nemenili.

## Dohodnuté pokračovanie: experiment 03

Podľa posledných pokynov konzultanta nasleduje optimalizácia exponentu pre
jednotlivé ligy a 5-násobná krížová validácia po celých sezónach: pri 10
kompletných ročníkoch vždy 8 na optimalizáciu a 2 na vyhodnotenie, každý ročník
raz v teste. Ďalším výstupom má byť porovnanie predikovaného poradia tímov
so skutočným. Tieto úlohy patria až do samostatného experimentu 03.

Pred jeho implementáciou treba určiť optimalizačnú metriku a rozdelenie
sezón. Testovacie sezóny nesmú vstupovať do optimalizácie exponentu ani do
odhadov ďalších parametrov. Validácia 8+2, ktorá môže trénovať na neskorších
rokoch, hodnotí prenos medzi historickými sezónami; nie je automaticky
chronologickou predikciou budúcnosti. Dataset má šesť líg, nie desať;
počet desiatich sa tu vzťahuje na sezóny. Ligy s odlišnou dĺžkou sezóny alebo
neúplnými ročníkmi potrebujú samostatne overiť použiteľnú vzorku.

## Čo bolo hotové pred experimentom

Repozitár obsahoval Python balík, CSV/Parquet loader, adaptéry dvoch
zápasových zdrojov, validáciu ich zhody, Pythagorejský podiel a MAE/RMSE.
Dátové adresáre a notebooky boli prázdne. Neboli vykonané reálne experimenty.

Pôvodný Understat loader predpokladal jeden celý zápas na riadok. Dodaný
Kaggle export má jednu perspektívu tímu na riadok, preto vznikol samostatný
adaptér. Kontrola zhody dvoch zdrojov sama nepotvrdzuje úplnosť rozpisu;
nový pilot kontroluje aj každý pár domáci–hosť.

## Splnenie zadaných úloh

| Úloha | Výsledok |
| --- | --- |
| 1. Oboznámiť sa s Understat datasetom | Overené tri súbory, schémy, 6 líg, roky 2014–2024, kvalita a možnosti použitia. |
| 2. Nastaviť experiment s pevným exponentom | Exponent 2 pre góly aj xG; celosezónny odhad a samostatná predikcia po 19 zápasoch. |
| 3. Vykonať a vyhodnotiť na jednej lige | EPL 2014/15–2023/24, 3 800 zápasov, 200 tímových sezón; MAE, RMSE, bias a grafy. |

Podrobný [prieskum datasetu](understat_dataset.md) a
[výsledkový report](experiment_01/report.md) sú hlavné podklady pre konzultáciu.

## Čo sa zmenilo v kóde

- `understat_dataset.py`: validácia tímových zápasov, kontrolované párovanie,
  sezónna agregácia a výber úplných ročníkov.
- `experiment.py`: retrospektívne odhady bodov a metriky s pevným exponentom.
- `forecast.py`: predikcia konečných bodov iba z prvých 19 zápasov tímu,
  vrátane referenčného modelu založeného na bodovom priemere.
- `pilot.py`: celý reprodukovateľný výpočet z ZIP, audit, výsledky a grafy.
- `pythagorean.py`: odmietnutie nekonečných/NaN vstupov a numericky stabilnejší výpočet.
- Testy overujú aj nedovolené použitie budúcich výsledkov, neúplné sezóny,
  chybné skóre, dvojité počítanie a nejednoznačné párovanie.

## Hlavné výsledky

Overenie: všetkých **36 automatizovaných testov prešlo**. Nezávislý prepočet
priamo z CSV cez štandardnú knižnicu Python potvrdil všetkých 200 predikcií
pre tri modely a súhrnné MAE/RMSE. Overené boli aj hashe kódu, ignorovanie
raw dát Gitom a čitateľnosť exportovaných grafov.

Pri predikcii po 19 zápasoch je MAE gólového modelu 7,365 bodu, xG modelu
6,040 bodu a bodového priemeru 6,040 bodu. xG má oproti gólom približne o 18 %
nižšiu MAE. Oproti jednoduchému bodovému priemeru sa však zlepšenie nepotvrdilo:
MAE je prakticky rovnaká a RMSE je pri xG o niečo vyššie (7,738 oproti 7,537).

Pri opisnom odhade z celej sezóny majú góly MAE 7,923 a xG 8,267 bodu.
Tieto dve nastavenia majú rozdielne dostupné informácie a nemajú sa interpretovať
ako rovnaká predikčná úloha.

## Čo treba uviesť školiteľovi

Cieľom sú body získané zo zápasov (3W + D), bez administratívnych odpočtov.
Predikčný čas je po 19 odohraných zápasoch každého tímu; nejde o spoločný deň.
Exponent sa neoptimalizoval. Prevod podielu na body je jednoduchý 3N benchmark
bez modelu remíz. Preto sa vykazuje aj bias a porovnanie s PPG.
Výsledky sú opisné, bez tvrdenia štatistickej významnosti.

## Pôvodné návrhy po experimente 01 a ich stav

1. Korekcia remíz z predchádzajúcich sezón je dokončená v experimente 02.
2. Vyhodnotiť aj hranice po 10 a 28 zápasoch, vždy oproti rovnakému PPG benchmarku.
3. Optimalizácia exponentu a validácia po sezónach nasledujú v experimente 03 podľa pokynov vyššie.
4. Rozšíriť analýzu na ďalšiu ligu so zohľadnením počtu tímov a dĺžky sezóny.
5. Ak má cieľ predstavovať oficiálnu ligovú tabuľku, doplniť samostatný zdroj
   administratívnych bodových odpočtov. Voliteľne overiť výsledky cez football-data.co.uk.

Licencia a číslo verzie Kaggle nie sú uvedené v archíve a zostávajú neoverené.
Raw dáta sú lokálne a ignorované Gitom. Notebooky zatiaľ nie sú potrebné na
reprodukciu, všetko sa spúšťa cez CLI podľa README.
