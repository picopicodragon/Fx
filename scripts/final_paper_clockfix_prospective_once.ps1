# FINAL-PAPER-164: exclusively offline; prospective after manual, attested EA cutover.
# DO NOT run to install EA, to stop Python or to clear communication latch.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$Mt4FilesDirectory,
    [Parameter(Mandatory=$true)][string]$CutoverUtc,
    [string]$BaselineReport='',
    [string]$StateRoot=''
)
$ErrorActionPreference='Stop'
if (-not $StateRoot) {
    $StateRoot=Join-Path $env:USERPROFILE 'Documents\FXForwardEvidence\final_virtual_paper'
}
if (-not $BaselineReport) {
    $BaselineReport=Join-Path $StateRoot 'quote_time_order_campaign_20261120_140145_466.json'
}
if (-not (Test-Path -LiteralPath $StateRoot -PathType Container)) {
    throw 'Existing evidence state root not present. NO_GO'
}
$mt4=(Resolve-Path -LiteralPath $Mt4FilesDirectory -ErrorAction Stop).Path.TrimEnd('\')
if (-not $mt4.EndsWith('\MQL4\Files',[StringComparison]::OrdinalIgnoreCase)) {
    throw 'Existing DEMO MQL4\Files required. NO_GO'
}
$baseline=(Resolve-Path -LiteralPath $BaselineReport -ErrorAction Stop).Path
$candidate=Join-Path (Split-Path -Parent $PSScriptRoot) 'mt4\read_only\FxFinalPaperReadOnlyObserver.mq4'
if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) {
    throw 'V2 candidate source absent. NO_GO'
}
$out=Join-Path $StateRoot ('clockfix_prospective_'+
    (Get-Date -Format 'yyyyMMdd_HHmmss_fff')+'.json')
Write-Host 'Read-only baseline and prospective original quote integrity review'
& python -m research.final_paper_clockfix_prospective --mt4-files $mt4 --baseline-report $baseline --cutover-utc $CutoverUtc --candidate-source $candidate --out $out
if ($LASTEXITCODE -ne 0) {
    throw 'Clock-fix baseline or claimed prospective source failed closed. Originals preserved.'
}
Write-Host ('No-trade clockfix research audit: '+$out)
Write-Host 'Manually supplied cutover date is NOT independent EA deployment proof.'
Write-Host 'No EA replacement, MetaEditor compile, monitor restart, journal edit, API or order.'
Write-Host 'Communication/risk latches, paid calls 6/6 and all virtual entry gates unchanged.'
