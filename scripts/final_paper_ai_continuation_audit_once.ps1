# FINAL-PAPER-18: no-cost, no-broker, read-only AI usage and journal audit.
# Never clears AI journals, relatches, or raises the paid inference limit.
[CmdletBinding()]
param([string]$StateRoot = '')
$ErrorActionPreference = 'Stop'
if (-not $StateRoot) {
    $StateRoot = Join-Path $env:USERPROFILE 'Documents\FXForwardEvidence\final_virtual_paper'
}
if (-not (Test-Path -LiteralPath $StateRoot -PathType Container)) {
    throw 'Missing paper portfolio directory. NO_GO'
}
$destination = Join-Path $StateRoot ('ai_continuation_audit_' +
    (Get-Date -Format 'yyyyMMdd_HHmmss_fff') + '.json')
& python -m research.final_paper_ai_continuation_audit --state-root $StateRoot --out $destination
if ($LASTEXITCODE -ne 0) {
    throw 'Unreconciled API ledger. No paid retry, no state deletion, NO_GO.'
}
Write-Host ('Read-only AI usage report: ' + $destination)
Write-Host 'No additional paid AI calls authorized. Check provider billing before seeking renewal.'
