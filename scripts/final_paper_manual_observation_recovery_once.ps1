# FINAL-PAPER-137: OPERATOR-ONLY manual lock archival for FREE observation.
# Acknowledges an unexplained 2026-11-20 gap. Does NOT clear trading latch.
# Run ONLY after reviewing forensic evidence. NEVER unattended.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$Mt4FilesDirectory,
    [switch]$ApproveObservationOnlyRecovery,
    [string]$StateRoot = ''
)
$ErrorActionPreference = 'Stop'
if (-not $ApproveObservationOnlyRecovery) {
    throw 'Explicit -ApproveObservationOnlyRecovery required. NO_GO'
}
if (-not $StateRoot) {
    $StateRoot=Join-Path $env:USERPROFILE 'Documents\FXForwardEvidence\final_virtual_paper'
}
if (-not (Test-Path -LiteralPath $StateRoot -PathType Container)) {
    throw 'Existing evidence root absent. NO_GO'
}
$mt4=(Resolve-Path -LiteralPath $Mt4FilesDirectory -ErrorAction Stop).Path.TrimEnd('\')
if (-not $mt4.EndsWith('\MQL4\Files',[StringComparison]::OrdinalIgnoreCase)) {
    throw 'Actual DEMO MQL4\Files required. NO_GO'
}
try {
    $processes=@(Get-CimInstance Win32_Process -ErrorAction Stop |
        Where-Object { $_.Name -in @('python.exe','pythonw.exe','py.exe') })
} catch {
    throw 'Cannot independently inspect Windows Python process table. NO_GO'
}
if (@($processes | Where-Object { $null -eq $_.CommandLine }).Count -gt 0) {
    throw 'Python process has inaccessible/unknown command-line. NO_GO'
}
$active=@($processes | Where-Object {
    $_.CommandLine -match 'research\.final_paper_runtime'
})
if ($active.Count -ne 0) {
    throw 'Another paper supervisor is running. No archival allowed. NO_GO'
}
# The helper validates 550 cycles; journal head; 6/6 AI ledgers;
# positions zero; no unrelated risk latch; fresh quote; exact old lock;
# new 38h incident; and absence of any old comm-release permit.
$approval='ACKNOWLEDGE_20261120_GAP_RESUME_UNPAID_OBSERVATION_ONLY'
& python -m research.final_paper_manual_observation_recovery --state-root $StateRoot --mt4-files $mt4 --windows-absence-checked --operator-approval $approval
if ($LASTEXITCODE -ne 0) {
    throw 'Safety lock archive refused; do not delete lock or retry blindly. NO_GO'
}
Write-Host 'Original lock archived for forensic history; communication latch STILL ACTIVE.'
Write-Host 'No paid AI allowed. Check free-only observation preflight.'
& "$PSScriptRoot\final_paper_free_resume_preflight_once.ps1" -Mt4FilesDirectory $mt4 -StateRoot $StateRoot
Write-Host 'Free observation ONLY is a manual restart candidate. No process started.'
Write-Host 'New virtual entries, paid AI, demo and real orders remain prohibited.'
