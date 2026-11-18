# FINAL-PAPER-34: read-only FREE observation restart verification.
# No orders/API, no lock removal and no automatic supervisor launch.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$Mt4FilesDirectory,
    [string]$StateRoot = ''
)
$ErrorActionPreference='Stop'
if (-not $StateRoot) {
    $StateRoot=Join-Path $env:USERPROFILE 'Documents\FXForwardEvidence\final_virtual_paper'
}
if (-not (Test-Path -LiteralPath $StateRoot -PathType Container)) {
    throw 'Paper state root missing; no restart. NO_GO'
}
if (-not (Test-Path -LiteralPath $Mt4FilesDirectory -PathType Container)) {
    throw 'MT4 Files missing; no restart. NO_GO'
}
$mt4=(Resolve-Path -LiteralPath $Mt4FilesDirectory).Path.TrimEnd('\')
if (-not $mt4.EndsWith('\MQL4\Files',[StringComparison]::OrdinalIgnoreCase)) {
    throw 'Unexpected MT4 Files directory; no restart. NO_GO'
}
# Fail closed when native process listing is unavailable or returns any
# running paper supervisor, regardless of worktree or paid/free settings.
try {
    $allPython=@(Get-CimInstance Win32_Process -ErrorAction Stop |
        Where-Object {
            $_.Name -in @('python.exe','pythonw.exe','py.exe') -and
            $_.CommandLine -match 'research\.final_paper_runtime'
        })
} catch {
    throw 'Cannot independently inspect Python processes; no restart. NO_GO'
}
if ($allPython.Count -gt 0) {
    $ids=@($allPython | ForEach-Object { $_.ProcessId })
    Write-Host ('Existing paper Python supervisor PID(s): ' + ($ids -join ', '))
    throw 'One or more paper supervisors appear active; DO NOT start another.'
}
$lock=Join-Path $StateRoot '.single_operator.lock'
if (Test-Path -LiteralPath $lock) {
    throw 'Paper safety lock exists; never remove it for automatic restart.'
}
$out=Join-Path $StateRoot ('free_resume_preflight_' +
    (Get-Date -Format 'yyyyMMdd_HHmmss_fff') + '.json')
& python -m research.final_paper_free_resume_preflight --state-root $StateRoot --mt4-files $mt4 --out $out
if ($LASTEXITCODE -ne 0) {
    throw 'Read-only free observation preflight failed closed. NO_GO.'
}
Write-Host ('Read-only restart preflight saved: ' + $out)
Write-Host 'No process was started; existing 6/6 paid AI cap remains in force.'
Write-Host 'On later free observation restart, >600s gap latches communication risk; do not auto-clear.'
