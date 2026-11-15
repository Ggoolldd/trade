# TRADING AI — svi Cursor zadaci

**189 samostalnih zadataka, 13 faza.**

Pročitaj `PROJECT_SPEC.md` i `CURSOR_MASTER_PROMPT.md` prije pokretanja. Naredni zadatak ne izvršava se automatski.

## Faza 00 — Arhitektura, sigurnosna pravila i radno okruženje

### TAI-001 — Inicijalizacija repozitorija
**Preduvjet:** —

**Implementacija:** Kreiraj novi Git repozitorij TRADING-AI s monorepo mapama android, backend, docs, infrastructure, research i cursor_tasks; dodaj .gitignore za Python, Gradle, baze i tajne, LICENSE odluku ostavi dokumentiranom.

**PASS:** git status čist nakon inicijalnog commita; nijedna tajna nije verzionirana

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-002 — Projektni charter i granice
**Preduvjet:** TAI-001

**Implementacija:** Napiši docs/PROJECT_CHARTER.md: privatna upotreba, dionice/UCITS ETF/spot kripto, bez poluge i shortanja, simulacija prvo, Android nije trading engine, nema obećanja povrata.

**PASS:** dokument pokriva ciljeve, non-goals, ograničenja i kriterije uspjeha

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-003 — ADR odabira tehnologija
**Preduvjet:** TAI-002

**Implementacija:** U docs/adr/0001-stack.md obrazloži Kotlin/Compose/Hilt, Python/FastAPI, PostgreSQL/Alembic, Redis, Docker; naznači verzioniranje, licence i održavanje.

**PASS:** ADR ima alternative, razloge i posljedice izbora

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-004 — Načini PAPER, SHADOW i LIVE
**Preduvjet:** TAI-003

**Implementacija:** Definiraj strogu domensku specifikaciju režima PAPER, SHADOW, LIVE; PAPER koristi virtualni račun; SHADOW prati podatke ali ne trguje; LIVE zahtijeva svjesno otključavanje i odvojen deployment.

**PASS:** tablica dozvoljenih operacija i fail-closed prijelaza je testabilna

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-005 — Specifikacija trgovačkih događaja
**Preduvjet:** TAI-004

**Implementacija:** Opiši evente signal, intent, risk_decision, submit, acknowledgment, partial_fill, fill, cancel i reconcile, uključujući correlation_id i idempotency_key.

**PASS:** postoji dijagram stanja i zabranjenih prijelaza

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-006 — Politika novca, valuta i vremena
**Preduvjet:** TAI-005

**Implementacija:** Dokumentiraj Decimal umjesto float za iznose i količine, UTC u bazi, timezone burze za raspored, EUR izvještavanje, FX izvore i tolerancije.

**PASS:** primjeri pokrivaju EUR, USD, BTC, ljetno računanje vremena

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-007 — Threat model i matrica ovlasti
**Preduvjet:** TAI-006

**Implementacija:** Popiši napadače, povjerljive podatke, API ključeve, uređaje, načine kompromitacije, zabranu withdrawal ovlasti i least-privilege matrice.

**PASS:** najmanje 12 konkretnih prijetnji i ublažavanja u dokumentu

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-008 — Pravila za Cursor agente
**Preduvjet:** TAI-007

**Implementacija:** Kreiraj .cursor/rules/engineering.mdc s obvezom: samo aktivni task, prvo inspect, ne izmišljati PASS, ne mijenjati tuđe projekte, sigurni Git, testovi i final report.

**PASS:** pravila su primjenjiva i uključuju format izvještaja

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-009 — Plan kvalitete i testne piramide
**Preduvjet:** TAI-008

**Implementacija:** Definiraj unit/integration/contract/e2e/fault-injection razine, minimalnu pokrivenost kritičnih grana risk/execution, CI blokade i artefakte.

**PASS:** svi tipovi testova imaju primjere i pravila prolaza

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-010 — Dokumentiranje kapaciteta i troškova
**Preduvjet:** TAI-009

**Implementacija:** Procijeni minimalan lokalni i VPS razvojni profil, storage za OHLCV, rate limitove, trošak market data feedova i granice prvog releasea bez kupnje servisa.

**PASS:** tablica troškova razlikuje poznato, procjenu i nepoznato

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

## Faza 01 — Backend i razvojna infrastruktura

### TAI-011 — Backend FastAPI skeleton
**Preduvjet:** TAI-010

**Implementacija:** Postavi backend kao Python projekt s paketom app, health endpointima /health/live i /health/ready, OpenAPI i urednim startup/shutdown lifecycleom.

**PASS:** pytest health test PASS; API se pokreće lokalno bez vanjskih API ključeva

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-012 — Konfiguracijski sustav
**Preduvjet:** TAI-011

**Implementacija:** Dodaj tipizirane postavke za DB, Redis, trading_mode i feedove; provjeri konfiguraciju na startu; secure defaults PAPER, LIVE zabranjen bez eksplicitnih preduvjeta.

**PASS:** neispravan env fail-fast; default ne može poslati live order

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-013 — Docker Compose development
**Preduvjet:** TAI-012

**Implementacija:** Kreiraj dev Compose s PostgreSQL, Redis i backendom; healthcheck, named volume i portovi na localhost gdje je moguće; bez privilegiranih kontejnera.

**PASS:** docker compose config PASS; servisi healthy

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-014 — PostgreSQL i Alembic
**Preduvjet:** TAI-013

**Implementacija:** Dodaj ORM/session layer, Alembic setup, baseline migraciju te test migracija up/down na praznoj bazi.

**PASS:** migracija naprijed/nazad PASS; nema ručnih SQL koraka

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-015 — Zajednički ID i tipovi
**Preduvjet:** TAI-014

**Implementacija:** Implementiraj UUID primarne ključeve, Decimal tipove, enums, CreatedAt UTC, canonical error schema i request_id middleware.

**PASS:** testovi serijalizacije i grešaka PASS

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-016 — Instrumenti i tržišta u bazi
**Preduvjet:** TAI-015

**Implementacija:** Modeliraj venues, instruments, instrument_aliases, quote_currencies, trading_hours i instrument_status uz jedinstvene indekse.

**PASS:** migracije i unique-constraint testovi PASS

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-017 — Računi i trading profili
**Preduvjet:** TAI-016

**Implementacija:** Modeliraj paper accounts, trading_profiles, account_permissions i account_mode; live/prod identiteti strogo odvojeni.

**PASS:** testovi ne dopuštaju mapiranje PAPER naloga na LIVE račun

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-018 — Audit append-only
**Preduvjet:** TAI-017

**Implementacija:** Implementiraj append-only audit_events, correlation ID i hash chain ili ekvivalentan tamper-evident potpis događaja; bez spremanja API tajni.

**PASS:** izmjena ili brisanje audit zapisa je odbijeno za aplikacijsku rolu

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-019 — Autentifikacija API-ja
**Preduvjet:** TAI-018

**Implementacija:** Implementiraj siguran users/sessions model s hashiranim lozinkama, kratkotrajnim tokenima, revokacijom i ograničenjem pokušaja prijave.

