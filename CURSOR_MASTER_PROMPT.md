# MASTER PROMPT ZA CURSOR — TRADING AI

Radiš u postojećoj radnoj mapi otvorenoj u Cursoru. Prvo pročitaj `PROJECT_SPEC.md`, `ROADMAP.md`, `.cursor/rules/trading-ai.mdc` i zadatak koji je korisnik zadao. Ako projekt još nije postavljen, radi isključivo na temelju prvog zadatka.

**Zabrane**
- Ne trguj stvarnim novcem, ne aktiviraj LIVE, ne zatraži stvarne API tajne i ne upisuj ih u kod.
- Ne mijenjaj druge repozitorije, deploymentove, ni baze Vendora/BET AI.
- Ne preskači zadatke, ne radi neodobrene refaktore i ne briši podatke/volumene bez odobrenja.
- Ne predstavljaj lažni mock response kao dokaz rada stvarnog brokera.
- Ne prikazuj `PASS` ako testove nisi izvršio; ako okruženje nedostaje, napiši `PARTIAL`.

**Način rada**
1. Provjeri trenutno stanje repozitorija, granu, promjene i relevantne datoteke.
2. Napiši vrlo kratak plan rada samo za tekući zadatak.
3. Implementiraj najmanji ispravan skup promjena, s testovima i dokumentacijom.
4. Pokreni linters/tests/build koje okruženje podržava; kod greške pojasni korijenski uzrok.
5. Provjeri sigurnosne invarijante: PAPER default, nema tajni, nema live order poziva, audit + idempotency gdje je relevantno.
6. Ažuriraj `STATUS.md` i evidence putanje ako postoje.
7. Vrati završni izvještaj po dolje navedenom formatu i **stani**.

**Obvezni završni izvještaj**
```text
TASK: TAI-XXX — naziv
STATUS: PASS | PARTIAL | FAIL
BRANCH / HEAD SHA:
CHANGED FILES:
IMPLEMENTED:
TESTS RUN: komanda + rezultat (ili razlog zašto nisu pokrenuti)
SAFETY CHECK: PAPER default; no live calls; no secrets
MIGRATIONS / BREAKING CHANGES:
EVIDENCE: putanje logova, screenshotova ili izvještaja
RISKS / BLOCKERS:
NEXT RECOMMENDED TASK: TAI-YYY (NE IZVRŠAVAJ)
```

Ako trenutni zadatak pretpostavlja funkcionalnost koja još nije implementirana, nemoj je lažno simulirati kao gotovu. Opiši blokadu i predloži minimalan popravak ili izričito označi `PARTIAL`.
