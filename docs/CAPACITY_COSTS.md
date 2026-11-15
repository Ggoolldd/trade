# Kapacitet, troškovi i granice prvog releasea

TAI-010; stanje 2026-11-15. Plan bez kupnje servisa ili aktivacije pretplate.
Izvori: [specifikacija](../PROJECT_SPEC.md), [ADR](adr/0001-stack.md).

## Razvojni profili

| Profil | Planirani minimum (procjena, nije benchmark) | Granice |
| --- | --- | --- |
| Lokalni backend | 2 CPU, 4 GB raspoloživog RAM-a, 20 GB slobodnog SSD-a | API, PostgreSQL, Redis, jedan worker; bez velikog ML-a |
| Lokalni Android + backend | 4 CPU, 16 GB ukupnog RAM-a, 50 GB slobodnog SSD-a | Emulator može zahtijevati više; fizički uređaj alternativa |
| Budući PAPER VPS | 2 vCPU, 4 GB RAM, 40 GB SSD, Linux | Samo PAPER; jedan ingest/worker; izmjeriti peak prije povećanja univerzuma |

Nisu izmjerene performanse projekta. Početni kapacitet mjeriti u TAI-013 i kasnije
load testom: resident RAM, CPU, write latency, queue lag, DB/WAL rast. Alarm na
70% diska, stop ingest/backfill na 85% uz očuvan audit. Nema automatskog brisanja ledgera.

## OHLCV račun

Pretpostavke: 2 crypto instrumenta 24/7, interval 1 min, 365 dana.
Redova = 2 * 365 * 24 * 60 = 1.051.200. Uz pretpostavljenih 200 B po canonical
retku to je 210.240.000 B (~200.5 MiB); s indeksima/bloat faktorom 3 planirati
~601.5 MiB. To nisu izmjerene PostgreSQL veličine. Raw payload, lineage, WAL i
backup nisu uključeni u faktor i trebaju zasebnu rezervu.

Za dodatnih 20 dionica/ETF-ova, pretpostavka 252 sesije * 390 min daje 1.965.600
redova/god (~1.10 GiB uz isti faktor). Ovo je samo račun kapaciteta; europske
sesije imaju drugačije trajanje i račun se ponavlja prema stvarnom kalendaru.
Crypto+dionice daju ~1.69 GiB/god canonical+indeksi. Za raw i backup početno
rezervirati dodatnih 5 GiB/god i izmjeriti; tick/order-book arhiva nije u opsegu.

## Feedovi i rate limitovi

[Kraken OHLC](https://docs.kraken.com/api-reference/market-data/get-ohlc-data)
vraća najviše 720 zadnjih zapisa; zadnji je nedovršen. Nije izvor neograničenog
historijskog backfilla. Backfill source i pravo uporabe zasebna su odluka.
Za dva para polling jednom po minuti znači 2 zahtjeva/min, 2.880/dan, prije retryja.
To je naš plan opterećenja, ne jamstvo dozvoljenog public API throughputa.

[Kraken REST limits](https://docs.kraken.com/exchange/guides/rest/ratelimits)
razlikuje tier counter i zaseban trading limiter. Private counter nije opća
public quota. Adapteri moraju imati timeout, bounded backoff+jitter, rate-limit
odgovor i monitoring; za create se ne radi blind retry nakon timeouta.
Za public feed prvo konzervativno ograničiti concurrency na 1 i nadzirati greške.
TAI-030/031 ponovno provjeravaju endpoint dokumentaciju prije implementacije.

[IBKR market data](https://www.interactivebrokers.com/docs/general/market-data-subscriptions/introduction)
za većinu securities traži odgovarajuću Level 1 pretplatu za API. Cijena ovisi o
burzi, statusu korisnika i paketu; delayed feed nije real-time dokaz. Entitlement,
pacing i dostupnost paper accounta provjeravaju se kasnije za konkretan račun.

## Troškovna tablica

| Stavka | Status | Iznos / mjesečno | Što još treba provjeriti |
| --- | --- | --- | --- |
| Dodatne kupnje u ovom zadatku | Poznato | 0 EUR | Ništa kupljeno ni pretplaćeno |
| Postojeće lokalno računalo | Nepoznato | Nije pripisan novi trošak | Struja, disk i postojeće licence nisu besplatni po pretpostavci |
| PAPER VPS | Procjena planiranja | 10–25 EUR | Nije ponuda; provider, PDV, promet i backup prije odluke |
| Off-host backup | Procjena planiranja | 2–10 EUR | Veličina, retention, encryption i restore; bez aktivacije |
| Public crypto feed | Poznato samo za scope | Nije kupljen plaćeni feed | API pristup nije ugovoreni SLA niti potvrda redistribucijskih prava |
| Stocks/UCITS historija i real-time | Nepoznato | TBD | Instrumenti, API prava, professional status i feed paket |
| Android alati | Plan | Bez dodatne kupnje u ovom zadatku | SDK licence i alatni uvjeti pri scaffoldingu |

VPS+backup planning envelope je 12–35 EUR/mj prije feedova, poreza i prometa.
Ovo su proračunske procjene, ne aktualne cjenovne preporuke ni odobren budžet.

## Prvi release i operativne blokade

Prvi release: jedan privatni owner, mali konfigurirani universe, PAPER, minute/daily
OHLCV, bez tick/HFT, leverage, short, paid feed kupnje ili LIVE naloga. ML tek
nakon baseline/backtest gatea. Opseg raste tek nakon mjerenja kvalitete i troškova.

U ovom okruženju Node i Docker CLI postoje; Python alias nije upotrebljiv, a Docker
daemon pipe nije dostupan. Izolirani Python runtime pokušava se pripremiti lokalno.
TAI-011 mora imati stvarni pytest/API smoke, TAI-013 stvarne healthy servise; ako to
nije moguće, ostaju PARTIAL bez izmišljanja rezultata.