**PASS:** auth integration tests pokrivaju expiry, logout, brute-force zaštitu

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-020 — Autorizacija i scope prava
**Preduvjet:** TAI-019

**Implementacija:** Uvedi role owner, readonly i system_worker te permission guard za konfiguraciju, naloge, risk i STOP; samo owner može mijenjati kontrolne parametre.

**PASS:** 403 za nedozvoljene scenarije kroz API testove

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-021 — Worker i queue infrastruktura
**Preduvjet:** TAI-020

**Implementacija:** Postavi Redis queue/worker za asinkrone poslove s retry/backoff pravilima, dead-letter konceptom i request tracingom.

**PASS:** test idempotentnog posla i failed-job evidencije PASS

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-022 — Scheduler i zaključavanje poslova
**Preduvjet:** TAI-021

**Implementacija:** Implementiraj scheduler s lease/advisory lock da se isti uvoz ili evaluacija ne izvodi dvaput pri restartu.

**PASS:** concurrent start test nema duplih jobova

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-023 — OpenAPI stabilnost i paginacija
**Preduvjet:** TAI-022

**Implementacija:** Standardiziraj paginaciju, filtriranje, API verzije, validaciju i greške; dodaj snapshot provjeru OpenAPI sheme.

**PASS:** API contract test detektira breaking change

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-024 — CI kvaliteta
**Preduvjet:** TAI-023

**Implementacija:** Uvedi GitHub Actions: pytest, ruff, mypy (postupno strict), migration smoke, secret scan te osnovni Gradle checks; zabrani merge kad ključni testovi padnu.

**PASS:** CI YAML validan; lokalne ekvivalentne provjere PASS

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-025 — Demo seed podaci
**Preduvjet:** TAI-024

**Implementacija:** Dodaj deterministički seed za instrumente, kalendar i fiktivni račun 10.000 EUR; seed ne sadrži stvarne ključeve.

**PASS:** ponovljeni seed ne duplicira podatke

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

## Faza 02 — Market data i integritet podataka

### TAI-026 — Catalog BTC/EUR i ETH/EUR
**Preduvjet:** TAI-025

**Implementacija:** Kreiraj canonical identifikatore BTC/EUR i ETH/EUR, mapping na venue simbol, pravila tick/lot size dohvaćena iz metapodataka.

**PASS:** test mapiranja i odbijanja nepostojećeg para PASS

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-027 — Catalog dionica i UCITS ETF-ova
**Preduvjet:** TAI-026

**Implementacija:** Dodaj 10-20 konfigurabilnih likvidnih dionica i 2-3 UCITS ETF kandidata kao metadata bez tvrde tvrdnje o dostupnosti; razluči ISIN, ticker, MIC i valutu.

**PASS:** ticker kolizije po burzi ne kvare identitet instrumenta

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-028 — Exchange calendar
**Preduvjet:** TAI-027

**Implementacija:** Implementiraj burzovne kalendare, vikende, praznike, DST i early close; za kripto zaseban 24/7 calendar.

**PASS:** test praznika i DST-a za odabrana tržišta PASS

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-029 — MarketDataProvider interface
**Preduvjet:** TAI-028

**Implementacija:** Definiraj adapter ugovor fetch_bars, fetch_quote, stream_quotes i provider_health; normaliziraj timeouts, retries i rate-limits.

**PASS:** mock provider prolazi contract suite

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-030 — Kraken javni OHLC ingest
**Preduvjet:** TAI-029

**Implementacija:** Implementiraj REST adapter za javne OHLC podatke s cursor/retention ograničenjima; dokumentiraj vremenske dosege i zamjenske izvore za staru povijest.

**PASS:** učitavanje demo uzorka + mocked HTTP edge tests PASS

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-031 — Kraken javni WebSocket stream
**Preduvjet:** TAI-030

**Implementacija:** Dodaj streaming cijena s ping/heartbeat, reconnect/backoff, redoslijedom poruka i detekcijom prekida.

**PASS:** simulirani disconnect/reconnect ne proizvodi lažne tickove

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-032 — Dionice: historijski feed adapter
**Preduvjet:** TAI-031

**Implementacija:** Implementiraj apstrakciju i jedan legalno dopušten historical provider; bez hardcodiranih besplatnih feedova za produkciju; provenance u bazi.

**PASS:** fixture-based ingest i license/coverage dokument PASS

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-033 — Canonical OHLCV pohrana
**Preduvjet:** TAI-032

**Implementacija:** Definiraj bar schema instrument, timeframe, start/end UTC, O/H/L/C/V, source, fetched_at i unique key; provjeri OHLC invariants.

**PASS:** loše i duple svijeće su odbijene ili karantenirane

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-034 — Canonical quote pohrana
**Preduvjet:** TAI-033

**Implementacija:** Definiraj bid/ask/last, quote_time, received_time, venue, sequence i market_state; preciznost Decimal.

**PASS:** stale quote i bid veći od ask označeni nevaljanima

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-035 — Backfill orkestracija
**Preduvjet:** TAI-034

**Implementacija:** Dodaj incremental backfill s checkpointima, rate-limit throttlingom, restart safe nastavljanjem i evidencijom rupe.

**PASS:** prekid i nastavak ne dupliciraju zapise

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-036 — Data quality provjere
**Preduvjet:** TAI-035

**Implementacija:** Automatski provjeri nedostajuće barove, outliere, nekonzistentne time zone, negativan volumen i stari timestamp.

**PASS:** quality report generira fail reason za svaki loš primjer

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-037 — Corporate actions model
**Preduvjet:** TAI-036

**Implementacija:** Dodaj split/dividend/currency change i adjusted/unadjusted price koncepte s point-in-time podacima.

**PASS:** test splita 2:1 čuva ekonomsku vrijednost pozicije

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-038 — FX referentni tečajevi
**Preduvjet:** TAI-037

**Implementacija:** Napravi provider za povijesne i aktualne FX tečajeve, konverzije u EUR, source timestamp i fallback politiku.

**PASS:** USD->EUR obračun reproducibilan na povijesni datum

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-039 — Market data entitlement status
**Preduvjet:** TAI-038

**Implementacija:** Dodaj evidenciju odgođenih i real-time feedova, mogućih zabrana redistribucije te fail-closed kada odgođeni feed nije dopušten za strategiju.

**PASS:** testovi blokiraju odluku s nedozvoljenim feed statusom

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-040 — Data lineage i dataset snapshot
**Preduvjet:** TAI-039

**Implementacija:** Spremi identitet izvora, import batch, checksum, verziju transformacije i immutable snapshot dataset ID.

**PASS:** isti dataset ID reproducira iste primjere

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-041 — Market data health API
**Preduvjet:** TAI-040

**Implementacija:** Dodaj /market-data/status s lagom, rupama, zadnjim ingestom i provider greškama, bez otkrivanja ključeva.

**PASS:** API test i graf podataka za demo status PASS

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

## Faza 03 — Paper broker, knjiga transakcija i portfelj

### TAI-042 — Trade intent schema
**Preduvjet:** TAI-041

**Implementacija:** Kreiraj order_intents s account, instrument, side, quantity/notional, source signal, timestamps i correlation ID; nema izravnog slanja preko modela.

