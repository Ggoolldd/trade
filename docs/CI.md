# CI quality gate and remaining setup

TAI-024 status: PARTIAL, 2026-11-15. Local backend/contract/DB/Redis checks and
workflow/secret validation pass. Remote GitHub enforcement and real Gradle results
are not claimed.

## Prepared workflow

[quality.yml](../.github/workflows/quality.yml) runs on main pushes, pull requests
and manual dispatch with contents:read only and no persisted checkout credential.
Jobs cover locked Python 3.12/uv environment, pytest, strict mypy, Ruff, OpenAPI
snapshot, docs, real PostgreSQL/Redis migration roundtrip, Gitleaks Git-history scan,
actionlint workflow validation and actual Android Gradle test/lint.

All critical jobs feed the always-run `required-quality` aggregate. Any failed,
cancelled or skipped required job fails the aggregate. No continue-on-error or
placeholder Android success is used. The Android job currently fails explicitly
because android contains only .gitkeep; TAI-129 has not supplied a real wrapper,
settings or app. This is a backlog ordering conflict to resolve before TAI-024 can
be certified PASS. Creating a dummy Gradle task would not resolve it.

Action references are immutable commit SHAs verified against official release tags;
CLI binaries have verified official SHA256 checksums for Linux/Windows x86_64 in
[ci-tools.json](../infrastructure/ci-tools.json). Tool installers extract only the
named binary, never arbitrary archive paths. Versions are reviewed updates, not
automatic latest downloads. Local tool binaries/cache stay in ignored tmp.

## Local equivalents

```powershell
backend/.venv/Scripts/python.exe scripts/run-backend-checks.py TAI-024
backend/.venv/Scripts/python.exe scripts/run-postgres-checks.py TAI-024
backend/.venv/Scripts/python.exe scripts/install-ci-tool.py actionlint --bin-dir tmp/ci-bin
backend/.venv/Scripts/python.exe scripts/install-ci-tool.py gitleaks --bin-dir tmp/ci-bin
tmp/ci-bin/actionlint.exe -shellcheck= -pyflakes= .github/workflows/quality.yml
tmp/ci-bin/gitleaks.exe git --redact --no-banner --log-opts=--all .
tmp/ci-bin/gitleaks.exe git --pre-commit --staged --redact --no-banner .
backend/.venv/Scripts/python.exe scripts/check-android.py
```

Use GIT_CONFIG_COUNT/KEY_0/VALUE_0 with process-local safe.directory=D:/TRADING on
this filesystem as recorded in earlier reports; no global Git config changed.
Run integration with only this project's PostgreSQL/Redis healthy and generated
infrastructure/.env. It creates/removes only a new tai_test_<uuid> DB and exact
test-owned Redis streams. Never upload infrastructure/.env or expanded Compose env.
The final Android command returns blocked exit 2 today, rather than test success.

## GitHub target and enforcement

Owner confirmed https://github.com/Ggoolldd/trade on 2026-11-15. Origin is
configured. Git ls-remote succeeded with no refs: target is empty. Authenticated
GitHub CLI verified private=true and admin/push permission. The connector returned
404; the CLI succeeds outside the restricted network sandbox.

GitHub rulesets API returned HTTP 403: upgrade to GitHub Pro or make the repository
public to enable this feature. No subscription purchase or visibility change is
authorized or performed. This remains a real enforcement blocker.

Automatic approval review rejected git push because explicit approval to upload
the complete project/history is required. No upload occurred. At review time the
payload contains 370 tracked files and 26 commits; full-history Gitleaks scanned
approximately 1.02 MB and found no leaks. Ignored credentials, virtualenv, caches
and local infrastructure/.env are excluded. Scanner success cannot prove that all
project content is suitable for external storage. Explicit approval is pending.

[github-ruleset.json](../infrastructure/github-ruleset.json) is a prepared active
main-branch ruleset requiring `required-quality` with strict/up-to-date checks and
an empty bypass list. A local JSON file is not a live GitHub rule. Repository
administration permission and supported ruleset availability must be verified on
the chosen target; no plan/subscription purchase was made.

Once the target is explicitly identified: verify ownership/access, publish the
reviewed workflow, run Actions, resolve the real Android prerequisite, and apply
the ruleset as the final repository configuration step. Then read back the active
branch rules and record run/check URLs proving failed critical checks block merge.
Do not claim this enforcement based only on YAML syntax or local test results.

Reference API operation, after target/setup are resolved:

```text
gh api --method POST repos/OWNER/REPO/rulesets --input infrastructure/github-ruleset.json
gh api repos/OWNER/REPO/rules/branches/main
```

No remote API mutation was executed. Remote changes remain pending upload approval, supported branch enforcement
and Android prerequisite resolution. Dependent TAI-025 is not started.

Official references reviewed:
[GitHub rulesets REST](https://docs.github.com/en/rest/repos/rules#create-a-repository-ruleset),
[protected branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches),
[Gitleaks releases](https://github.com/gitleaks/gitleaks/releases),
[actionlint releases](https://github.com/rhysd/actionlint/releases).
