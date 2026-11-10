# FX-FWD-042: Windows one-shot offline receipt chain preflight.
# This script does NOT read MT4 program directories, log in to broker,
# install tasks, change execution policy, send network requests or trade.
param(
  [Parameter(Mandatory = $true)][string]$ReceiptsDir,
  [Parameter(Mandatory = $true)][string[]]$ReceiptFiles,
  [Parameter(Mandatory = $true)][string]$ManifestOutput,
  [Parameter(Mandatory = $true)][string]$AuditOutput
)

$ErrorActionPreference = "Stop"
if (-not (Test-Path -LiteralPath $ReceiptsDir -PathType Container)) {
  throw "FWD-042 missing offline receipts directory (NO_GO)"
}
foreach ($target in @($ManifestOutput, $AuditOutput)) {
  if (Test-Path -LiteralPath $target) {
    throw "FWD-042 output exists; refusing overwrite (NO_GO)"
  }
}
if ($ReceiptFiles.Count -lt 1 -or $ReceiptFiles.Count -gt 10000) {
  throw "FWD-042 unsupported receipt count (NO_GO)"
}

$manifestArgs = @("-m", "research.forward_receipt_manifest",
                  "--receipts-dir", $ReceiptsDir,
                  "--out", $ManifestOutput)
foreach ($file in $ReceiptFiles) {
  $manifestArgs += @("--receipt", $file)
}
& python @manifestArgs
if ($LASTEXITCODE -ne 0) {
  throw "FWD-042 manifest creation failed closed (NO_GO)"
}
& python -m research.forward_receipt_chain --manifest $ManifestOutput --receipts-dir $ReceiptsDir --out $AuditOutput
if ($LASTEXITCODE -ne 0) {
  throw "FWD-042 chain audit failed closed (NO_GO)"
}
Write-Output "FWD-042 offline receipt chain checked. NO_GO; no broker/demo orders enabled."
