# Model prijetnji i ovlasti

TAI-007, razvojni dizajn. Izvori: [charter](PROJECT_CHARTER.md),
[režimi](MODES.md), [događaji](TRADING_EVENTS.md).

## Imovina i granice povjerenja

Štitimo brokerske API tajne, autentikacijske tokene/MFA, identitet računa, financijski
ledger/audit, privatne pozicije, risk politike, market-data provenance i model artefakte.
Granice su Android -> API -> DB/queue/worker -> broker/feed te CI -> artefakti -> server.
Feed, model, mobilni uređaj i queue poruke nisu autoritet za odobravanje naloga.

Napadači: vanjski mrežni korisnik, kradljivac telefona/tokena, kompromitirani dependency
ili CI, zlonamjerni feed/model input, lokalni malware i operator s preširokim pravima.
Nenamjerne pogreške operatora i brokerski outage također su relevantni rizici.

## Konkretne prijetnje i mjere

| ID | Napad / kvar | Mjera i dokaz buduće provedbe | Preostali rizik |
| --- | --- | --- | --- |
| T01 | API key u Git-u ili logu | Ignore, secret scan, redaction i rotacija; test s canary tajnom | Već objavljena tajna traži revokaciju, brisanje loga nije dovoljno |
| T02 | Ukraden Android uređaj | Kratka sesija, secure storage, reauth/MFA za osjetljivo; server scope test | Rootani uređaj se ne smatra pouzdanim |
| T03 | Replay intent/API zahtjeva | Unique idempotency key po account/mode i payload hash; concurrency test | DoS ne nestaje dedupeom |
| T04 | Model zaobilazi risk | Model nema trade credential ni submit scope; obvezan risk approval hash | Pogrešan model može slati mnogo odbijenih intentova |
| T05 | PAPER/LIVE zamjena računa | Odvojeni deployment/tajne/DB, mode AND checks; mismatch test | Operator treba provjeriti pravi account identitet |
| T06 | Credential s withdrawal/transfer | Zabraniti te ovlasti; permissions audit fail-closed prije readiness | Broker audit dostupnost ograničava readiness |
| T07 | Zastarjeli/manipulirani quote | Provenance, usable_at, max age i deviation guard; stale/future tests | Valjan ali loš tržišni podatak traži dodatnu usporedbu |
| T08 | Submit timeout dovodi do duple kupnje | UNKNOWN quarantine, read reconcile, nikad blind create retry | Broker može kasniti s dokazima; account ostaje halted |
| T09 | Dupli/out-of-order fill | Execution uniqueness, atomic ledger marker; replay/race test | Inconsistent broker evidence ide u incident |
| T10 | DB korisnik briše audit | Append-only privilegije, odvojeni migrator, checksum export i backup restore | DB superuser može mijenjati lokalne zapise; off-host dokaz potreban |
| T11 | Supply-chain/CI krađa tajni | Pin/hash dependencies, minimalan CI token, bez prod tajni u PR buildovima | Potpisani upstream nije dokaz bezgrešnosti |
| T12 | Public Redis/Postgres | Privatna mreža, localhost dev portovi, auth, least privilege; infra config test | Host compromise ostaje granica |
| T13 | Krađa admin sesije mijenja risk | Owner-only scope, step-up, audit razlog i server-side hard cap | Aktivni kompromitirani owner treba revokaciju |
| T14 | STOP se izgubi restartom | Durable latch i odvojen resume; restart/fault test | Nedostupna DB znači odbijanje novih naloga |
| T15 | Nedostupna queue / dva workera | Durable jobs, lease/fencing, idempotent DB write; kill-worker test | Redis lock sam nije dokaz exactly-once |
| T16 | Prompt injection u dokumentu/feedu | Input je podatak; ne dobiva alate/ovlasti ni mijenja safety policy | Čovjek i dalje pregledava promjene pravila |
| T17 | Clock drift/lookahead | UTC, usable_at, monotonic timeout, clock health; future-data test | Izvorni timestamp mora imati lineage |
| T18 | Disk pun / audit write fails | Atomarna transakcija, readiness false, HALT; failure injection | Nastali broker ishod treba read reconciliation |

## Least-privilege matrica

`Da` vrijedi samo za navedeni scope i mode; sve ostalo deny. Nema zajedničke
admin credential za aplikaciju i migracije.

| Identitet | Market read | Privatni read | Intent | Risk/policy | Place/cancel | Ledger/audit | Unlock/resume |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Android viewer | API read | Vlastiti API read | Ne | Read | Ne | Read redacted | Ne |
| Owner | API read | Vlastiti API read | PAPER zahtjev | Kontrolirani edit uz reauth | Samo kroz server gate | Read/export | Poseban step-up + MFA |
| Strategy/model worker | Odobren dataset | Minimalni portfolio snapshot | Da | Read policy | Ne | Event append kroz service | Ne |
| Risk service | Quote + exposure | Snapshot | Read | Evaluate, ne samostalni edit | Ne | Decision append | Ne |
| Execution worker | Nužni quote | Orders/fills za svoj account | Read approved | Provjera approvala | PAPER; budući LIVE samo gated adapter | Financial service transakcija | Ne |
| Feed worker | Public/feed entitlement | Ne | Ne | Ne | Ne | Data lineage append | Ne |
| API runtime DB role | Scoped queries | Scoped queries | Service write | Autorizirano | Ne izravno brokeru | INSERT audit; nema UPDATE/DELETE | Provjera dokaza |
| Migrator/operator | Maintenance | Ne brokerske tajne | Ne | Ne runtime | Ne | DDL samo kontrolirano | Ne |
| CI | Fixture read | Ne | Ne | Ne | Ne | Test DB samo | Ne |

Broker ključevi su odvojeni po ulozi i računu: read-only bez trade ovlasti za
SHADOW; budući execution samo nužne trade/read ovlasti. Withdrawal i transfer
zabranjeni su svima, uključujući owner credential kojim upravlja aplikacija.

## Incident postupak

Sumnja na kompromitaciju -> STOP/HALT, revoke sesije/ključeva izvan aplikacije,
sačuvati redacted dokaze, read reconciliation, rotacija i zasebno odobren resume.
Ne zapisivati ključeve u incident. Ne tvrditi da je position zatvoren bez fill dokaza.
Mjere iz tablice su plan provjera; ova dokumentacija ne potvrđuje njihovu provedbu.
