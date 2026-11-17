# DEMO-SPRINT-43: one safe operator-run, choose fresh MT4 3-pair capture,
# copy same timestamp 3 files, and perform FREE preflight automatically.
# Explicitly no paid API, no orders, no MT4 terminal control.
[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)][string]$Mt4FilesDirectory,
  [Parameter(Mandatory=$true)][string[]]$NewsBundle
)
$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $Mt4FilesDirectory -PathType Container)) {
  throw 'MT4 MQL4\Files folder does not exist; no analysis.'
}
$canonical = (Resolve-Path -LiteralPath $Mt4FilesDirectory).Path.TrimEnd('\')
if (-not $canonical.EndsWith('\MQL4\Files', [StringComparison]::OrdinalIgnoreCase)) {
  throw 'Only the current MT4 MQL4\Files folder is accepted.'
}
$all = @(Get-ChildItem -LiteralPath $canonical -File -Filter 'FxDemoH1_USDJPY_*.csv')
if ($all.Count -eq 0) { throw 'No MT4 H1 export CSV. Run read-only script once.' }
$latest = $all | Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 1
$suffix = $latest.BaseName.Substring('FxDemoH1_USDJPY_'.Length)
if ($suffix -notmatch '^[0-9]{8}_[0-9]{6}$') { throw 'Invalid CSV filename stamp.' }
$symbols = @('USDJPY','EURJPY','EURUSD')
$inputs = @()
$seenEpochs = @()
foreach ($symbol in $symbols) {
  $filename = 'FxDemoH1_' + $symbol + '_' + $suffix + '.csv'
  $file = Join-Path $canonical $filename
  if (-not (Test-Path -LiteralPath $file -PathType Leaf)) {
    throw ('Three-pair export incomplete: ' + $symbol)
  }
  $rows = @(Import-Csv -LiteralPath $file)
  if ($rows.Count -ne 120) { throw ('H1 not 120 bars: ' + $symbol) }
  if ($rows[0].pair -ne $symbol -or $rows[0].timeframe -ne 'H1') {
    throw ('H1 pair/timeframe mismatch: ' + $symbol)
  }
  if (@($rows | Select-Object -ExpandProperty capture_epoch_utc_pc -Unique).Count -ne 1) {
    throw ('H1 capture epoch inconsistent: ' + $symbol)
  }
  $seenEpochs += [long]$rows[0].capture_epoch_utc_pc
  $inputs += $file
}
if (@($seenEpochs | Select-Object -Unique).Count -ne 1) {
  throw 'Three-pair capture epochs disagree, no analysis.'
}
$ageSec = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds() - $seenEpochs[0]
if ($ageSec -lt -60 -or $ageSec -gt 480) {
  Write-Host ('H1_CAPTURE_STALE_OR_CLOCK_SKEW; age_seconds=' + $ageSec)
  throw 'Refresh H1 by re-running the read-only MT4 script, then retry free preflight only.'
}
$base = Join-Path $env:USERPROFILE 'Documents\FXForwardEvidence'
if (-not (Test-Path -LiteralPath $base -PathType Container)) {
  throw 'Expected evidence root does not exist.'
}
$dst = Join-Path $base ('h1_copy_' + (Get-Date -Format 'yyyyMMdd_HHmmss_fff'))
New-Item -ItemType Directory -Path $dst -ErrorAction Stop | Out-Null
foreach ($file in $inputs) {
  Copy-Item -LiteralPath $file -Destination $dst -ErrorAction Stop
}
Write-Host ('Copied 3 real H1 CSVs to: ' + $dst)
Write-Host ('H1 source age in seconds (PC derived): ' + $ageSec)
& (Join-Path $PSScriptRoot 'final_demo_periodic_once.ps1') -H1CopiedDirectory $dst -NewsBundle $NewsBundle
if (-not $?) { throw 'Free H1/news preflight failed, NO_GO.' }
Write-Host 'Free preflight finished. No API calls or orders were authorized.'
