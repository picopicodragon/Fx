# Human-triggered staging for the exact current 2026-11-20 PAPER incident.
# NEVER automatically stops the active paper supervisor or changes MT4.
# No automatic trading, billable AI request, or risk latch modification.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$Mt4FilesDirectory,
    [Parameter(Mandatory=$true)][string]$OperatorApproval,
    [string]$StateRoot=''
)
$ErrorActionPreference='Stop'
$expected='APPROVE_20261120_INCIDENT_INTERNAL_VIRTUAL_COMMUNICATION_RELEASE_ONLY'
if ($OperatorApproval -cne $expected) {
    throw 'This exact, current incident requires separate operator approval.'
}
if (-not $StateRoot) {
    $StateRoot=Join-Path $env:USERPROFILE 'Documents\FXForwardEvidence\final_virtual_paper'
}
if (-not (Test-Path -LiteralPath $StateRoot -PathType Container)) {
    throw 'Existing research state root missing. NO_GO'
}
$mt4=(Resolve-Path -LiteralPath $Mt4FilesDirectory -ErrorAction Stop).Path.TrimEnd('\')
if (-not $mt4.EndsWith('\MQL4\Files',[StringComparison]::OrdinalIgnoreCase)) {
    throw 'Actual DEMO MT4 source required. NO_GO'
}
# A lock alone is not process proof. Check both independently and refuse
# ambiguous permission errors. An active supervisor is never terminated.
$python=@(Get-CimInstance Win32_Process -ErrorAction Stop |
    Where-Object {
        $_.Name -match '^python(w)?\.exe$' -and
        $_.CommandLine -match 'research\.final_paper_runtime'
    })
if ($python.Count -ne 0) {
    throw 'Python paper runtime still running. Manually plan its safe stop first.'
}
if ((Test-Path -LiteralPath (Join-Path $StateRoot '.single_operator.lock'))) {
    throw 'Existing supervisor lock requires independent manual review. Never delete it automatically.'
}
& python -m research.final_paper_current_incident_release --state-root $StateRoot --mt4-files $mt4 --operator-approval $OperatorApproval
if ($LASTEXITCODE -ne 0) {
    throw 'No valid current-incident approval was staged. Keep all trading holds.'
}
Write-Host 'COMMUNICATION RELEASE STAGED ONLY. No active latch was cleared.'
Write-Host 'If/when the Python observer is safely restarted, a new quote MAY consume it once.'
Write-Host 'Macro evidence, cost, provider billing and broker-order holds remain separate.'
