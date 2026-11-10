# FWD-067 operator-controlled, one-shot OFFLINE evidence review.
# Neither compiles MQL4 nor runs MetaEditor/MT4, installs a script, schedules
# a task, touches a broker account, connects a service or sends an order.
param(
    [Parameter(Mandatory=$true)][string]$Mql4Source,
    [Parameter(Mandatory=$true)][string]$CompilerManifest,
    [Parameter(Mandatory=$true)][string]$CompilerReport,
    [Parameter(Mandatory=$true)][string[]]$QuoteCsvs,
    [Parameter(Mandatory=$true)][string]$AsOfUtc,
    [Parameter(Mandatory=$true)][string]$SeriesReport
)
$ErrorActionPreference = "Stop"
foreach ($p in @($Mql4Source, $CompilerManifest) + $QuoteCsvs) {
    if (-not (Test-Path -LiteralPath $p -PathType Leaf)) {
        throw "FWD-067 missing manually supplied file (NO_GO)"
    }
}
foreach ($p in @($CompilerReport, $SeriesReport)) {
    if (Test-Path -LiteralPath $p) {
        throw "FWD-067 output already exists (NO_GO)"
    }
}
& python -m research.forward_metaeditor_evidence --manifest $CompilerManifest --source $Mql4Source --out $CompilerReport
if ($LASTEXITCODE -ne 0) { throw "FWD-067 compiler record failed closed (NO_GO)" }
$cmd = @("-m", "research.forward_mt4_v2_series", "--asof-utc", $AsOfUtc, "--out", $SeriesReport)
foreach ($csv in $QuoteCsvs) { $cmd += @("--csv", $csv) }
& python @cmd
if ($LASTEXITCODE -ne 0) { throw "FWD-067 quote evidence failed closed (NO_GO)" }
Write-Output "FWD-067 local evidence audit complete. NO_GO; DEMO and LIVE orders prohibited."
