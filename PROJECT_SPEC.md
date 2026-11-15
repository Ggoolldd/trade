# TRADING AI — Projektna specifikacija 1.0

**Datum početka:** 15.11.2026.  
**Namjena:** privatna Android aplikacija i backend za autonomno trgovanje dionicama, europskim UCITS ETF-ovima i spot kriptovalutama.  
**Status:** plan i zadaci; ništa nije implementirano samim stvaranjem ovog paketa.

## Neupitne projektne odluke

- Android **Kotlin, Jetpack Compose, Hilt**, služi za nadzor i upravljanje; backend u Pythonu **FastAPI** neovisno radi na serveru.
- **PostgreSQL, Alembic, Redis, Docker Compose**. Domena: instrument/venue, market data, strategija, signal, order intent, risk approval, order, fill, ledger, portfolio, broker, audit, incident.
- Početni simulacijski račun **10.000 EUR**. Taj broj je primjer, ne preporuka iznosa ulaganja.
- Režimi: **PAPER** (samo virtualni nalozi), **SHADOW** (pasivno promatranje stvarnog feeda/računa), **LIVE** (stvarni nalozi). DEFAULT PAPER. Nema automatskog prelaska u LIVE.
- Model može **predložiti namjeru trgovanja**, ali nikada ne može zaobići **Risk Engine**. Live unlock zahtijeva korisnikovu zasebnu eksplicitnu odluku, MFA i sigurnosne provjere. Kad je LIVE aktiviran, nalozi mogu nastajati autonomno unutar limita.
- Prva verzija: **bez leverage, short, derivatives, margin, withdrawals i transfera**. Koristiti isključivo spot i long-only kupnje/prodaje.
- Kriptovalute: **BTC/EUR i ETH/EUR** (konačna dostupnost/lot size potvrđuju se metapodacima burze), dionice: konfigurabilna mala lista likvidnih instrumenata, ETF-ovi: samo regulatorno prikladni UCITS za hrvatskog retail korisnika.
- Početni PAPER limiti **predložene testne vrijednosti**: 5% za pojedinu novu kupnju, 0,5% *planiranog* rizika po transakciji, 2% dnevni halt, 5% tjedni halt, 10% drawdown halt, 25% kripto ukupne izloženosti. Nisu jamstva maksimalnog stvarnog gubitka. Politike su verzionirane.
- Novčani iznosi: **Decimal**, nikad binary float. Timestampi u UTC, eksplicitni tržišni kalendari i FX konverzije u EUR.
- No-lookahead: povijesni podaci s usable_at, samo tada poznate činjenice i dostupni instrumenti; korektni naknade, spread, slippage, market data greške i partial fills.
- Svaka promjena stanja financija je auditabilna, idempotentna i usklađena s brokerskim evidencijama. UNKNOWN broker result blokira retry dok se nalog ne razriješi.
- Autonomija nije obećanje zarade. Sigurnost, dokazivost, usporedivost s benchmarkom i fail-closed ponašanje imaju prednost pred učestalošću trgovanja.

## Arhitektura servisa

1. `market_data`: prikup, normalizacija, quality, provenance, replay.
2. `research`: features, indikatori, train/test i eksperimentiranje.
3. `strategies`: versionirane strategije i kandidati naloga.
4. `ai_engine`: ML candidate models, experiment registry, champion/challenger.
5. `risk_engine`: pre-trade gate, exposure, stop, HALT, idempotency.
6. `execution`: paper i broker adapter, state machine, reconciliation.
7. `portfolio`: ledger, PnL, snapshots, tax export.
8. `api`: Android auth, status, portfolio, orders, alerts, emergency STOP.
9. `monitoring`: metrics, alerts, audit log, incident handling.

## Live brokers: potvrđene tehničke činjenice i izvori

- **IBKR TWS/IB Gateway API**: TWS/IBGW koristi socket client, autentificirani GUI login; automatski restart može pokrivati radni tjedan, ali se tipično traži ponovno unošenje vjerodajnica nakon tjednog resetiranja. Nije dopušteno pretpostaviti potpuno headless login. Službeno: https://www.interactivebrokers.com/docs/tws-api/doc/architecture/the-trader-workstation/the-ib-gateway
- **Kraken**: službeni REST/WebSocket API za naloge i autorizirane kanale; mora se koristiti najmanji nužni skup ovlasti, nikada withdrawal. Službeno: https://docs.kraken.com/api/
- **Hrvatska/MiCA**: prije live korištenja provjeriti pravni status pružatelja na aktualnim Hanfa/ESMA registrima. Službeno: https://www.hanfa.hr/vijesti/pruzanje-kriptousluga-od-1-srpnja-2026-za-drustva-obvezna-kriptolicenca-i-upis-u-hanfine-registre-a-korisnike-se-poziva-na-oprez/ i https://www.esma.europa.eu/esmas-activities/digital-finance-and-innovation/markets-crypto-assets-regulation-mica
- Prije svake implementacije vanjskog API-ja provjeriti **najnoviju službenu dokumentaciju** i eventualne promjene uvjeta.

## Pravila o redoslijedu

- Prije svih market, AI i Android prikaza: API, baza, monitoring i test framework.
- Prije prve simulirane strategije: paper ledger, state machine i Risk Engine.
- Prije ML: transparentni baseline, backtesting, no-leakage i benchmark.
- Prije LIVE: najprije 90+ dana dokumentiranog forward PAPER rezultata, contract tests, korisnikov zaseban unlock i dokazi o statusu brokera.
- Oznaka `PASS` je dopuštena **samo ako su pokrenuti odgovarajući testovi**. Inače status `PARTIAL` uz konkretan razlog.

## Zadaci

Svaki zadatak je samostalna Markdown uputa u `cursor_tasks/TAI-XXX.md`. Prati redoslijed u `ROADMAP.md` ili `TASKS_INDEX.csv`. Cursor treba odraditi **jedan po jedan zadatak** i izvijestiti prije nastavka.