**PASS:** validacija BUY/SELL i pogrešnog instrumenta PASS

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-043 — Order lifecycle state machine
**Preduvjet:** TAI-042

**Implementacija:** Definiraj DRAFT, APPROVED, SUBMITTING, SUBMITTED, PARTIAL, FILLED, CANCEL_PENDING, CANCELLED, REJECTED, UNKNOWN te dozvoljene prijelaze.

**PASS:** property tests odbijaju nedozvoljena stanja

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-044 — Virtualni cash account
**Preduvjet:** TAI-043

**Implementacija:** Implementiraj paper račun u EUR s rezerviranim/raspoloživim saldom i pravima samo simuliranih operacija.

**PASS:** kupnja ne može potrošiti više od raspoloživog novca

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-045 — Double-entry ledger
**Preduvjet:** TAI-044

**Implementacija:** Implementiraj uravnotežene journal_entries i journal_lines za svaku novčanu promjenu i proviziju; audit trace.

**PASS:** suma debita/kredita=0; migracijski test PASS

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-046 — PaperBroker adapter
**Preduvjet:** TAI-045

**Implementacija:** Implementiraj standardni BrokerAdapter u paper modu koji ne koristi nikakav vanjski private endpoint.

**PASS:** integration test prati da nema mrežnog slanja naloga

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-047 — Instrument precision validator
**Preduvjet:** TAI-046

**Implementacija:** Provjeri tick size, min lot, min notional i Decimal rounding prije kreiranja naloga.

**PASS:** rubni lot i min notional testovi PASS

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-048 — Order matching simulacija
**Preduvjet:** TAI-047

**Implementacija:** Implementiraj determinističko izvršavanje na sljedećem dostupnom quote/bar događaju, bez gledanja budućih cijena.

**PASS:** replay fixtures daje isti rezultat nakon 2 pokretanja

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-049 — Market i limit nalozi
**Preduvjet:** TAI-048

**Implementacija:** Simuliraj market i limit naloge s realnim uvjetima dostupnosti i neprihvaćanja, bez implicitnog garantiranja fill-a.

**PASS:** limit order izvan cijene ostaje otvoren

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-050 — Partial fills
**Preduvjet:** TAI-049

**Implementacija:** Podrži djelomična izvršenja, više fillova po nalogu, naknade po fillu i preostalu količinu.

**PASS:** 30% + 70% fill točno zatvara nalog

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-051 — Fee and spread model
**Preduvjet:** TAI-050

**Implementacija:** Napravi konfigurabilne spread/commission/taker-maker fee strukture po instrumentu i venueu, versionirane kroz vrijeme.

**PASS:** fee testovi za 2 tržišta i bez naknade PASS

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-052 — Slippage i likvidnost
**Preduvjet:** TAI-051

**Implementacija:** Dodaj konzervativan model slippagea i ograničene dubine likvidnosti; nemoj garantirati stop cijenu tijekom gapova.

**PASS:** scenarij gap-a bilježi veći gubitak od ciljanog

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-053 — Positions i cost basis
**Preduvjet:** TAI-052

**Implementacija:** Izvedi pozicije iz fillova, ponderiranu nabavnu cijenu i realizirani/nerealizirani PnL; razdvoji računovodstveno i porezno praćenje.

**PASS:** sekvenca kupi/prodaj ima točan PnL

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-054 — Reserved funds i otkazi
**Preduvjet:** TAI-053

**Implementacija:** Kod otvorenog buy naloga rezerviraj novac; partial/cancel oslobađa samo preostalo; SELL provjerava raspoloživu količinu.

**PASS:** paralelni buy nalozi ne mogu dvostruko potrošiti cash

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-055 — Portfolio snapshots
**Preduvjet:** TAI-054

**Implementacija:** Kreiraj snapshots na poznati timestamp, market value i available cash, with stale valuation status.

**PASS:** dnevni snapshoti ne mijenjaju se retroaktivno bez korekcijskog eventa

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-056 — Cash, fills i positions reconciliation
**Preduvjet:** TAI-055

**Implementacija:** Uvedi provjeru ledger saldo vs pozicije vs stanje brokera; mismatch => HALT, audit incident.

**PASS:** namjerno pokvaren fill detektiran bez automatskog prikrivanja

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-057 — Paper trading REST API
**Preduvjet:** TAI-056

**Implementacija:** Izloži read-only portfelj, naloge i transakcije te kontrolirani testni order-intent endpoint s auth i risk checkom.

**PASS:** OpenAPI i e2e mock scenariji PASS

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-058 — Historical paper replay
**Preduvjet:** TAI-057

**Implementacija:** Omogući puštanje vremenski označenih fixture događaja kroz isti broker/risk pipeline kao u stvarnoj simulaciji.

**PASS:** deterministički replay kroz 3 instrumenta PASS

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

## Faza 04 — Risk engine i fail-safe zaštite

### TAI-059 — Versioned risk policies
**Preduvjet:** TAI-058

**Implementacija:** Implementiraj risk_policy schema s defaultima 5% po kupnji, 0.5% planiranog rizika, 2% dnevni stop, 5% tjedni, 10% drawdown, 25% kripto izloženost; PAPER only default.

**PASS:** svaki policy ima verziju, vlasnika i audit događaj

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-060 — Pre-trade risk pipeline
**Preduvjet:** TAI-059

**Implementacija:** Implementiraj sinkronu provjeru svakog order_intenta kroz isti workflow koji može APPROVE, RESIZE ili REJECT.

**PASS:** bez tokena risk approvala izvršavanje je nemoguće

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-061 — Max single order exposure
**Preduvjet:** TAI-060

**Implementacija:** Ograniči kupnju po pojedinom nalogu i min/max veličine; ako minimum venuea prelazi dopušten limit odbij nalog.

**PASS:** test 5% notional limita i min-size konflikta PASS

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-062 — Position sizing model
**Preduvjet:** TAI-061

**Implementacija:** Izračunaj količinu prema stop distance, volatilnosti i planiranom risk budgetu; upozori da gap može premašiti planirani iznos.

**PASS:** nulta volatilnost i premali stop distance ne dijele s nulom

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-063 — Overall gross exposure
**Preduvjet:** TAI-062

**Implementacija:** Uvedi ukupni exposure limit i pravila da više istodobnih naloga rezervira buduću izloženost.

**PASS:** paralelni nalozi ne prelaze limit

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-064 — Crypto allocation cap
**Preduvjet:** TAI-063

**Implementacija:** Ukupni kripto exposure limit 25% u PAPER default profilu; računaj postojeće i pending buy pozicije.

**PASS:** simultani BTC/ETH intent ne probija limit

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-065 — Symbol concentration cap
**Preduvjet:** TAI-064

**Implementacija:** Ograniči udio jednog instrumenta/izdavatelja; povezane pozicije računaj zajedno kada se zna povezani exposure.

**PASS:** dva tickera istog izdavatelja ne zaobilaze limit

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-066 — Correlation/concentration guard
**Preduvjet:** TAI-065

**Implementacija:** Dodaj opcionalno ograničenje koreliranih izloženosti i fallback u slučaju nedovoljno povijesti.

