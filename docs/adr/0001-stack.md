# ADR 0001: razvojni stack

Datum: 2026-11-15. Status: prihvaćeno za PAPER razvoj.
Kontekst: [specifikacija](../../PROJECT_SPEC.md) i [charter](../PROJECT_CHARTER.md).

## Odluka i alternative

| Sloj | Odabir i razlog | Razmotrena alternativa | Posljedice |
| --- | --- | --- | --- |
| Android | Kotlin, Jetpack Compose, Hilt: nativni UI, tipovi, lifecycle i dependency injection | Flutter: dodatni runtime i jezik; web: slabija integracija uređaja | Kotlin/Gradle/AGP/Hilt kompatibilnost mora se testirati zajedno; Android nije engine |
| Backend | Python + FastAPI: tipizirani API, OpenAPI, zajednički jezik s istraživanjem | Django: više gotovih modula, ali širi framework; Node: dva jezika za ML i server | CPU-heavy posao ide workeru; async endpoint ne smije blokirati event loop |
| Baza | PostgreSQL + SQLAlchemy/Alembic: transakcije, NUMERIC, constraints i pregledne migracije | SQLite: lokalno praktičan, ali nije dokaz PostgreSQL locking ponašanja; dokumentna baza: slabiji fit za ledger | Migracije pregledati i testirati na stvarnom PostgreSQL-u; ledger ostaje izvor istine |
| Queue | Redis za red poslova i kratkotrajne lockove | RabbitMQ: dodatna administracija; samo DB queue: manje infrastrukture, drugačiji operativni model | Delivery može biti višestruk; idempotency mora biti u domeni/bazi; Redis nije ledger |
| Pakiranje | Docker Engine + Compose za razvoj i kasniji izolirani PAPER server | Ručna instalacija: drift; Kubernetes: prevelik početni operativni teret | Health checks, odvojeni volumeni i mreže; bez public DB/Redis portova u server deploymentu |

## Verzioniranje i održavanje

Početna ciljna Python linija je 3.12, projektna odluka radi zrele podrške paketa,
ne tvrdnja da je najnovija. Stvarno odabrani patch i kompatibilnost zabilježiti pri
TAI-011. FastAPI/Pydantic i testni alati dobivaju točne reproducibilne verzije;
upgrade ide zasebnim diffom uz API i negativne testove. Ne pinati Starlette mimo
FastAPI kompatibilnosti bez razloga. Izvor: [FastAPI versions](https://fastapi.tiangolo.com/deployment/versions/).

Android pri TAI-129 koristi version catalog, Gradle wrapper i stabilan
[Compose BOM](https://developer.android.com/develop/ui/compose/bom). Kotlin,
Compose compiler, AGP i JDK moraju imati provjerenu kompatibilnost prije pina.
Ne izmišljamo sada neprovjereni skup Android verzija.

PostgreSQL major, Redis izdanje i container tag/digest biraju se pri TAI-013/014;
bez `latest` u reproducibilnom deploymentu. Mjesečno pregledati zakrpe i ranjivosti;
kritične sigurnosne zakrpe imaju prednost. Major DB upgrade zahtijeva restore i
rollback plan, ne automatski bump. API ima /api/v1 namespace i verzionirane ugovore.

## Licence

| Komponenta | Licencna odluka / provjera |
| --- | --- |
| Kotlin, AndroidX Compose, Hilt | Apache-2.0 za navedene projekte; provjeriti NOTICE i tranzitivne dependency licence pri pinu |
| Python | PSF licenca; zadržati obavijesti pri redistribuciji |
| FastAPI | MIT; [upstream LICENSE](https://github.com/fastapi/fastapi/blob/master/LICENSE) |
| SQLAlchemy / Alembic | MIT; inventar stvarno instaliranih verzija prije releasea |
| PostgreSQL | [PostgreSQL License](https://www.postgresql.org/about/licence/) |
| Redis | Licenca ovisi o izdanju i distribuciji; prije odabira pregledati točan artefakt i [upstream licence](https://redis.io/legal/licenses/); ne pretpostavljati BSD za sva izdanja |
| Docker | Engine/Compose i Desktop imaju različite uvjete; [Desktop terms](https://docs.docker.com/subscription-billing/desktop-license/) dopuštaju personal use, druge namjene ponovno provjeriti |

Gornje licence ne biraju licencu ovog projekta, koja ostaje
[odgođena odluka](../LICENSE_DECISION.md). Prije distribucije popisati dependency
licence i market-data prava; pretplata na feed nije dozvola redistribucije.

## Provjera i granice

TAI-011 dokazuje backend smoke; TAI-013 Compose; TAI-014 stvarnu migraciju;
TAI-024 CI; TAI-129 Android build. Ovaj ADR ne tvrdi da su te provjere obavljene.
Nema brokerskog API odabira ili aktivacije LIVE u ovoj odluci.
