# FINAL-PAPER-30: diagnose quote gap without stopping existing operator.
# Read-only; does not clear lock, journal or paid AI ledger. No orders/API.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$Mt4FilesDirectory,
    [string]$StateRoot = ''
)
$ErrorActionPreference = 'Stop'
if (-not $StateRoot) {
    $StateRoot = Join-Path $env:USERPROFILE 'Documents\FXForwardEvidence\final_virtual_paper'
}
if (-not (Test-Path -LiteralPath $StateRoot -PathType Container)) {
    throw 'Virtual paper state folder missing. NO_GO'
}
if (-not (Test-Path -LiteralPath $Mt4FilesDirectory -PathType Container)) {
    throw 'MT4 files folder missing. NO_GO'
}
$mt4 = (Resolve-Path -LiteralPath $Mt4FilesDirectory).Path.TrimEnd('\')
if (-not $mt4.EndsWith('\MQL4\Files',
        [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Expected existing DEMO MT4 MQL4\Files path. NO_GO'
}
$out = Join-Path $StateRoot ('stream_diagnostic_' +
    (Get-Date -Format 'yyyyMMdd_HHmmss_fff') + '.json')
& python -m research.final_paper_stream_diagnostic --state-root $StateRoot --mt4-files $mt4 --out $out
if ($LASTEXITCODE -ne 0) {
    throw 'DEMO quote gap diagnostic failed closed; do not clear runtime lock.'
}
Write-Host ('Read-only producer/consumer gap report: ' + $out)
Write-Host 'MT4 Expert status and Python process presence must be checked separately.'