**PASS:** bez podataka sustav odbija povećanje previše koncentrirane pozicije

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-067 — Daily stop logic
**Preduvjet:** TAI-066

**Implementacija:** Dnevni stop na stvarni mark-to-market gubitak od početka trgovačkog dana; uz jasnu timezone i reset politiku.

**PASS:** ostvareni + nerealizirani gubitak uključeni u test

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-068 — Weekly stop logic
**Preduvjet:** TAI-067

**Implementacija:** Implementiraj tjedni stop i reset prema eksplicitno definiranoj kalendarskoj konvenciji.

**PASS:** test tjedna s prijelazom mjeseca PASS

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-069 — Drawdown halt
**Preduvjet:** TAI-068

**Implementacija:** Izračunaj high-water mark portfelja i aktiviraj HALT na zadani drawdown; snapshoti i FX uključeni.

**PASS:** 10% pad aktivira blokadu novih naloga

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-070 — Stale data guard
**Preduvjet:** TAI-069

**Implementacija:** Blokiraj trgovanje kada je quote/starost feeda iznad instrument-specific praga ili je calendar nedostupan.

**PASS:** stale i missing bid/ask scenario FAIL CLOSED

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-071 — Price deviation / fat-finger guard
**Preduvjet:** TAI-070

**Implementacija:** Odbij kupnju po znatno odstupajućoj cijeni od referentne, nelikvidne instrumente i neprihvatljiv spread.

**PASS:** ekstremna cijena i negativna likvidnost odbijene

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-072 — Order rate limiter
**Preduvjet:** TAI-071

**Implementacija:** Ograniči broj naloga, izmjena i otkaza po vremenu, instrumentu i računu da spriječi petlje.

**PASS:** burst od 100 identičnih signala ne kreira 100 naloga

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-073 — Idempotent request handling
**Preduvjet:** TAI-072

**Implementacija:** Uvedi jedinstveni idempotency_key kroz decision->risk->execution->broker; unique constraints + safe retry.

**PASS:** paralelni duplikati rezultiraju najviše jednim stvarnim intentom

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-074 — Unknown order quarantine
**Preduvjet:** TAI-073

**Implementacija:** Nakon timeouta slanja označi UNKNOWN i blokiraj ponovno slanje do reconciliationa s brokerom.

**PASS:** inject timeout nakon submit-a ne stvara dvostruki nalog

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-075 — Emergency STOP ALL i latch
**Preduvjet:** TAI-074

**Implementacija:** STOP blokira nove naloge na svim putanjama; reset uz owner auth, razlog i audit; postojeće pozicije ne likvidiraj automatski.

**PASS:** STOP preživljava restart i nikakav buy prolaz ne radi

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-076 — Security fault injection matrix
**Preduvjet:** TAI-075

**Implementacija:** Automatiziraj testove: DB outage, broker disconnect, stale feed, Redis down, clock skew, restart između fillova i stop signal.

**PASS:** svaki kritični kvar završava HALT ili kontroliranim degradiranim stanjem

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

## Faza 05 — Strategije, signali i konstrukcija portfelja

### TAI-077 — Feature store point-in-time
**Preduvjet:** TAI-076

**Implementacija:** Implementiraj versionirani feature_store koji koristi samo podatke raspoložive u trenutku odluke, s valid_from i availability_time.

**PASS:** look-ahead test ne dopušta buduću informaciju

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-078 — Technical indicators library
**Preduvjet:** TAI-077

**Implementacija:** Dodaj EMA, SMA, ATR, RSI, realized volatility, volume change i normalizirani trend s minimalnim warmup razdobljima.

**PASS:** testovi uspoređeni s ručno provjerenim serijama

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-079 — No-trade baseline
**Preduvjet:** TAI-078

**Implementacija:** Strategija koja uvijek drži cash, služi kao kontrola za provjeru troška i rizika.

**PASS:** backtest bez naloga i PnL=0 prije FX promjena

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-080 — Buy-and-hold benchmark
**Preduvjet:** TAI-079

**Implementacija:** Benchmark kupnje i držanja pojedinog instrumenta uz realne troškove, usporediv početni datum i raspodjelu.

**PASS:** output benchmarka reproducibilan

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-081 — Equal-weight benchmark
**Preduvjet:** TAI-080

**Implementacija:** Implementiraj periodični jednako ponderirani rebalans s troškovima za odabrani svemir instrumenata.

**PASS:** rebalans zadovoljava sumu ciljanih težina i fee model

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-082 — Trend-following 1.0
**Preduvjet:** TAI-081

**Implementacija:** Napiši jednostavnu transparentnu trend strategiju (npr. EMA cross s filterom) i konfiguracijski registry parametara.

**PASS:** deterministički BUY/HOLD/SELL fixtures

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-083 — Momentum ranking 1.0
**Preduvjet:** TAI-082

**Implementacija:** Rangiraj instrumente po prošlom momentumu uz kontrolu volatilnosti i minimalnu povijest.

**PASS:** nema rangiranja instrumenta bez dovoljno podataka

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-084 — Volatility filter 1.0
**Preduvjet:** TAI-083

**Implementacija:** Napravi zasebni volatility gate koji smanjuje ili blokira pozicije pri nestabilnosti, ne predviđa siguran profit.

**PASS:** volatility spike mijenja risk decision

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-085 — Regime classifier (rule-based)
**Preduvjet:** TAI-084

**Implementacija:** Uvedi rule-based trend/range/high volatility režime i evidenciju razloga prebacivanja.

**PASS:** jasne granice i test prijelaza režima

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-086 — Signal contract standard
**Preduvjet:** TAI-085

**Implementacija:** Standardiziraj signal: strategy_id, version, instrument, score, direction, confidence metadata, generated_at, valid_until i source data hash.

**PASS:** schema contract test PASS

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-087 — Signal aggregation
**Preduvjet:** TAI-086

**Implementacija:** Kombiniraj više kompatibilnih signala u kandidatski trade intent, uz konfliktno pravilo i mogućnost NO TRADE.

**PASS:** suprotni signali ne uzrokuju dvije suprotne kupnje

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-088 — Portfolio optimizer v0
**Preduvjet:** TAI-087

**Implementacija:** Pretvori kandidatske signale u ciljane težine uz cash buffer, caps i izbjegavanje nepotrebnog turnovera.

**PASS:** ciljane težine i ukupni cash uvijek unutar limita

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-089 — Rebalancing planner
**Preduvjet:** TAI-088

**Implementacija:** Generiraj minimalni set naloga do ciljnih težina uz proviziju, minimalne lotove i porezne implikacije kao informaciju.

**PASS:** male razlike ispod praga ne trguju

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-090 — Decision explainability log
**Preduvjet:** TAI-089

**Implementacija:** Uz svaku odluku zabilježi featuree, signal, model/policy verziju, troškove i razlog BUY/HOLD/SELL/REJECT.

**PASS:** svaki nalog ima pregledan uzročni trag

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-091 — Strategy parameter registry
**Preduvjet:** TAI-090

**Implementacija:** Omogući deklarativne, versionirane parametre po instrumentu i timeframeu s validation schema.

**PASS:** pogrešan parametar ne može do produkcijskog starta

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-092 — Universe selection guard
**Preduvjet:** TAI-091

