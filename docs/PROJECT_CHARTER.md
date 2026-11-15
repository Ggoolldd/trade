# Projektni charter

Status: prihvaćena razvojna osnova, 2026-11-15. Izvor:
[PROJECT_SPEC.md](../PROJECT_SPEC.md), odjeljci Neupitne projektne odluke i Pravila o redoslijedu.

## Ciljevi

Privatna upotreba za vlasnikovo istraživanje, simulaciju i nadzor portfelja.
Podržani opseg su long-only dionice, regulatorno prikladni europski UCITS ETF-ovi
za hrvatskog retail korisnika te spot BTC/EUR i ETH/EUR. Dostupnost i preciznost
instrumenata moraju se potvrditi metapodacima pružatelja.

Razviti dokaziv proces od podataka preko signala i risk odluke do virtualnog
izvršenja, dvostrukog knjigovodstva i usporedbe s transparentnim benchmarkom.
Početni virtualni saldo je 10.000 EUR: simulacijski primjer, ne preporuka ulaganja.

## Granice i non-goals

Nema leverage, shortanja, derivatives, margina, withdrawals ni transfera.
Nema upravljanja tuđim novcem, javnih investicijskih preporuka, prodaje signala
ili obećanja povrata. Pozitivan backtest nije dokaz budućeg prinosa.
Prvi release ne uključuje stvarno trgovanje ili automatsko uključivanje LIVE.

Android je klijent za nadzor i autorizirane kontrole. Nije trading engine i ne
pohranjuje brokerske tajne. Backend radi neovisno o telefonu; nedostupnost klijenta
ne smije zaobići risk zaštitu ili prikazati lažan uspjeh.

## Ograničenja i sigurnost

PAPER je zadani režim. SHADOW je pasivan. Model predlaže intent, Risk Engine ima
neovisno pravo odbijanja. Svaki financijski događaj zahtijeva audit i idempotency;
UNKNOWN broker ishod zaustavlja retry do reconciliationa. Novac koristi Decimal,
pohrana vremena UTC, podaci usable_at i tržišne kalendare.

Nema stvarnih tajni u repozitoriju, APK-u ili logovima. Nema withdrawal/transfer
ovlasti. Odvojeni LIVE deployment, 90+ dana forward PAPER dokaza, brokerski audit,
zaseban owner unlock i MFA preduvjeti su za eventualni budući pilot. Ovaj charter
ne daje taj unlock. STOP ostaje latched do odvojenog autoriziranog resumea.

## Kriteriji uspjeha

| Područje | Provjerljiv kriterij |
| --- | --- |
| Integritet | Replay istih događaja ne udvostručuje cash, fillove ili PnL; ledger se usklađuje |
| Risk | Svi negativni critical-path testovi prolaze; stale feed i UNKNOWN blokiraju nove naloge |
| Istraživanje | Reproducibilan dataset i konfiguracija; no-lookahead i troškovi; baseline usporedba |
| Operacije | Restart, STOP i outage scenariji imaju dokaze; nema gubitka audita |
| Android | Status režima i stale/offline prikaz su točni; osjetljive kontrole autorizira server |
| Promocija | Dokazi gateova i vlasnikova odluka; nedostatak dokaza znači odbijanje |

Profit nije uvjet prolaza ni obećanje. Razvojni taskovi prolaze samo uz stvarno
izvršene primjerene provjere; infrastrukturne blokade ostaju PARTIAL.
