# FX-FWD-037: one-shot, no-order offline research audit launcher.
# Never installs an MT4 script, schedules a task, accesses the network,
# reads credentials or starts a trading service. Requires Python on PATH.
param(
  [Parameter(Mandatory = $true)][string]$Manifest,
  [Parameter(Mandatory = $true)][string]$ReportsDir,
  [Parameter(Mandatory = $true)][string]$Output
)

$ErrorActionPreference = "Stop"
if ([string]::IsNullOrWhiteSpace($Manifest) -or
    [string]::IsNullOrWhiteSpace($ReportsDir) -or
    [string]::IsNullOrWhiteSpace($Output)) {
  throw "FWD-037 invalid arguments (NO_GO)"
}
if (-not (Test-Path -LiteralPath $Manifest -PathType Leaf)) {
  throw "FWD-037 manifest not found (NO_GO)"
}
if (-not (Test-Path -LiteralPath $ReportsDir -PathType Container)) {
  throw "FWD-037 reports directory missing (NO_GO)"
}
if (Test-Path -LiteralPath $Output) {
  throw "FWD-037 output already exists (NO_GO)"
}
# No -ExecutionPolicy Bypass; the operator's Windows policy remains intact.
& python -m research.forward_offline_batch --manifest $Manifest --reports-dir $ReportsDir --out $Output
if ($LASTEXITCODE -ne 0) {
  throw "FWD-037 offline research audit failed closed (NO_GO)"
}
Write-Output "FWD-037 offline audit complete. NO_GO; demo and real orders remain prohibited."
