# DEMO-SPRINT-51: one operator-run using fresh 3-pair MT4 CLOSED H1.
# FREE by default. Only -AllowPaidAi with explicit pair(s) and model IDs
# may make bounded research-only inference calls after FREE preflight.
# No orders, no EA activation, no MT4 terminal control, no automatic retry.
[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)][string]$Mt4FilesDirectory,
  [Parameter(Mandatory=$true)][string[]]$NewsBundle,
  [switch]$AllowPaidAi,
  [string[]]$Pair = @(),
  [string]$AnalystModel = '',
  [string]$ReviewerModel = ''
)
$ErrorActionPreference = 'Stop'
if ($AllowPaidAi) {
  if (-not $Pair -or $Pair.Count -gt 3 -or
      @($Pair | Select-Object -Unique).Count -ne $Pair.Count -or
      @($Pair | Where-Object { $_ -notin @('USD/JPY','EUR/JPY','EUR/USD') }).Count -ne 0 -or
      -not $AnalystModel -or -not $ReviewerModel -or
      $AnalystModel -eq $ReviewerModel -or -not $env:OPENAI_API_KEY) {
    throw 'Explicit paid model pair(s), distinct IDs and OPENAI_API_KEY required. NO_GO'
  }
} elseif ($Pair.Count -gt 0 -or $AnalystModel -or $ReviewerModel) {
  throw 'Paid AI parameters must have explicit -AllowPaidAi. NO_GO'
}
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
# FREE and paid checks use identical 420-second freshness upper bound.
if ($ageSec -lt -60 -or $ageSec -gt 420) {
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
if ($AllowPaidAi) {
  # A narrow second freshness gate protects against prolonged news preflight.
  # When it expires, NO paid inference dispatch may occur.
  $ageAtPaidStart = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds() - $seenEpochs[0]
  if ($ageAtPaidStart -lt -60 -or $ageAtPaidStart -gt 420) {
    throw ('H1_CAPTURE_STALE_BEFORE_PAID_RESEARCH; age_seconds=' + $ageAtPaidStart)
  }
  & (Join-Path $PSScriptRoot 'final_demo_periodic_once.ps1') `
      -H1CopiedDirectory $dst -NewsBundle $NewsBundle `
      -Pair $Pair -AllowPaidAi `
      -AnalystModel $AnalystModel -ReviewerModel $ReviewerModel
  if (-not $?) {
    throw 'Paid research failed or ledger ambiguous. Never retry automatically. NO_GO'
  }
  Write-Host 'Explicit paid AI research completed; still NO MT4 orders or trading permission.'
}
