# FINAL-PAPER-132: read-only forensic report for no Python process + safety lock.
# NEVER stop/start MT4 or Python. NEVER remove/rename lock or clear any latch.
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
    throw 'No existing final paper state root. NO_GO'
}
if (-not (Test-Path -LiteralPath $Mt4FilesDirectory -PathType Container)) {
    throw 'No existing MT4 DEMO MQL4 Files. NO_GO'
}
$mt4=(Resolve-Path -LiteralPath $Mt4FilesDirectory).Path.TrimEnd('\')
if (-not $mt4.EndsWith('\MQL4\Files',[StringComparison]::OrdinalIgnoreCase)) {
    throw 'Only actual DEMO MQL4\Files accepted. NO_GO'
}
try {
    $all=@(Get-CimInstance Win32_Process -ErrorAction Stop)
} catch {
    throw 'Could not verify process list. NO_GO'
}
$active=@($all | Where-Object {
    $_.Name -in @('python.exe','pythonw.exe','py.exe') -and
    $_.CommandLine -match 'research\.final_paper_runtime'
})
$mt4Processes=@($all | Where-Object { $_.Name -ieq 'terminal.exe' })
$lock=Join-Path $StateRoot '.single_operator.lock'
$report=Join-Path $StateRoot ('supervisor_incident_'+
    (Get-Date -Format 'yyyyMMdd_HHmmss_fff')+'.json')
& python -m research.final_paper_supervisor_incident --state-root $StateRoot --mt4-files $mt4 --out $report
if ($LASTEXITCODE -ne 0) {
    throw 'Forensic verification failed closed. Do not touch lock or relaunch.'
}
Write-Host ('WINDOWS_PYTHON_SUPERVISOR_PROCESS_COUNT='+$active.Count)
Write-Host ('WINDOWS_MT4_TERMINAL_PROCESS_COUNT='+$mt4Processes.Count)
Write-Host ('SAFETY_LOCK_PRESENT='+[bool](Test-Path -LiteralPath $lock))
Write-Host ('FORENSIC_REPORT='+$report)
if ($active.Count -eq 0 -and (Test-Path -LiteralPath $lock)) {
    Write-Warning 'POSSIBLE_ORPHAN_LOCK: Python absent, safety lock present. CAUSE UNPROVEN.'
    Write-Warning 'Do not remove/rename lock. Current long interruption is NOT covered by historical approval.'
}
if ($active.Count -gt 0) {
    Write-Warning 'A Python supervisor is present: do not launch another one.'
}
Write-Host 'No restart, risk latch release, paid AI call, virtual entry or broker order executed.'
