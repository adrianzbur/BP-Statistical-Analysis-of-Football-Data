# Understat: preskúmanie dodaného datasetu

Zdroj uvedený používateľom: https://www.kaggle.com/datasets/codytipton/understat-data .
Kontrolovaný súbor: `data/raw/Understat-data.zip`. Rozbalené originály sú
v `data/raw/understat/`. Presný SHA-256 archívu je v
[`experiment_01/metadata.json`](experiment_01/metadata.json).
Zistenia sa vzťahujú na tento konkrétny archív, nie na aktuálny obsah webu.
Dátum stiahnutia a číslo verzie neboli uvedené. Archív neobsahuje licenciu.

## Čo je v archíve

| Súbor | Riadky | Stĺpce | Úroveň záznamu |
| --- | ---: | ---: | --- |
| `game_stats.csv` | 41 722 | 23 | Jeden tím v jednom zápase |
| `player_stats.csv` | 35 076 | 19 | Hráč, sezóna a tímové pôsobenie |
| `understat.db` | Dve tabuľky | Rovnaké schémy ako CSV | Alternatívne uloženie rovnakých dát |

CSV a SQLite tabuľky boli porovnané po riadkoch, s toleranciou 1e-12 pre
desatinné čísla; obsah sa zhoduje. Databázu preto nepripájame ako ďalšie
pozorovania. V zápasovej tabuľke je 197 klubových ID, v hráčskej 10 175 hráčskych ID.

## Časové a ligové pokrytie

Zápasy majú dátumy **1. 8. 2014 – 29. 9. 2024**. `season = 2014` označuje
ročník 2014/15; celý rozsah štítkov je 2014 až 2024. Dataset nie je aktuálny
do roku 2026, aj keď bol dodaný v roku 2026.

| Liga v CSV | Sezóny 2014–2023 | Čiastočná sezóna 2024: zápasy |
| --- | --- | ---: |
| `EPL` | 380 zápasov v každej z 10 sezón | 59 |
| `La liga` | 380 zápasov v každej z 10 sezón | 79 |
| `Bundesliga` | 306 zápasov v každej z 10 sezón | 45 |
| `Serie A` | 380 zápasov v každej z 10 sezón | 59 |
| `Ligue 1` | Zvyčajne 380; 2019 má 279, 2023 má 306 | 54 |
| `RFPL` | 240 zápasov v každej z 10 sezón | 80 |

Ligue 1 v sezóne 2019 obsahuje 27–28 zápasov na tím a v sezóne 2023 má
18 tímov. Pri rozšírení analýzy nemožno všade vyžadovať 20 tímov a 38 zápasov.
Úplný profil ligy a sezóny je v [`experiment_01/dataset_coverage.csv`](experiment_01/dataset_coverage.csv).
Úplný rozpis doma/vonku bol na účely experimentu overený pre vybrané EPL sezóny.

## Zápasové stĺpce

| Stĺpce | Význam a použitie |
| --- | --- |
| `id`, `club_name` | Klubové ID a názov. `id` sa opakuje v zápasoch, nie je to ID zápasu. |
| `league`, `season` | Liga a začiatkový rok sezóny; výber a skupinová agregácia. |
| `home_away` | `h` doma, `a` vonku. |
| `date` | Dátum a čas; chronologický výber prvých 19 zápasov. Časové pásmo export neuvádza. |
| `scored`, `missed` | Góly tímu a súpera v jednom zápase; sčítajú sa na GF a GA. |
| `xG`, `xGA` | Očakávané góly tímu a súpera; sčítajú sa pre xG model. |
| `result` | Výsledok z pohľadu tímu: `w`, `d`, `l`. |
| `wins`, `draws`, `loses` | Zápasové indikátory 0/1, nie priebežné sezónne počty. |
| `pts` | Body zo zápasu: 3, 1 alebo 0. Cieľ vzniká súčtom. |
| `xpts` | Zdrojový odhad očakávaných bodov. Nie je to skutočný počet bodov ani náš Pythagorejský odhad. |
| `npxG`, `npxGA`, `npxGD` | xG bez penált, proti tímu a ich rozdiel; možný ďalší experiment. |
| `ppda`, `ppda_allowed` | Ukazovatele prihrávok na obrannú akciu tímu/súpera; možný rozbor pressingu. |
| `deep`, `deep_allowed` | Zdrojové ukazovatele prihrávok do nebezpečných priestorov; doplnkové vysvetľujúce premenné. |