**Implementacija:** Odabir instrumenata samo iz whiteliste/availability liste, bez survivorship biasa za povijesne eksperimente.

**PASS:** delistirani instrumenti u starim podacima ne nestaju iz backtesta

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-093 — Multi-asset market exposure
**Preduvjet:** TAI-092

**Implementacija:** Računaj korelaciju i zajednički beta/risk exposure dionica, ETF-ova i kripta za pregled, bez automatiziranog ignoriranja starih podataka.

**PASS:** jednostavan fixture pokazuje agregirani exposure

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

## Faza 06 — Backtesting, evaluacija i znanstvena provjera

### TAI-094 — Event-driven backtest engine
**Preduvjet:** TAI-093

**Implementacija:** Izgradi backtest koji pušta market evente vremenskim redom kroz istu strategiju, risk i paper execution logiku.

**PASS:** deterministički test 2 instrumenta, ne koristi buduće barove

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-095 — As-of availability model
**Preduvjet:** TAI-094

**Implementacija:** Separiraj event_time, received_time i usable_at kako cijena zatvaranja ne bi bila poznata prije zatvaranja svijeće.

**PASS:** test namjernog look-ahead bug-a FAIL

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-096 — Point-in-time universe
**Preduvjet:** TAI-095

**Implementacija:** Historijski selection koristi tada poznate simbole, delistinge, corporate actions i podatke, bez današnjeg filtra pobjednika.

**PASS:** stari fixture uključuje uklonjeni instrument

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-097 — Corporate actions replay
**Preduvjet:** TAI-096

**Implementacija:** U backtestu ispravno prilagodi split, cash dividend i promjenu tickera u odgovarajućem trenutku.

**PASS:** 2:1 split ne generira lažan PnL

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-098 — Execution cost scenarios
**Preduvjet:** TAI-097

**Implementacija:** Podrži optimističan, bazni i konzervativni troškovni profil te stresni slippage/gap.

**PASS:** report jasno pokazuje osjetljivost na trošak

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-099 — Data splitting by time
**Preduvjet:** TAI-098

**Implementacija:** Implementiraj train/validation/test prema vremenu, uz configurable embargo tamo gdje postoji label overlap.

**PASS:** nijedan training zapis ne gleda u test prihodnost

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-100 — Walk-forward validation
**Preduvjet:** TAI-099

**Implementacija:** Orkestriraj rolling/expanding train/test foldove, uz spremanje konfiguracije i random seedova.

**PASS:** izvještaj po foldovima i agregat PASS

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-101 — Model-independent benchmark suite
**Preduvjet:** TAI-100

**Implementacija:** Usporedi sa cash, buy-and-hold i equal-weight, uz jednake datume i izloženost koliko je izvedivo.

**PASS:** benchmarki jasno prikazani uz strategiju

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-102 — Performance metrics package
**Preduvjet:** TAI-101

**Implementacija:** Neto prinos, CAGR kada ima smisla, volatility, Sharpe, Sortino, max drawdown, Calmar, hit rate, profit factor i turnover.

**PASS:** numerički unit testovi i nule/negativni slučajevi PASS

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-103 — Trade attribution report
**Preduvjet:** TAI-102

**Implementacija:** Analiza PnL po instrumentu, strategiji, sektoru/klasi imovine, naknadama i periodu.

**PASS:** suma atribucija slaže se s ukupnim PnL-om

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-104 — Sensitivity and parameter sweep
**Preduvjet:** TAI-103

**Implementacija:** Za ograničen skup parametara izračunaj surface rezultata; razdvoji od finalnog test seta.

**PASS:** finale nije optimizirano na test segmentu

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-105 — Bootstrap uncertainty analysis
**Preduvjet:** TAI-104

**Implementacija:** Dodaj blok bootstrap / scenario resampling i intervale pouzdanosti za metrike s jasno navedenim ograničenjima.

**PASS:** seed daje reproducibilan interval

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-106 — Stress test historical regimes
**Preduvjet:** TAI-105

**Implementacija:** Pokreni scenarije tržišnog pada, povećanog spreda, praznika, manjkavog feeda i velikog gap-a.

**PASS:** svaki scenarij ima eksplicitan rezultat i event trace

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-107 — Backtest report artifact
**Preduvjet:** TAI-106

**Implementacija:** Generiraj HTML/JSON/CSV izvještaj s verzijama koda, podataka, strategije, risk pravila, troškova i razlozima neuspjeha.

**PASS:** report ponovljiv iz spremljenih inputa

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-108 — Promotion gate for paper
**Preduvjet:** TAI-107

**Implementacija:** Definiraj formalni gate iz backtesta u real-time PAPER; potrebni su troškovi, no-leakage, benchmark i risk testovi, ne samo pozitivan PnL.

**PASS:** automatski gate odbija strategiju bez minimuma dokaza

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

## Faza 07 — Machine Learning i upravljanje modelima

### TAI-109 — ML data labeling
**Preduvjet:** TAI-108

**Implementacija:** Izradi label pipeline za buduće povrate/rizike s horizonima i verzijama, bez curenja kroz overlapping target.

**PASS:** testovi availability i embargo zaštite PASS

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-110 — ML baseline classifier/regressor
**Preduvjet:** TAI-109

**Implementacija:** Istreniraj jednostavan logistički/GBM model kao challenger postojećoj transparentnoj strategiji, bez live integracije.

**PASS:** model artifact + reproducibilna evaluacija

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-111 — ML feature pipeline
**Preduvjet:** TAI-110

**Implementacija:** Uvedi train/inference parity, imputaciju, scaling samo na treningu i schema hash.

**PASS:** offline i inference feature matrice identične

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-112 — Hyperparameter experiment tracking
**Preduvjet:** TAI-111

**Implementacija:** Evidentiraj skup parametara, seed, dataset/version, commit SHA i ishode u experiment registryju.

**PASS:** dva pokretanja s istim seedom usporediva

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-113 — Probability calibration
**Preduvjet:** TAI-112

**Implementacija:** Dodaj reliability / calibration analizu ako model emitira vjerojatnosti; zabraniti neinterpretirane confidence brojeve.

**PASS:** reliability report po segmentima

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-114 — Champion-challenger framework
**Preduvjet:** TAI-113

**Implementacija:** Stari model ostaje aktivan dok challenger ne prođe validaciju i kontroliranu promociju; rollback podržan.

**PASS:** promjena modela je auditirana i reverzibilna

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-115 — Model registry artifact integrity
**Preduvjet:** TAI-114

**Implementacija:** Spremi hash modela, data schema, train config, vrijeme treniranja, potpis i dozvoljeni deployment stage.

**PASS:** izmijenjeni artifact se odbija pri učitavanju

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-116 — Drift and data-shift monitor
**Preduvjet:** TAI-115

**Implementacija:** Uvedi upozorenja za promjenu distribucije featurea, performansi i dostupnosti podataka; drift sam po sebi ne pokreće kupnju.

**PASS:** synthetic drift aktivira upozorenje

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-117 — Scheduled retraining sandbox
**Preduvjet:** TAI-116

