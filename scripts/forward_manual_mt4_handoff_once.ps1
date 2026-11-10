# FWD-047 manual-only MT4 export handoff, without launching MT4.
# Accepts an explicit source path under the current operator's control.
# Does not copy account details to Git, install scripts or enable AutoTrading.
param(
  [Parameter(Mandatory = $true)][string]$SourceCsv,
  [Parameter(Mandatory = $true)][string]$CaptureId,
  [Parameter(Mandatory = $true)][string]$CaptureDirectory
)
$ErrorActionPreference = "Stop"
if (-not (Test-Path -LiteralPath $SourceCsv -PathType Leaf)) {
  throw "FWD-047 source CSV does not exist (NO_GO)"
}
if (Test-Path -LiteralPath $CaptureDirectory) {
  throw "FWD-047 capture destination already exists (NO_GO)"
}
if ([string]::IsNullOrWhiteSpace($CaptureId)) {
  throw "FWD-047 capture ID missing (NO_GO)"
}
# The operator decides which read-only CSV to supply. No MT4 auto-discovery.
& python -m research.forward_manual_handoff --source $SourceCsv --capture-id $CaptureId --out-dir $CaptureDirectory
if ($LASTEXITCODE -ne 0) {
  throw "FWD-047 manual snapshot failed closed; inspect partial evidence (NO_GO)"
}
Write-Output "FWD-047 manual research snapshot saved; NO_GO. No trading activated."
