# Režimi i fail-closed prijelazi

Normativni dizajn za TAI-004; runtime provedba dolazi kasnije.
Izvori: [specifikacija](../PROJECT_SPEC.md), [charter](PROJECT_CHARTER.md).

## Operacije

Prazna konfiguracija znači PAPER. Nepoznata, pogrešno napisana ili proturječna
vrijednost konfiguracije znači startup error, nikada fallback u LIVE.

| Operacija | PAPER | SHADOW | LIVE_LOCKED | LIVE_UNLOCKED |
| --- | --- | --- | --- | --- |
| Public market data | Da, uz quality provjere | Da | Da | Da |
| Stvarni account read | Ne u početnom razvoju | Samo zasebno autorizirani read-only adapter | Samo read-only ovlasti | Prema account scopeu |
| Strategija / predloženi intent | Da | Analitički, bez submita | Preview bez submita | Da |
| Virtualni place / cancel | Da, virtualni račun | Ne | Ne | Ne |
| Stvarni place / cancel | Ne | Ne | Ne | Samo uz sve gateove i risk approval |
| Withdraw / transfer / margin / short | Ne | Ne | Ne | Ne |
| Audit / reconciliation | Da, virtualni ledger | Da, read-only usporedba | Da | Da |

LIVE_LOCKED i LIVE_UNLOCKED su sigurnosna stanja jednog LIVE režima, a ne dodatne
vrijednosti mode varijable. Početni release podržava samo PAPER; SHADOW i LIVE
konfiguracije moraju biti odbijene dok njihova provedba nije verificirana.

## Identitet i izolacija

Deployment, account, intent i execution adapter nose isti eksplicitni mode.
PAPER account ima isključivo virtualni cash (početni primjer 10.000 EUR) i PAPER
instrument/ledger namespace. Nije dopušten fallback s PaperBroker na pravi broker.
Odvojiti DB, mrežu, tajne i account IDs za LIVE; klijentski header nije izvor režima.

## Prijelazi i dozvola

| Izvor / događaj | Rezultat | Provjera / negativni primjer |
| --- | --- | --- |
| Startup bez mode | PAPER | Ne učitati trade tajne |
| Startup s nepoznatim modeom | Odbiti start | `LIV`, prazna eksplicitna vrijednost ili `paper/live` ne prolaze |
| PAPER -> SHADOW | Zaustaviti worker, novi izolirani session, read-only adapter | Nema konverzije postojećeg virtualnog naloga u stvarni |
| PAPER/SHADOW -> LIVE | Zabranjen in-place prijelaz | REST promjena modea ili environment flag sama nije unlock |
| LIVE deployment start/restart | LIVE_LOCKED | Stari unlock se ne obnavlja automatski |
| LIVE_LOCKED -> UNLOCKED | Samo nakon svih gateova i owner step-up autorizacije | Jedan nedostajući dokaz znači deny |
| Unlock expiry / STOP / auth expiry / stale feed / UNKNOWN | Zaključati nove naloge, incident i reconciliation | Nema retry create nakon nepoznatog ishoda |
| Resume poslije STOP | Odvojeni owner postupak, ponovno provjeriti dokaze | Obični restart ili novi signal ne resetira latch |

Uvjeti za budući LIVE submit su logički AND: zaseban LIVE deployment; LIVE account;
broker permissions audit bez withdrawal/transfer; 90+ dana stvarnog forward PAPER
dokaza i prethodni gateovi; važeći owner unlock uz MFA i rok; ispravan whitelist i
hard cap; svježi podaci; zdrava reconciled sesija; risk approval; STOP nije latched.
Nepoznat ili nedostajući uvjet uvijek je false. Model ne smije mijenjati te uvjete.

## STOP i otvoreni nalozi

STOP odmah blokira nove namjere/submit, ali ne tvrdi da su postojeći nalozi otkazani.
U budućem LIVE kontroliranom postupku cancel/reconcile postojećih naloga ima zasebnu
recovery autorizaciju, audit i idempotency; expiry običnog unlocka ne smije potaknuti
nove kupnje ni onemogućiti praćenje ishoda. Ne likvidirati pozicije automatski.

## Obvezni acceptance scenariji za provedbu

1. PAPER intent + LIVE adapter/account odbija se prije mrežnog poziva.
2. SHADOW ne šalje ni virtualni ni stvarni nalog, čak uz trade ključ u okolini.
3. LIVE s isteklim MFA/unlockom ili bez jednog gatea odbija submit.
4. UNKNOWN blokira isti idempotency key i novi create do resolutiona.
5. Restart nakon STOP ostaje zaustavljen; read-only health i reconciliation rade.
6. Dva istodobna zahtjeva za isti intent stvaraju najviše jedan efekt.

Ovo su ugovori budućih testova, ne izvještaj o već implementiranom brokeru.
