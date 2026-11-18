# FINAL-PAPER-64: read-only final paper readiness and billing blockers.
# No API calls, lock/latch modifications, order interfaces or restart.
[CmdletBinding()]
param(
    [string]$StateRoot = '',
    [string]$BillingStatement = '',
    [string]$EventCalendar = ''
)
$ErrorActionPreference='Stop'
if (-not $StateRoot) {
    $StateRoot=Join-Path $env:USERPROFILE 'Documents\FXForwardEvidence\final_virtual_paper'
}
if (-not (Test-Path -LiteralPath $StateRoot -PathType Container)) {
    throw 'Virtual-paper state root missing. NO_GO'
}
$report=Join-Path $StateRoot ('release_matrix_' +
    (Get-Date -Format 'yyyyMMdd_HHmmss_fff') + '.json')
$cmd=@('-m','research.final_paper_release_matrix',
    '--state-root',$StateRoot,'--out',$report)
if ($BillingStatement) {
    if (-not (Test-Path -LiteralPath $BillingStatement -PathType Leaf)) {
        throw 'Optional operator billing evidence file missing. NO_GO'
    }
    $cmd+=@('--billing-statement',$BillingStatement)
}
if ($EventCalendar) {
    if (-not (Test-Path -LiteralPath $EventCalendar -PathType Leaf)) {
        throw 'Optional research macro-event archive missing. NO_GO'
    }
    $cmd+=@('--event-calendar',$EventCalendar)
}
& python @cmd
if ($LASTEXITCODE -ne 0) {
    throw 'Read-only readiness review failed closed. No risk latch clearance.'
}
Write-Host ('Read-only readiness matrix saved: ' + $report)
Write-Host 'No order/paid-AI/virtual-entry activation was performed.'
