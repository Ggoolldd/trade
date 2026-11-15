# Plan kvalitete i testna piramida

TAI-009; ugovor za naredne implementacijske zadatke. Izvori:
[specifikacija](../PROJECT_SPEC.md), [događaji](TRADING_EVENTS.md),
[prijetnje](THREAT_MODEL.md). Ovo nije izvještaj o već aktivnom CI-u.

## Razine i pravila prolaza

| Razina | Primjer | Izolacija / artefakt | PASS |
| --- | --- | --- | --- |
| Unit | Decimal granica, risk limit točno ispod/na/iznad praga, zabranjen state transition | Bez mreže, kontrolirani clock; JUnit XML i coverage | Sva očekivanja prolaze, deterministično; kritične negativne grane obvezne |
| Integration | PostgreSQL constraint, migration up/down, atomic ledger + consumed event | Posebna test DB/volume; DB verzija i migration log | Stvarni PostgreSQL, ne SQLite zamjena; balans i rollback dokazani |
| Contract | Isti canonical nalog na PaperBroker i fixture broker adapterima | Sanitizirani verzionirani upstream fixtures, bez tajni | Payload, precision i error mapping zadovoljavaju ugovor; ne tvrditi da je broker live |
| E2E | Login -> virtualni intent -> risk -> fill -> portfolio; Android STOP do backend latcha | Izolirani PAPER backend + emulator; trace/screenshots | Provjereni backend efekti i UI stale/error stanja, ne samo HTTP 200 |
| Fault injection | Kill poslije submit zapisa, prije acknowledgmenta; duplicate fill; DB unavailable | Kontrolirani fault hooks, timeline i event IDs | Nema duplih naloga/knjiženja; UNKNOWN i HALT ostaju dok nema reconciliation dokaza |
| Dokumenti | Lokalne reference, encoding, review acceptance tablice | node scripts/check-docs.mjs; semantic review u reportu | Sve reference postoje, odlike zadatka stvarno pregledane; ne zamjenjuje runtime testove |

Najviše brzih unit testova, manji broj stvarnih integration/contract testova,
selektivni E2E i obvezni failure scenariji na kritičnom putu. Ne postavljati broj
testova kao zamjenu za dokaz invarijante.

## Kritične grane i pokrivenost

Risk/execution/ledger moraju imati 100% pokrivenosti identificiranih safety odluka:
PAPER/LIVE mismatch, risk reject, expiry, stale/future feed, exposure/cash granice,
STOP, UNKNOWN, idempotency konflikt, duplicate i out-of-order fill, race i rollback.
Linijski/branch alat cilj je najmanje 95% branch coverage za te module; prag sam
ne dokazuje sigurnost. Svaka preostala nepokrivena grana zahtijeva dokumentiran
razlog i ne smije biti put koji odobrava nalog. Testovi namjerno moraju pasti ako
se deny uvjet ukloni. Za ostali backend početni ukupni cilj je 80% branch coverage.

## CI blokade i promocija

TAI-024 implementira automatizaciju: format/lint, type check, unit/contract,
PostgreSQL integration kad postoji schema, migration drift, OpenAPI compatibility,
secret/dependency scan i docs checks. Failed, missing ili skipped critical suite
blokira merge/release; lokalni PASS nije tvrdnja da je udaljeni CI izvršen.

Deploy PAPER traži build, health/ready smoke i rollback dokaz. Strategija traži
ledger+risk gate; ML traži reproducibilni baseline/no-lookahead. LIVE traži odvojeni
gate s 90+ dana forward PAPER, permissions auditom i owner odobrenjem/MFA.
Offline fixture ili backtest ne može zamijeniti forward dane.

## Reproducibilnost i artefakti

Za svaki task: početni HEAD i task commit kroz Git history, promijenjene datoteke,
točna komanda, exit code, dependency/runtime verzije, report i redacted log.
Za eksperimente dodatno seed, dataset hash, usable_at cutoff i konfiguracija.
Fake clock u unit testu mora biti eksplicitan; ne nazivati ga vremenom pravog feeda.

Čuvati docs/reports/TAI-XXX.md i kratke tekstualne logove bez tajni u Git-u.
Veliki test artefakti idu u kontrolirani artifact store kasnije, s checksumom i
retentionom. Dok taj store ne postoji, ne tvrditi da su screenshotovi pohranjeni.

## Rad kad okruženje nedostaje

Ako nema Pythona, DB-a, Docker daemona ili Android SDK-a, prvo pokušati izolirani
lokalni razvojni alat. Ne mijenjati tuđe servise i ne kupovati resurse. Ako se
obvezni acceptance test ne može izvršiti, task je PARTIAL s preciznom blokadom;
ne nastavljati na task kojem je to preduvjet. Docs review sam ne dokazuje API build.
