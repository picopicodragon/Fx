# FINAL-PAPER-139: real USDJPY/EURJPY/EURUSD quote spread/regime profile.
# Read-only, no API, no orders, no risk changes. 240 most recent MT4 files.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$Mt4FilesDirectory,
    [string]$StateRoot='',
    [int]$MaxFiles=240
)
$ErrorActionPreference='Stop'
if (-not $StateRoot) {
    $StateRoot=Join-Path $env:USERPROFILE 'Documents\FXForwardEvidence\final_virtual_paper'
}
if (-not (Test-Path -LiteralPath $StateRoot -PathType Container)) {
    throw 'Existing evidence folder required. NO_GO'
}
$mt4=(Resolve-Path -LiteralPath $Mt4FilesDirectory -ErrorAction Stop).Path.TrimEnd('\')
if (-not $mt4.EndsWith('\MQL4\Files',[StringComparison]::OrdinalIgnoreCase)) {
    throw 'Expected real DEMO MQL4\Files. NO_GO'
}
if ($MaxFiles -lt 2 -or $MaxFiles -gt 240) {
    throw 'MaxFiles must be from 2 to 240. NO_GO'
}
$out=Join-Path $StateRoot ('quote_regime_'+
    (Get-Date -Format 'yyyyMMdd_HHmmss_fff')+'.json')
& python -m research.final_paper_quote_regime_profile --mt4-files $mt4 --max-files $MaxFiles --out $out
if ($LASTEXITCODE -ne 0) {
    throw 'Real MT4 three-pair quote regime audit failed. No state changed.'
}
Write-Host ('Real-source research profile: '+$out)
Write-Host 'Observed spread and clock jitter are not independent cost or clock attestation.'