**Implementacija:** Periodično retreniranje radi u izoliranoj okolini bez trading ključeva, a samo stvara kandidata za evaluaciju.

**PASS:** job ne mijenja aktivni champion bez gate-a

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-118 — Model safety governance
**Preduvjet:** TAI-117

**Implementacija:** Zapiši jasno da generativni AI može objašnjavati ali ne mijenja risk limite niti šalje naloge; testiraj authorization granice.

**PASS:** LLM input ne može promijeniti odobrene limte niti adapter

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

## Faza 08 — Neprekidni real-time paper trading

### TAI-119 — Real-time paper orchestrator
**Preduvjet:** TAI-118

**Implementacija:** Složi market data -> features -> strategy -> risk -> PaperBroker pipeline sa schedulerom, dedupe i observability.

**PASS:** autonomni PAPER test izvršava virtualne naloge

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-120 — Market session controller
**Preduvjet:** TAI-119

**Implementacija:** Dionice mogu stvarati naloge samo u dopuštenim session prozorima; kripto radi 24/7 uz maintenance pauze.

**PASS:** američki i europski praznik blokiraju naloge

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-121 — Paper account daily reset rules
**Preduvjet:** TAI-120

**Implementacija:** Definiraj dnevne granice bez resetiranja cash-a, izračun daily PnL-a i referentne vrijednosti za stop.

**PASS:** prijelaz dana ne resetira portfelj

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-122 — Crash recovery paper worker
**Preduvjet:** TAI-121

**Implementacija:** Nakon restarta posloži pending naloge, lockove i checkpoint bez duplikata, uz primjere crash prije/poslije fill-a.

**PASS:** forced crash replay ne stvara višak pozicija

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-123 — Provider outage contingency
**Preduvjet:** TAI-122

**Implementacija:** Na stale stream ili timeout prijeđi u HALT, odgodi nove signale i pošalji incident s jasnim uvjetima oporavka.

**PASS:** test outage i recovery s manual reset pravilom PASS

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-124 — Paper performance daily snapshot
**Preduvjet:** TAI-123

**Implementacija:** Svaki dan stvaraj snapshot, promjene net worth, open risk, fill rate i warning; bez sakrivanja neuspješnih naloga.

**PASS:** batch report za 7 virtualnih dana PASS

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-125 — Paper journal API
**Preduvjet:** TAI-124

**Implementacija:** Izloži pregled objašnjenja odluka i operativnih incidenata s cursor paginacijom i filterima.

**PASS:** list query i auth testovi PASS

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-126 — 90-day evaluation tracker
**Preduvjet:** TAI-125

**Implementacija:** Dodaj izvještaj o napretku kroz najmanje 90 kalendarskih dana i minimalnom broju odlukâ/različitih režima, bez automatske LIVE promocije.

**PASS:** gate ne prolazi bez trajanja i dokaza

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-127 — Shadow feed comparison
**Preduvjet:** TAI-126

**Implementacija:** Kada su konektori dostupni, prati stvarne brokere read-only i usporedi papirnate fill cijene sa stvarnim quoteovima bez live naloga.

**PASS:** razlike se bilježe, nema place-order poziva

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-128 — Paper soak and chaos tests
**Preduvjet:** TAI-127

**Implementacija:** Višednevna ubrzana simulacija s prekidima feeda, restartovima, rate-limitovima, stale FX i queue timeoutima.

**PASS:** reproducibilan PASS/FAIL evidence bundle

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

## Faza 09 — Android Kotlin / Compose aplikacija

### TAI-129 — Android app scaffold
**Preduvjet:** TAI-128

**Implementacija:** Postavi Compose projekt s Hilt, Retrofit/Ktor client, lifecycle i debug/release konfiguracijama; bez API tajni u APK-u.

**PASS:** gradle test i debug build PASS

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-130 — Navigation i UI design system
**Preduvjet:** TAI-129

**Implementacija:** Kreiraj navigaciju Dashboard, Portfolio, Orders, Decisions, Analytics, Settings; Material3 theme i reusable states.

**PASS:** Compose UI smoke test PASS

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-131 — Login i secure session
**Preduvjet:** TAI-130

**Implementacija:** Izradi login/logout, short-lived token i secure Android keystore storage, error i reauth states.

**PASS:** ne postoji token u plain SharedPreferences

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-132 — Dashboard status i mode
**Preduvjet:** TAI-131

**Implementacija:** Prikaži portfelj, PAPER/SHADOW/LIVE mode, feed/broker health, dnevni PnL i zadnje ažuriranje.

**PASS:** badge mode vezan na API, nikad hardcode

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-133 — Portfolio screen
**Preduvjet:** TAI-132

**Implementacija:** Pozicije, količina, cost basis, real/unrealized PnL, udjeli, cash i period osvježenja.

**PASS:** test praznog i djelomičnog podataka PASS

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-134 — Orders & executions screen
**Preduvjet:** TAI-133

**Implementacija:** Filtrirane liste naloga, stanja PARTIAL/UNKNOWN, fillovi i naknade, s objašnjenjem grešaka.

**PASS:** paging i status filter UI test PASS

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-135 — AI decisions explain screen
**Preduvjet:** TAI-134

**Implementacija:** Prikaži signal, strategy/model version, risk decision i razlog HOLD/REJECT, kao i korištene podatke.

**PASS:** complete decision trace na demo podacima

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-136 — Analytics graphs and metrics
**Preduvjet:** TAI-135

**Implementacija:** Graf vrijednosti, drawdown, PnL, fees i benchmark za odabrani period; indikacija nekompletnih podataka.

**PASS:** sample fixtures i UI screenshot smoke PASS

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-137 — Risk settings read-only first
**Preduvjet:** TAI-136

**Implementacija:** Prikaži aktivnu risk policy i limte, inicijalno read-only, uz objašnjenje planiranog rizika vs garancije.

**PASS:** promjena limita ne postoji prije auth API gate-a

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-138 — Risk settings controlled editing
**Preduvjet:** TAI-137

**Implementacija:** Dodaj owner-authorized promjenu PAPER risk parametara s potvrdom, audit razlogom i server-side validacijom.

**PASS:** nedopušteni limiti vraćaju validation error

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-139 — STOP ALL action
**Preduvjet:** TAI-138

**Implementacija:** Istaknuta STOP akcija s potvrdom, owner auth, prikazom latched statusa i odvojenim postupkom za resume.

**PASS:** backend STOP efekt testiran, ne samo UI

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-140 — Notifications and incidents
**Preduvjet:** TAI-139

**Implementacija:** Prikaži incident inbox i Android push za HALT, outage i dnevne izvještaje, bez osjetljivih podataka u notifikaciji.

**PASS:** instrumentirani handler test PASS

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-141 — Offline-safe UI
**Preduvjet:** TAI-140

**Implementacija:** Cache samo read-only podatke, jasno označi offline/stale stanje, zabrani prikaz fiktivnog live uspjeha.

**PASS:** airplane mode UI nije 'connected'

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-142 — Biometric owner protection
**Preduvjet:** TAI-141

**Implementacija:** Za osjetljive kontrole dodaj biometrics/PIN step-up, uz server-side neovisnu autorizaciju.

