# FINAL-AI-INTEGRATION: read-only real DEMO final readiness + isolated E2E
# rehearsal. DO NOT interrupt the existing Python or MT4 observer.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$Mt4FilesDirectory,
    [string]$StateRoot='',
    [string]$OfficialArchiveDirectory=''
)
$ErrorActionPreference='Stop'
if (-not $StateRoot) {
    $StateRoot=Join-Path $env:USERPROFILE 'Documents\FXForwardEvidence\final_virtual_paper'
}
if (-not $OfficialArchiveDirectory) {
    $OfficialArchiveDirectory=Join-Path $StateRoot 'official_public_capture_20261120_113041_303'
}
if (-not (Test-Path -LiteralPath $StateRoot -PathType Container)) {
    throw 'Actual existing paper state root missing. NO_GO'
}
$mt4=(Resolve-Path -LiteralPath $Mt4FilesDirectory -ErrorAction Stop).Path.TrimEnd('\')
if (-not $mt4.EndsWith('\MQL4\Files',[StringComparison]::OrdinalIgnoreCase)) {
    throw 'Actual Rakuten DEMO MT4 MQL4\Files required. NO_GO'
}
$archive=(Resolve-Path -LiteralPath $OfficialArchiveDirectory -ErrorAction Stop).Path
if (-not (Split-Path -Leaf $archive).StartsWith('official_public_capture_')) {
    throw 'Expected immutable official archive. NO_GO'
}
Write-Host '1/2: Review immutable quote/official archives, live paper and paid 6/6.'
$now=Get-Date -Format 'yyyyMMdd_HHmmss_fff'
$readiness=Join-Path $StateRoot ('final_integrated_readiness_'+$now+'.json')
& python -m research.final_paper_integrated_readiness --state-root $StateRoot --mt4-files $mt4 --official-archive $archive --out $readiness
$codeReadiness=$LASTEXITCODE
Write-Host '2/2: Rehearse three-pair AI-to-risk engine with original quote, no live signals.'
$source=Get-ChildItem -LiteralPath $mt4 -File -Filter 'FxPaperQuote_*.csv' |
    Sort-Object -Property Name -Descending | Select-Object -First 1
$codeExercise=2
if ($null -ne $source) {
    $exercise=Join-Path $StateRoot ('final_integrated_rehearsal_'+$now+'.json')
    & python -m research.final_paper_integrated_rehearsal --quote $source.FullName --out $exercise
    $codeExercise=$LASTEXITCODE
    if ($codeExercise -eq 0) {
        Write-Host ('Three-pair isolated no-order evidence: '+$exercise)
    }
}
if ($codeReadiness -eq 0) {
    Write-Host ('Real running paper AI readiness evidence: '+$readiness)
}
Write-Host 'Missing independently verified macro event/time/clock/cost and new budget approvals remain blocking.'
Write-Host 'Risk latches and historical paid 6/6 are unchanged. NO orders or live AI calls.'
if ($codeReadiness -ne 0 -or $codeExercise -ne 0) {
    throw 'One or both independent read-only assessments were incomplete; remain NO_GO.'
}
