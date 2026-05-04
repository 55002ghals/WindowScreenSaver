# Sync dev tree -> prod folder, applying prod-only transformations.
# Usage:  pwsh -File .\sync-to-prod.ps1
# Idempotent: safe to re-run.

$ErrorActionPreference = "Stop"
$DEV  = "C:\Users\ab550\OneDrive\Desktop\proj_WindowsContext"
$PROD = "C:\Users\ab550\OneDrive\Desktop\proj_WindowsContext_prod"

if (-not (Test-Path $PROD)) {
    New-Item -ItemType Directory -Path $PROD | Out-Null
}

# robocopy /MIR with exclusions. /MIR mirrors -> deletes prod-only artifacts that aren't in dev (excluding .git).
$exDirs  = @("tests", "build", "dist", "installer\Output", "__pycache__", ".git", ".pytest_cache")
$exFiles = @("rebuild.bat", "requirements-dev.txt", "pytest.ini", "Task-*.md", "PLAN.md", "sync-to-prod.ps1")

$xdArgs = $exDirs  | ForEach-Object { "/XD"; (Join-Path $DEV $_) }
$xfArgs = $exFiles | ForEach-Object { "/XF"; $_ }

robocopy $DEV $PROD /MIR /NFL /NDL /NJH /NJS /NC /NS /NP @xdArgs @xfArgs
# robocopy exit codes 0-7 are success; 8+ are real errors.
if ($LASTEXITCODE -ge 8) { throw "robocopy failed: $LASTEXITCODE" }

# Flip IS_PROD_BUILD = False  ->  True in prod copy.
$bc = Join-Path $PROD "src\build_config.py"
(Get-Content $bc -Raw) -replace "IS_PROD_BUILD\s*=\s*False", "IS_PROD_BUILD = True" |
    Set-Content $bc -Encoding UTF8 -NoNewline

Write-Host "Sync complete: $PROD"
Write-Host "Verify: prod/src/build_config.py should contain IS_PROD_BUILD = True"
