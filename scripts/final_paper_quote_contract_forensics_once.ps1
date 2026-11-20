# FINAL-PAPER-157: read-only incident-specific quote and contract inspector.
# Preserves all original CSV bytes and MT4/Python journal and process state.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$Mt4FilesDirectory,
    [string]$Target = 'FxPaperQuote_20261119_035152.csv',
    [string]$StateRoot = ''
)
$ErrorActionPreference='Stop'
if (-not $StateRoot) {
    $StateRoot=Join-Path $env:USERPROFILE 'Documents\FXForwardEvidence\final_virtual_paper'
}
if (-not (Test-Path -LiteralPath $StateRoot -PathType Container)) {
    throw 'Existing state root unavailable. NO_GO'
}
$mt4=(Resolve-Path -LiteralPath $Mt4FilesDirectory -ErrorAction Stop).Path.TrimEnd('\')
if (-not $mt4.EndsWith('\MQL4\Files',[StringComparison]::OrdinalIgnoreCase)) {
    throw 'Existing DEMO MQL4\Files source required. NO_GO'
}
if ($Target -notmatch '^FxPaperQuote_\d{8}_\d{6}\.csv$') {
    throw 'Original quote basename required, not a path. NO_GO'
}
$original=Join-Path $mt4 $Target
if (-not (Test-Path -LiteralPath $original -PathType Leaf)) {
    throw 'Target original DEMO CSV missing. Do not replace it. NO_GO'
}
$originalHash=(Get-FileHash -LiteralPath $original -Algorithm SHA256).Hash
$out=Join-Path $StateRoot ('quote_contract_forensics_'+
    (Get-Date -Format 'yyyyMMdd_HHmmss_fff')+'.json')
Write-Host ('Analyzing original '+$Target+' without editing it')
& python -m research.final_paper_quote_contract_forensics --mt4-files $mt4 --target $Target --out $out
$inspectionExit=$LASTEXITCODE
$newHash=(Get-FileHash -LiteralPath $original -Algorithm SHA256).Hash
if ($originalHash -ne $newHash) {
    throw 'Original SHA256 changed DURING review. Stop and preserve evidence.'
}
if ($inspectionExit -ne 0) {
    throw 'Read-only field classifier could not verify the original. NO_GO'
}
Write-Host ('Detailed safe field codes: '+$out)
Write-Host 'Original CSV SHA256 remained unchanged.'
Write-Host 'Field codes are research only. Multi-day strict validation remains NO_GO.'
Write-Host 'No paid AI, market order, virtual entry, communication reset or journal write.'