Presné definície priestorových hraníc PPDA/deep a postup výpočtu xpts nie sú
v archíve zdokumentované. Pred použitím v ďalšom modeli treba overiť metodiku
Understatu. Priemery pomerových metrík, napríklad PPDA, nesčítavať ako góly.

## Hráčske stĺpce

| Stĺpce | Význam a možné použitie |
| --- | --- |
| `player_id`, `name`, `season`, `team` | Identita a sezónne tímové pôsobenie hráča. |
| `position`, `games`, `time` | Pozícia, zápasy a odohrané minúty; normalizácia výkonu, napr. na 90 minút. |
| `goals`, `shots`, `xG` | Góly, strely a xG; efektivita zakončenia. |
| `assists`, `xA`, `key_passes` | Asistencie a tvorba šancí. |
| `yellow`, `red` | Karty. |
| `npg`, `npxG` | Góly a xG bez penált. |
| `xGChain`, `xGBuildup` | Zdrojové ukazovatele zapojenia do útokov; presnú metodiku overiť pred interpretáciou. |

Hráčska tabuľka nemá dátumy jednotlivých zápasov ani stĺpec ligy. V tejto
podobe nie je vhodná ako zdroj priebežných hráčskych vstupov po 19 zápasoch.
Pre prvý tímový experiment ju nepoužívame. Kľúč `(player_id, season)` má
1 618 opakovaní; po zahrnutí `team` nie sú duplicity. Tieto riadky sa nesmú
automaticky zmazať: reprezentujú rôzne tímové pôsobenia v sezóne.

## Kontroly a agregácia

- V oboch CSV je nula prázdnych hodnôt. Numerické stĺpce sú konečné.
- V zápasovej tabuľke nie sú duplicity `(league, season, club_name, date)`.
- Góly, výsledky, indikátory výhry/remízy/prehry a body sú konzistentné.
- Všetkých 20 861 domácich riadkov má práve jeden zodpovedajúci hosťujúci
  riadok podľa ligy, sezóny, času a zrkadlového skóre/xG.
- Export neobsahuje súpera ani ID zápasu. Rekonštrukcia dvojíc preto pri
  nejednoznačnosti skončí chybou; nepoužíva približné spájanie.
- Tímové súčty vznikajú iba z vlastných riadkov tímu. Pri počítaní zápasov
  ligy treba dve perspektívy spojiť, aby sa počet zápasov nezdvojnásobil.
- EPL 2014–2023 má vždy 20 tímov, 38 zápasov na tím a každý usporiadaný pár
  domáci–hosť práve raz. Kontroluje sa aj rovnováha GF/GA a xG/xGA.
- Body sú `3W + D`; z tohto exportu nemožno zistiť administratívne odpočty.

Audit: [`experiment_01/dataset_audit.json`](experiment_01/dataset_audit.json).
Rozsahy a chýbajúce hodnoty všetkých stĺpcov:
[`experiment_01/column_profile.csv`](experiment_01/column_profile.csv).

## Čo je použiteľné pre bakalársku prácu

Prvý experiment je uskutočniteľný priamo z `game_stats.csv`: porovnanie
Pythagorejského odhadu z gólov a xG, po sezónach a s chronologickými hranicami.
Výsledky sú v [`experiment_01/report.md`](experiment_01/report.md).
Neskôr možno skúmať npxG, domáce a vonkajšie výkony, dĺžku pozorovaného obdobia,
ligové rozdiely a odhad exponentu na historických tréningových sezónach.
Hráčska analýza je samostatné rozšírenie; na splnenie prvých troch úloh nie je potrebná.
