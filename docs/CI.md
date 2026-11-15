# CI quality gate

TAI-024 status: PASS. Verification: all five GitHub jobs PASS on
[run 43751964422](https://github.com/Ggoolldd/trade/actions/runs/43751964422),
commit e27da4a. Android test (debug/release), lint and debug APK build executed.
Local clean test/lint/assembleDebug also passed (75 tasks; no lint errors).
Final report/status publication goes through the same protected PR checks.

## Checks

[quality.yml](../.github/workflows/quality.yml) runs on main push, pull requests and
manual dispatch. The token has contents:read and no persisted checkout credential.
It executes locked Python 3.12/uv, pytest, strict mypy, Ruff, OpenAPI snapshot,
docs, real PostgreSQL/Redis and migration roundtrip, Gitleaks full-history scan,
actionlint and Android Gradle test/lint/assembleDebug.

Every critical job feeds the always-run required-quality aggregate. A failed,
cancelled or skipped critical job fails it. No continue-on-error or placeholder
Android success is used. Backend and Android reports are retained as Actions
artifacts for 14 days; credentials and expanded Compose env are never uploaded.

The owner requested resolving TAI-024 and authorized the minimal real Android CI
prerequisite ahead of TAI-129. See [Android README](../android/README.md).
Full Hilt/client/lifecycle integration remains TAI-129 work. No trading UI, API
credentials, network permissions or live orders are introduced by this scaffold.

Actions use immutable verified SHAs. CLI releases have official SHA256 pins in
[ci-tools.json](../infrastructure/ci-tools.json). The installer checks archive hashes
and extracts only the named executable. Gradle distribution and wrapper JAR
checksums were checked against Gradle's official published values.

## Real GitHub enforcement

The owner selected Ggoolldd/trade, explicitly approved project/history upload and
subsequently approved making it public after the private-plan rulesets API
returned 403. Visibility was changed and read back as public. No purchase occurred.

Active repository ruleset 27327041 applies to main: strict/up-to-date
required-quality status, no bypass actors, enforced on branch creation.
GitHub readback confirms it. A real empty-commit push without the status was rejected
with GH013/required-quality expected; main contents were unchanged. Evidence:
[enforcement log](reports/TAI-024-enforcement.txt). This is an executed rejection,
not an inference from a local JSON configuration.

Changes now go through a branch/PR and green checks. Do not bypass the ruleset.
[infrastructure policy](../infrastructure/github-ruleset.json) matches the live rule.

## Local checks

```text
backend/.venv/Scripts/python.exe scripts/run-backend-checks.py TAI-024
backend/.venv/Scripts/python.exe scripts/run-postgres-checks.py TAI-024
backend/.venv/Scripts/python.exe scripts/check-android.py
```

Use the project's generated ignored local Compose env for PostgreSQL/Redis.
Integration checks create/remove only a new test database and test-owned streams.
On Windows the Python path differs from Linux. See Android README for JDK/SDK.
Both test runners create their scratch parent on clean checkouts.

Initial remote run 43749739846 exposed a missing scratch parent and the absent
Android scaffold. Run 43749890200 on 70fa69c proved backend (100 tests), workflow
lint and secret checks; Android correctly failed before this real scaffold.
Those historical failures remain visible; no previous result is relabeled PASS.

Official references:
[GitHub rulesets REST](https://docs.github.com/en/rest/repos/rules#create-a-repository-ruleset),
[protected branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches),
[Gradle wrapper](https://docs.gradle.org/8.13/userguide/gradle_wrapper.html).
