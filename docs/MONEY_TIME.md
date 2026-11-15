# Novac, valute, FX i vrijeme

Normativna politika TAI-006. Izvor: [specifikacija](../PROJECT_SPEC.md).

## Preciznost i serijalizacija

Iznosi, količine, cijene, naknade i tečajevi koriste Python Decimal konstruiran iz
stringa, nikad iz float. API ih šalje i prima kao decimalne stringove s točkom,
bez separatora tisućica. Odbiti NaN, Infinity, binarne float inpute, negativnu
qty/cijenu te out-of-range precision umjesto tihog rezanja. Ledger knjiženje može
biti signed; strana BUY/SELL nije kodirana negativnom order qty.

Radni Decimal context ima najmanje 38 značajnih znamenki; DB cilj NUMERIC(38,18),
s provjerom 20 integer i 18 fractional znamenki prije upisa. Instrument s većim
zahtjevom odbiti do eksplicitne migracije. Rounding se ne događa na svakom koraku:
sačuvati original i točan izračun, kvantizirati samo na imenovanim granicama.

| Granica | Pravilo | Primjer (sintetički) |
| --- | --- | --- |
| EUR/USD prikaz | 2 decimale, ROUND_HALF_EVEN; ledger čuva veću preciznost | EUR 12.345 -> 12.34; USD 12.355 -> 12.36 |
| Order qty | Mora biti točan višekratnik lot step iz metapodataka; ne zaokruživati prešutno | BTC 0.00012345 uz step 0.00000001 prolazi; 0.000123451 odbija se |
| Limit price | Mora odgovarati tick size; nema tihog mijenjanja intent hasha | EUR 100.005 uz tick 0.01 odbiti |
| Planirana qty | Konzervativno floor na step, zatim ponoviti min notional i risk provjeru | 50 EUR / 30000 EUR/BTC = 0.00166666 BTC na step 1e-8 |
| Fee rezervacija | Ceiling na fee quantum pružatelja da rezervacija ne bude manja | Fee iz brokera ostaje izvor istine |
| Ledger | Debiti i krediti identični unutar valute; bez epsilon tolerancije | Nesklad 0.00000001 BTC je nesklad |

Qty/price primjeri nisu tvrdnja o aktualnim pravilima burze.
Službena osnova: [Python Decimal](https://docs.python.org/3/library/decimal.html).

## EUR i FX

EUR je izvještajna valuta; USD i BTC subledger ostaju u vlastitoj valuti. FX event
nosi source, base, quote, rate, effective_at, received_at, usable_at i snapshot ID.
Za stop/risk valuaciju koristiti svjež tržišni tečaj i konzervativnu stranu spreada;
nedostajući ili stale tečaj blokira novu izloženost, ne vraća 1 ili 0.

Za dnevni informativni izvještaj predviđen je
[ECB referentni tečaj](https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html).
Objavljuje se radnim danima, informativan je i nije izvršivi transaction rate.
Bez tvrdnje o poreznoj dostatnosti. Stvarna FX konverzija ima brokerski fill i fee.

Sintetički primjer: ako 1 EUR = 1.10 USD, onda 110 USD / 1.10 = 100 EUR. Obrnuti
rate ne množiti pogrešno. BTC/EUR 50000 uz 0.001 BTC daje 50 EUR prije troškova.
Na vikend zadnji poznati ECB rate smije služiti samo označenom izvještaju, uz
as_of i stale flag; nikad uz usable_at iz budućnosti. Ne objavljivati kompletan
EUR NAV ako nedostaje jedna materijalna FX stopa: status incomplete i izvorni iznosi.

Početna PAPER pretpostavka: quote/FX za novi order najviše 60 s star,
konfigurabilno i verzionirano po feedu. Budući datum > 1 s tolerancije sata znači
quality incident. ECB reporting snapshot najviše 5 kalendarskih dana star uz
jasan stale flag; stariji znači incomplete. To su razvojne odluke za testiranje,
ne tržišni standard. Broker reconciliation tolerira samo dokumentirani rounding
quantum po assetu; ledger nikada ne tolerira neuravnoteženost.

## Vrijeme, UTC i DST

DB timestampi su timezone-aware UTC (PostgreSQL TIMESTAMPTZ), API RFC3339 s `Z` ili
eksplicitnim offsetom; naive datetime odbiti. Čuvati event, receive i usable vrijeme
odvojeno. Za elapsed timeout koristiti monotonic clock; wall clock za audit.

Raspored burze koristi IANA timezone vezan uz venue i stvarni exchange calendar,
uključujući blagdane i early close. Europe/Zagreb služi vlasnikovom prikazu;
America/New_York primjer je američke venue zone, UTC za 24/7 crypto. Ne dodavati
fiksni offset ni pretpostaviti da Europa i SAD mijenjaju sat istoga dana.

Primjeri Europe/Zagreb za test: 2026-03-29T00:30Z -> 01:30+01:00;
2026-03-29T01:30Z -> 03:30+02:00 (02:30 lokalno ne postoji).
2026-10-25T00:30Z i 01:30Z oba imaju lokalno 02:30, ali različite offsete.
Neodređen lokalni input bez offseta/folda odbiti; nepostojeći input odbiti.
Izvor: [zoneinfo i fold](https://docs.python.org/3/library/zoneinfo.html).
Pin tzdata u reproducibilnom backtest okruženju, posebno na Windowsu.

Risk dan i tjedan: početni PAPER account timezone Europe/Zagreb; dan od lokalne
ponoći, tjedan od ponedjeljka 00:00. Spremiti UTC granice perioda, nikada računati
dan kao uvijek 24 sata. Ne resetirati HALT automatski pri dnevnom resetu casha.
