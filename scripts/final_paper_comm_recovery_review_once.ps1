# FINAL-PAPER-39: read-only evidence for manual communication recovery review.
# No lock removal, no journal mutation, no AI requests or broker orders.
[CmdletBinding()]
param([string]$StateRoot='')
$ErrorActionPreference='Stop'
if (-not $StateRoot) {
    $StateRoot=Join-Path $env:USERPROFILE 'Documents\FXForwardEvidence\final_virtual_paper'
}
if (-not (Test-Path -LiteralPath $StateRoot -PathType Container)) {
    throw 'Virtual paper state root missing. NO_GO'
}
$out=Join-Path $StateRoot ('comm_recovery_review_' +
    (Get-Date -Format 'yyyyMMdd_HHmmss_fff') + '.json')
& python -m research.final_paper_comm_recovery_review --state-root $StateRoot --out $out
if ($LASTEXITCODE -ne 0) {
    throw 'Communication recovery evidence review fail closed. No automatic release.'
}
Write-Host ('Read-only communication recovery review saved: ' + $out)
Write-Host 'This report does NOT clear any risk latch or authorize a new AI call.'
