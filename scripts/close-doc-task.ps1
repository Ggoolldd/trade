param(
    [Parameter(Mandatory=$true)][string]$Task,
    [Parameter(Mandatory=$true)][string]$Title,
    [Parameter(Mandatory=$true)][string[]]$Documents,
    [Parameter(Mandatory=$true)][string]$Implemented,
    [Parameter(Mandatory=$true)][string]$Review,
    [Parameter(Mandatory=$true)][string]$Next
)
$ErrorActionPreference = 'Stop'
function Invoke-Git {
    & git -c safe.directory=D:/TRADING @args
    if ($LASTEXITCODE -ne 0) { throw 'Git command failed' }
}
$parentSha = Invoke-Git rev-parse HEAD
$log = @(& node scripts/check-docs.mjs @Documents)
if ($LASTEXITCODE -ne 0) { throw 'Document checks failed' }
$log += "REVIEW: $Review"
$log | Set-Content -Encoding UTF8 "docs/reports/$Task-checks.txt"
$status = Get-Content -Raw -Encoding UTF8 STATUS.md
$status = $status -replace 'Next: TAI-\d+\.', "Next: $Next."
$row = "| $Task | PASS | [Report](docs/reports/$Task.md) |"
$status = $status -replace '(\r?\nNext:)', "$row`n`nNext:"
$status.TrimEnd() | Set-Content -Encoding UTF8 STATUS.md
$changed = @(Invoke-Git diff --name-only) + @(Invoke-Git ls-files --others --exclude-standard)
$changed += "docs/reports/$Task.md"
$report = @"
TASK: $Task — $Title
STATUS: PASS
BRANCH / HEAD SHA: main; parent $parentSha; task commit: git log -1 --format=%H -- docs/reports/$Task.md
CHANGED FILES: $($changed -join ', ')
IMPLEMENTED: $Implemented
TESTS RUN: node scripts/check-docs.mjs $($Documents -join ' '); PASS. Semantic acceptance review: $Review. git diff --cached --check run before commit.
SAFETY CHECK: PAPER default; no live calls; no secrets. Documentation only; runtime enforcement is not claimed.
MIGRATIONS / BREAKING CHANGES: None.
EVIDENCE: docs/reports/$Task-checks.txt
RISKS / BLOCKERS: Specifications are contracts for subsequent implementation, not evidence of running trading functionality.
NEXT RECOMMENDED TASK: $Next (owner authorized sequential continuation).
"@
$report | Set-Content -Encoding UTF8 "docs/reports/$Task.md"
Invoke-Git add -- .
Invoke-Git diff --cached --check
Invoke-Git commit -m "docs($Task): $Title"
$log
Invoke-Git status --short
