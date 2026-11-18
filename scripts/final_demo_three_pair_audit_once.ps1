# DEMO-SPRINT-56: read-only completed USD/JPY EUR/JPY EUR/USD AI ledger audit.
# No MT4, no network/API, no order intent, no trading permission.
[CmdletBinding()]
param([string]$EvidenceRoot = '')
$ErrorActionPreference = 'Stop'
if (-not $EvidenceRoot) {
    $EvidenceRoot = Join-Path $env:USERPROFILE 'Documents\FXForwardEvidence'
}
$ledgerDir = Join-Path $EvidenceRoot 'final_demo_periodic'
if (-not (Test-Path -LiteralPath $ledgerDir -PathType Container)) {
    throw 'Missing saved AI ledger directory. NO_GO'
}
$out = Join-Path $EvidenceRoot ('three_pair_ai_audit_' +
    (Get-Date -Format 'yyyyMMdd_HHmmss_fff') + '.json')
& python -m research.final_demo_three_pair_audit `
    --ledger-directory $ledgerDir --out $out
if ($LASTEXITCODE -ne 0) {
    throw 'Three-pair research audit failed closed. Check AI ledgers. No retry.'
}
Write-Host ('Saved READ-ONLY three-pair AI audit: ' + $out)
Write-Host 'Research ledger verification only. NO MT4 orders authorized.'
