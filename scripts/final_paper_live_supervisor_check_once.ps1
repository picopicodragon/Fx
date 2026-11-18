# FINAL-PAPER-105: existing Windows DEMO observer / paper supervisor proof.
# Read-only. No process stop/start, lock removal, MT4 orders, network, or API.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$Mt4FilesDirectory,
    [string]$StateRoot = '',
    [string]$EventCalendar = '',
    [string]$BillingStatement = ''
)
$ErrorActionPreference='Stop'
if (-not $StateRoot) {
    $StateRoot=Join-Path $env:USERPROFILE 'Documents\FXForwardEvidence\final_virtual_paper'
}
if (-not (Test-Path -LiteralPath $StateRoot -PathType Container)) {
    throw 'Final paper state absent. NO_GO'
}
if (-not (Test-Path -LiteralPath $Mt4FilesDirectory -PathType Container)) {
    throw 'DEMO MT4 files absent. NO_GO'
}
$mt4=(Resolve-Path -LiteralPath $Mt4FilesDirectory).Path.TrimEnd('\')
if (-not $mt4.EndsWith('\MQL4\Files',[StringComparison]::OrdinalIgnoreCase)) {
    throw 'Expected active DEMO MT4 MQL4\Files directory. NO_GO'
}
try {
    $processes=@(Get-CimInstance Win32_Process -ErrorAction Stop |
        Where-Object {
            $_.Name -in @('python.exe','pythonw.exe','py.exe') -and
            $_.CommandLine -match 'research\.final_paper_runtime'
        })
} catch {
    throw 'Unable to inspect Windows process list. NO_GO'
}
$payload=[ordered]@{
    schema='fx_final_paper_windows_live_process_probe_v1'
    status='WINDOWS_PROCESS_PRESENCE_ONLY_NO_GO'
    paper_supervisor_process_count=$processes.Count
    paper_supervisor_single_process_present=($processes.Count -eq 1)
    mt4_expert_running='NOT_ATTESTED'
    mt4_process_running='NOT_ATTESTED'
    mt4_order_execution_permitted=$false
    new_paid_ai_calls_permitted=$false
    new_virtual_positions_permitted=$false
    runtime_go_no_go='NO_GO'
}
$target=Join-Path $StateRoot ('windows_process_presence_'+(Get-Date -Format 'yyyyMMdd_HHmmss_fff')+'.json')
$payload | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $target -Encoding UTF8 -NoNewline
Write-Host ($payload | ConvertTo-Json -Compress -Depth 4)
if ($processes.Count -ne 1) {
    Write-Host 'No sole live supervisor. Do not start a second process or clear locks.'
}
$report=Join-Path $StateRoot ('five_gate_readiness_'+(Get-Date -Format 'yyyyMMdd_HHmmss_fff')+'.json')
$cmd=@('-m','research.final_paper_five_gate_readiness','--state-root',
       $StateRoot,'--mt4-files',$mt4,'--out',$report)
if ($EventCalendar) {
    if (-not (Test-Path -LiteralPath $EventCalendar -PathType Leaf)) {
        throw 'Event archive missing. NO_GO'
    }
    $cmd+=@('--event-calendar',$EventCalendar)
}
if ($BillingStatement) {
    if (-not (Test-Path -LiteralPath $BillingStatement -PathType Leaf)) {
        throw 'Billing evidence missing. NO_GO'
    }
    $cmd+=@('--billing-statement',$BillingStatement)
}
& python @cmd
if ($LASTEXITCODE -ne 0) {
    throw 'Five-gate offline audit rejected evidence. NO_GO'
}
Write-Host ('Read-only readiness report: '+$report)
Write-Host 'No API, virtual entry, supervisor restart, or broker order authorized.'
