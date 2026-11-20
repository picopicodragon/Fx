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
# Search the probable stop window, but export ONLY event metadata, never
# raw Windows Message, account identifiers, paths, API keys or user secrets.
try {
    $sourceReport=Get-Content -LiteralPath $report -Raw -ErrorAction Stop | ConvertFrom-Json
    $since=[datetimeoffset]::Parse($sourceReport.last_consumed_quote_utc_pc_unattested).LocalDateTime.AddMinutes(-30)
    $until=$since.AddHours(4)
    $system=@()
    $pythonErrors=@()
    $systemQueryOk=$false
    $applicationQueryOk=$false
    try {
        $hits=@(Get-WinEvent -FilterHashtable @{
            LogName='System'; StartTime=$since; EndTime=$until
            Id=@(41,1074,6005,6006,6008)
        } -MaxEvents 100 -ErrorAction Stop)
        $systemQueryOk=$true
        $system=@($hits | Select-Object -First 30 | ForEach-Object {
            [ordered]@{
                time_utc_pc_unattested=$_.TimeCreated.ToUniversalTime().ToString('o')
                id=$_.Id
                provider=$_.ProviderName
            }
        })
    } catch { $systemQueryOk=$false }
    try {
        $app=@(Get-WinEvent -FilterHashtable @{
            LogName='Application'; StartTime=$since; EndTime=$until
            Id=@(1000,1001)
        } -MaxEvents 100 -ErrorAction Stop)
        $applicationQueryOk=$true
        $pythonErrors=@($app | Where-Object {
            $_.Message -match '(?i)python(w)?\.exe'
        } | Select-Object -First 30 | ForEach-Object {
            [ordered]@{
                time_utc_pc_unattested=$_.TimeCreated.ToUniversalTime().ToString('o')
                id=$_.Id
                provider=$_.ProviderName
            }
        })
    } catch { $applicationQueryOk=$false }
    $events=[ordered]@{
        schema='fx_final_paper_windows_exit_event_hints_v1'
        status='WINDOWS_EVENT_HINTS_NOT_PROOF_OF_ROOT_CAUSE_NO_GO'
        incident_last_quote_utc_pc_unattested=$sourceReport.last_consumed_quote_utc_pc_unattested
        system_query_succeeded=$systemQueryOk
        application_query_succeeded=$applicationQueryOk
        system_restart_event_hints=$system
        python_application_error_event_hints=$pythonErrors
        event_messages_redacted=$true
        independent_root_cause_proven=$false
        supervisor_restarted=$false
        lock_file_modified=$false
        communication_latch_cleared=$false
        paid_ai_calls_permitted=$false
        new_virtual_entries_permitted=$false
        broker_orders_permitted=$false
        runtime_go_no_go='NO_GO'
    }
    $hintPath=Join-Path $StateRoot ('windows_exit_event_hints_'+
        (Get-Date -Format 'yyyyMMdd_HHmmss_fff')+'.json')
    $events | ConvertTo-Json -Depth 7 |
        Set-Content -LiteralPath $hintPath -Encoding UTF8 -NoNewline
    Write-Host ('WINDOWS_EXIT_EVENT_HINTS='+$hintPath)
    Write-Host ('SYSTEM_RESTART_EVENT_HINT_COUNT='+$system.Count)
    Write-Host ('PYTHON_APPLICATION_ERROR_HINT_COUNT='+$pythonErrors.Count)
} catch {
    Write-Warning 'Windows event hints could not be captured; cause remains unproven.'
}
Write-Host 'No restart, risk latch release, paid AI call, virtual entry or broker order executed.'