**PASS:** samo biometric bypass nije dovoljan za unlock

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-143 — Accessibility & responsive layout
**Preduvjet:** TAI-142

**Implementacija:** Provjeri TalkBack labelove, kontraste, loading/empty/error states i male ekrane.

**PASS:** lint i UI smoke za 2 veličine ekrana PASS

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-144 — Android end-to-end demo
**Preduvjet:** TAI-143

**Implementacija:** Spoji aplikaciju s demo backendom i izradi snimljive smoke scenarije login->dashboard->orders->STOP.

**PASS:** svaki scenarij reproducibilan uz upute

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

## Faza 10 — Brokerski konektori — read-only i paper prvo

### TAI-145 — BrokerAdapter canonical contract
**Preduvjet:** TAI-144

**Implementacija:** Definiraj broker contract get_account, positions, orders, quote, place, cancel, fills, health; jasno razdvoji read-only i trade ovlasti.

**PASS:** contract test radi na MockBroker i PaperBroker

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-146 — Kraken public metadata connector
**Preduvjet:** TAI-145

**Implementacija:** Dohvati Kraken parove, min količine, korak cijene i dozvoljene statusne oznake; pretvori u canonical instrument.

**PASS:** testovi precision i unavailable pair PASS

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-147 — Kraken private read-only client
**Preduvjet:** TAI-146

**Implementacija:** Dodaj HMAC auth i samo read-only balances/orders endpoints s testnim key mockovima; secret masking.

**PASS:** HTTP fixture test, nema withdrawal prava

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-148 — Kraken order adapter dry-run
**Preduvjet:** TAI-147

**Implementacija:** Implementiraj mapiranje canonical naloga u Kraken REST/WebSocket order request, ali poziv ide na mock u svim default okruženjima.

**PASS:** test request payload, precision i forbidden fields

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-149 — Kraken broker error taxonomy
**Preduvjet:** TAI-148

**Implementacija:** Standardiziraj insufficient funds, invalid pair, rate limit, auth expired, unknown submit, rejected i partial fill.

**PASS:** error mapping fixture suite PASS

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-150 — Kraken private order stream parser
**Preduvjet:** TAI-149

**Implementacija:** Obradi order status i fills kroz adapter na mock streamu, s idempotentnim event insertima.

**PASS:** replay duplih događaja bez duplog PnL-a

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-151 — Kraken cancel/reconcile dry-run
**Preduvjet:** TAI-150

**Implementacija:** Implementiraj cancel i status lookup preko mock transporta; timeout => UNKNOWN + read reconciliation.

**PASS:** ne ponavlja create nakon nepoznatog ishoda

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-152 — Kraken API permissions audit
**Preduvjet:** TAI-151

**Implementacija:** Izradi skriptu/proceduru za provjeru potrebnih API ovlasti; zabrani withdrawal/transfer; dokumentiraj IP restriction ako dostupno.

**PASS:** provjera faila ako nepotrebne ovlasti postoje

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-153 — IBKR adapter feasibility note
**Preduvjet:** TAI-152

**Implementacija:** Napravi aktualnu provjeru službene IBKR dokumentacije o TWS/IB Gateway/Web API, autentifikaciji, paper account i market data ograničenjima.

**PASS:** ADR s dokumentiranim manual login i tjednim reauth ograničenjem

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-154 — IBKR session watcher
**Preduvjet:** TAI-153

**Implementacija:** Implementiraj pasivni monitor TWS/IB Gateway statusa, readiness, auth expiry i safe HALT, bez automatiziranog zaobilaženja prijave.

**PASS:** session-expiry mock test blokira nove naloge

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-155 — IBKR market data read-only
**Preduvjet:** TAI-154

**Implementacija:** Dodaj IBKR instrument resolution (conId/contract) i read-only market data adapter u paper/development okruženju.

**PASS:** ticker/contract disambiguation i stale data tests PASS

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-156 — IBKR paper order adapter
**Preduvjet:** TAI-155

**Implementacija:** Implementiraj place/cancel samo za eksplicitno konfigurirani IBKR paper račun; zadani env sve odbija.

**PASS:** IBKR paper fixture / sandbox contract PASS

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-157 — IBKR execution + corporate event parser
**Preduvjet:** TAI-156

**Implementacija:** Mapiraj broker events u canonical fills, statusne promjene i corporate action events s Decimal preciznošću.

**PASS:** duplicate fill i out-of-order event fixtures PASS

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-158 — IBKR reconnect & reconciliation
**Preduvjet:** TAI-157

**Implementacija:** Nakon prekida stanja naloga ne zaključuj po pretpostavci; dohvati orders, fills, positions i cash prije ponovnog dopuštanja.

**PASS:** UNKNOWN order nakon reconnecta razriješen bez dupla

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-159 — Cross-broker contract test suite
**Preduvjet:** TAI-158

**Implementacija:** Pokreni isti skup mock scenarija na PaperBroker, Kraken adapteru i IBKR adapteru; dokumentiraj razlike.

**PASS:** 20+ canonical edge case testova, bez LIVE poziva

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-160 — Broker readiness matrix
**Preduvjet:** TAI-159

**Implementacija:** Evidentiraj razine DATA, READ_ONLY, PAPER, LIVE_LOCKED, LIVE_READY i uvjete svake; objavi u admin API-ju.

**PASS:** slučaj bez MFA/auth ne može biti LIVE_READY

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

## Faza 11 — Sigurnost, nadzor i infrastruktura

### TAI-161 — Secret storage and rotation
**Preduvjet:** TAI-160

**Implementacija:** Implementiraj loader tajni iz okoline/secret storea, nikad u Git-u, mobile APK-u ni logovima; plan rotacije ključeva.

**PASS:** secret scan i masked logging test PASS

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-162 — Environment isolation
**Preduvjet:** TAI-161

**Implementacija:** Razdvoji local, staging PAPER i prod LIVE network, DB, env i ključeve; `LIVE` se ne pokreće s dev postavkama.

**PASS:** integration test odbija cross-env račun

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-163 — Hardened Docker images
**Preduvjet:** TAI-162

**Implementacija:** Non-root runtime, minimalne slike, read-only FS gdje moguće, pin dependencies i resource limits.

**PASS:** container scan / container smoke PASS

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-164 — TLS and network exposure
**Preduvjet:** TAI-163

**Implementacija:** Backend preko HTTPS, ograniči javne portove i pristup brokerskim tajnama; nema izravnog public Redis/Postgres.

**PASS:** infra validation i curl security headers PASS

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-165 — API rate limits and abuse defenses
**Preduvjet:** TAI-164

**Implementacija:** Rate limit login, policy edit, STOP i backend API, CSRF ako se koristi cookie auth; security event log.

**PASS:** burst test demonstrira throttling

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-166 — Observability structured logs
**Preduvjet:** TAI-165

**Implementacija:** JSON logovi s event type, correlation_id, mode, account i redacted fields; log sampling bez gubitka financijskih audita.

**PASS:** test bez API key leakova

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-167 — Prometheus metrics & health
**Preduvjet:** TAI-166

**Implementacija:** Broker/feed age, worker heartbeat, trade rejects, UNKNOWN orders, mismatch count, position exposure, queue depth i DB health.

