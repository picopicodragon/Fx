# FINAL-PAPER-99: stage ONE explicit virtual-only communication-latch release.
# Do not run while the current paper supervisor is active.
# Does not clear the latch now, renew paid AI, change journal, or place orders.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$Mt4FilesDirectory,
    [switch]$ApproveVirtualCommRelease,
    [string]$StateRoot = ''
)
$ErrorActionPreference = 'Stop'
if (-not $ApproveVirtualCommRelease) {
    throw 'Explicit -ApproveVirtualCommRelease required. NO_GO'
}
if (-not $StateRoot) {
    $StateRoot = Join-Path $env:USERPROFILE 'Documents\FXForwardEvidence\final_virtual_paper'
}
if (-not (Test-Path -LiteralPath $StateRoot -PathType Container)) {
    throw 'Missing existing paper state. NO_GO'
}
if (-not (Test-Path -LiteralPath $Mt4FilesDirectory -PathType Container)) {
    throw 'Missing DEMO MQL4\Files. NO_GO'
}
$mt4 = (Resolve-Path -LiteralPath $Mt4FilesDirectory).Path.TrimEnd('\')
if (-not $mt4.EndsWith('\MQL4\Files',[StringComparison]::OrdinalIgnoreCase)) {
    throw 'Expected exact DEMO MQL4\Files path. NO_GO'
}
# No user-private process arguments are printed. Process discovery failures
# and any supervisor instance on any worktree block approval staging.
try {
    $active = @(Get-CimInstance Win32_Process -ErrorAction Stop |
        Where-Object {
            $_.Name -in @('python.exe','pythonw.exe','py.exe') -and
            $_.CommandLine -match 'research\.final_paper_runtime'
        })
} catch {
    throw 'Cannot attest supervisor absence. NO_GO'
}
if ($active.Count -gt 0) {
    throw 'Python paper supervisor appears active. No permit staged. NO_GO'
}
if (Test-Path -LiteralPath (Join-Path $StateRoot '.single_operator.lock')) {
    throw 'Runtime safety lock present. Do not remove. NO_GO'
}
$approval = 'APPROVE_INTERNAL_VIRTUAL_COMMUNICATION_LATCH_RELEASE_ONLY'
& python -m research.final_paper_manual_comm_release --state-root $StateRoot --mt4-files $mt4 --operator-approval $approval
if ($LASTEXITCODE -ne 0) {
    throw 'Virtual-only communication release preflight failed closed. NO_GO'
}
Write-Host 'One-use approval staged. Latch is NOT yet cleared.'
Write-Host 'New paper supervisor, if started safely, may apply on next fresh quote.'
Write-Host 'Independent calendar/clock/cost gates and paid-AI lifetime 6/6 remain CLOSED.'
