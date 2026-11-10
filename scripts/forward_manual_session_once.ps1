# FWD-052: operator-run verification of local, already captured MT4 DEMO CSV files.
# Does not discover MT4 terminals, start processes other than Python,
# modify terminal folders, connect to the network or trade.
param(
  [Parameter(Mandatory = $true)][string]$CapturesDir,
  [Parameter(Mandatory = $true)][string]$Manifest,
  [Parameter(Mandatory = $true)][string]$AsOfUtc,
  [Parameter(Mandatory = $true)][string]$SessionReport,
  [Parameter(Mandatory = $true)][string]$Mql4Source,
  [Parameter(Mandatory = $true)][string]$SourceReport
)
$ErrorActionPreference = "Stop"
if (-not (Test-Path -LiteralPath $CapturesDir -PathType Container) -or
    -not (Test-Path -LiteralPath $Manifest -PathType Leaf) -or
    -not (Test-Path -LiteralPath $Mql4Source -PathType Leaf)) {
    throw "FWD-052 missing operator-selected local evidence (NO_GO)"
}
foreach ($target in @($SessionReport, $SourceReport)) {
    if (Test-Path -LiteralPath $target) {
        throw "FWD-052 output collision. No overwrite permitted (NO_GO)"
    }
}
& python -m research.forward_mt4_source_contract --source $Mql4Source --out $SourceReport
if ($LASTEXITCODE -ne 0) {
    throw "FWD-052 static source/parser contract failed (NO_GO)"
}
& python -m research.forward_manual_session --manifest $Manifest --captures-dir $CapturesDir --asof-utc $AsOfUtc --out $SessionReport
if ($LASTEXITCODE -ne 0) {
    throw "FWD-052 manual session failed closed (NO_GO)"
}
Write-Output "FWD-052 offline integrity reports created. NO_GO; no broker/demo orders authorized."