**PASS:** synthetic metric scrape PASS

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-168 — Alert routing and severity
**Preduvjet:** TAI-167

**Implementacija:** HIGH/Critical incidenti (STOP, unknown order, live disconnect) šalju push/email prema pravilima i dedupe/cooldownu.

**PASS:** mock delivery test bez beskonačnog spam-a

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-169 — Backups and restore drill
**Preduvjet:** TAI-168

**Implementacija:** Postgres backup, enkripcija, retention i restore na novu bazu; document RPO/RTO ciljeve.

**PASS:** stvarni restore test i hash važnih tablica PASS

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-170 — Disaster recovery runbook
**Preduvjet:** TAI-169

**Implementacija:** Postupci server down, DB corruption, compromised key, broker unreachable i stale quotes, s fail-closed fazama.

**PASS:** tabletop scenarij pokriva 5 incidenta

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-171 — Secure audit export
**Preduvjet:** TAI-170

**Implementacija:** Izvoz evidencije naloga, fillova, policy promjena i modela za owner; potpis/sha256 i bez tajni.

**PASS:** svaka export serija ima checksum

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-172 — Tax/accounting export Croatia
**Preduvjet:** TAI-171

**Implementacija:** CSV/JSON izvoz za nabave, otuđenja, naknade, EUR/FX tečajeve i vremenske oznake, uz napomenu da to nije porezni obračun.

**PASS:** trade FIFO/specific cost evidence transparentno i testirano

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-173 — Data retention and cleanup
**Preduvjet:** TAI-172

**Implementacija:** Politika čuvanja market data, PII, audit i logova; oprezno purge samo nefinancijskih tmp podataka.

**PASS:** dry-run purge ne dira ledger/audit

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-174 — CI security and dependencies
**Preduvjet:** TAI-173

**Implementacija:** SAST/secret/dependency scanning, SBOM i provjera licence; fix kritičnih ranjivosti prije releasea.

**PASS:** pregledan security report bez kritičnih nalaza

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-175 — Server PAPER deployment
**Preduvjet:** TAI-174

**Implementacija:** Compose/staging deploy na odvojen Linux server s health/rollback i isključivo PAPER konfiguracijom.

**PASS:** postdeploy smoke + vraćanje prethodne verzije PASS

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-176 — Operational runbook and release tag
**Preduvjet:** TAI-175

**Implementacija:** Runbook za update, rollback, manual unlock, STOP, alarm test, maintenance prozor i changelog release tag.

**PASS:** nova osoba može reproducirati release iz dokumenta

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

## Faza 12 — Gateovi, ograničeni LIVE pilot i produkcijska autonomija

### TAI-177 — 90-day PAPER gate evidence
**Preduvjet:** TAI-176

**Implementacija:** Sastavi automatizirani evidence bundle: povijest 90+ dana, tržišni režimi, backtest, forward PnL, troškovi, risk incidents i tehničke greške.

**PASS:** gate report može rezultirati PASS ili FAIL bez manualnog uljepšavanja

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-178 — Broker/legal readiness checklist
**Preduvjet:** TAI-177

**Implementacija:** Prije LIVE provjeri ovlasti računa, dostupnost tržišta, brokerske uvjete, licencu kripto pružatelja prema ESMA/HANFA registru te hrvatsko porezno evidentiranje.

**PASS:** dokumentirana provjera s datumom i izvorima

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-179 — LIVE deployment immutable gate
**Preduvjet:** TAI-178

**Implementacija:** Izradi odvojeno LIVE okruženje s trgovinskim ovlastima po principu deny by default; backend mora provjeriti deploy mode, account mode i auth proof.

**PASS:** test konfiguracije s jednim nedostajućim uvjetom odbija place

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-180 — Explicit owner unlock workflow
**Preduvjet:** TAI-179

**Implementacija:** Implementiraj svjesnu aktivaciju LIVE uz reauth + MFA + potvrdu iznosa + vremensko ograničenje + audit; nakon aktivacije strategije mogu raditi bez potvrde svakog naloga.

**PASS:** istekao unlock ili STOP odmah blokira nove naloge

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-181 — Pilot capital containment
**Preduvjet:** TAI-180

**Implementacija:** Dodaj dnevni hard notional cap i odvojeni pilot account/strategy whitelist, nezavisno od standardne policy konfiguracije.

**PASS:** testovi ne dopuštaju izlaz iz pilot limita

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-182 — LIVE observation read-only
**Preduvjet:** TAI-181

**Implementacija:** Najprije poveži stvarni broker read-only, uskladi balances, quotes i session status s našom bazom bez slanja naloga.

**PASS:** audit potvrđuje nula stvarnih order API poziva

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-183 — LIVE order preview only
**Preduvjet:** TAI-182

**Implementacija:** Za brokerske naloge napravi simulaciju payload-a, planirane provizije i očekivanog slippagea bez slanja; owner vidi razloge odbijanja.

**PASS:** dry-run proof ne doseže private trade endpoint

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-184 — Kraken spot micro-pilot
**Preduvjet:** TAI-183

**Implementacija:** Tek nakon korisnikove izričite dozvole i prethodnih PASS gateova omogući jedan ograničeni stvarni spot nalog uz minimalni iznos, risk approval i evidentirano izvršenje.

**PASS:** confirmed fill + broker/local reconciliation + STOP test; inače FAIL

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-185 — IBKR paper-to-live controlled handoff
**Preduvjet:** TAI-184

**Implementacija:** Nakon paper dokaza i korisnikove autorizacije izvedi najmanji dopušteni dionički nalog samo preko LIVE konfiguracije s provjerom sesije i provizije.

**PASS:** confirmed fill, no duplicate i reconciled account

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-186 — Live partial/timeout incident rehearsal
**Preduvjet:** TAI-185

**Implementacija:** U kontroliranim uvjetima testiraj partial fills, cancel rejected i unknown submit te prekide veze; bez pretpostavljene likvidacije pozicija.

**PASS:** dokazano no-resubmit ponašanje i incident evidencija

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-187 — Formal LIVE pilot review
**Preduvjet:** TAI-186

**Implementacija:** Izvještaj nakon ograničenog pilota: stvarni fill vs model, fees, drawdown, incidenti, matching kvaliteta i odluka nastaviti/zaustaviti.

**PASS:** odluka temeljem dokumentiranih kriterija, bez automatskog povećanja kapitala

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-188 — Controlled autonomous release
**Preduvjet:** TAI-187

**Implementacija:** Uključivanje autonomnih naloga tek nakon posebne potvrde ownera, dokumentiranih limita, revokacije, rollbacka i tjednog nadzora.

**PASS:** end-to-end rehearsal STOP/restore + live gate proof PASS

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.

### TAI-189 — Ongoing model and risk monitoring
**Preduvjet:** TAI-188

**Implementacija:** Definiraj dnevne i tjedne provjere drifta, prinos/rizik, broker reconciliations i automatski rollback strategije na prethodni sigurni champion ili HALT.

**PASS:** false-positive/false-negative incident testovi PASS

**Uputa:** Primijeni globalna Cursor pravila; testovi i final report obvezni.
