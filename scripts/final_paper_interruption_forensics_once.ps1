# FINAL-PAPER-44: audit latest journal gap and limited local Windows event IDs.
# Read-only input. Never prints event messages, command lines or account IDs.
# The report is only a time correlation, never proof of process exit reason.
[CmdletBinding()]
param([string]$StateRoot = '')
$ErrorActionPreference = 'Stop'
if (-not $StateRoot) {
    $StateRoot = Join-Path $env:USERPROFILE 'Documents\FXForwardEvidence\final_virtual_paper'
}
if (-not (Test-Path -LiteralPath $StateRoot -PathType Container)) {
    throw 'Paper journal directory is unavailable; NO_GO'
}
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss_fff'
$report = Join-Path $StateRoot ('interruption_timeline_' + $stamp + '.json')
& python -m research.final_paper_interruption_forensics --state-root $StateRoot --out $report
if ($LASTEXITCODE -ne 0) {
    throw 'Journal-based forensic check failed. Do not clear any lock or latch.'
}
$timeline = Get-Content -LiteralPath $report -Raw -Encoding UTF8 | ConvertFrom-Json
$gap = $timeline.latest_level2_gap_in_scanned_window
if ($null -eq $gap) {
    Write-Host 'No >600-second gap in scanned journal window. No Windows event correlation performed.'
    return
}
$from = [DateTimeOffset]::FromUnixTimeSeconds([long]$gap.previous_quote_epoch_pc_unattested).ToLocalTime().AddMinutes(-10).DateTime
$to = [DateTimeOffset]::FromUnixTimeSeconds([long]$gap.first_quote_after_gap_epoch_pc_unattested).ToLocalTime().AddMinutes(10).DateTime
$windows = @()
foreach ($spec in @(
    @{Log='System'; Id=@(41,1074,6005,6006,6008)},
    @{Log='Application'; Id=@(1000,1001)}
)) {
    try {
        $hits = @(Get-WinEvent -FilterHashtable @{
            LogName=$spec.Log
            Id=$spec.Id
            StartTime=$from
            EndTime=$to
        } -MaxEvents 80 -ErrorAction Stop)
        $windows += [pscustomobject]@{
            log_name=$spec.Log
            query_status='QUERY_COMPLETED_NO_CAUSE_INFERENCE'
            event_ids_only=@($hits | ForEach-Object { [int]$_.Id })
            event_times_local=@($hits | ForEach-Object { $_.TimeCreated.ToString('o') })
            records_truncated_at_80=($hits.Count -eq 80)
        }
    } catch {
        $windows += [pscustomobject]@{
            log_name=$spec.Log
            query_status='NO_MATCH_OR_NOT_ACCESSIBLE'
            event_ids_only=@()
            event_times_local=@()
            records_truncated_at_80=$false
        }
    }
}
$bundle=[ordered]@{
    schema='fx_final_paper_windows_event_correlation_v1'
    status='LOCAL_WINDOWS_EVENT_CORRELATION_RESEARCH_ONLY_NO_GO'
    gap_previous_cycle=$gap.previous_cycle
    gap_first_cycle_after=$gap.first_cycle_after_gap
    gap_duration_seconds_pc_derived=$gap.observation_gap_seconds_pc_derived
    local_query_start=$from.ToString('o')
    local_query_end=$to.ToString('o')
    system_and_application_event_id_metadata=$windows
    event_text_and_process_command_lines_saved=$false
    exact_root_cause_proved=$false
    exit_reason_still_unknown=$true
    no_risk_latch_changed=$true
    new_paid_calls_allowed=$false
    broker_orders_permitted=$false
    runtime_go_no_go='NO_GO'
}
$eventFile=Join-Path $StateRoot ('interruption_windows_events_' + $stamp + '.json')
$utf8 = [System.Text.UTF8Encoding]::new($false)
$body = ConvertTo-Json -InputObject $bundle -Depth 8
$stream = [System.IO.File]::Open($eventFile,[System.IO.FileMode]::CreateNew,[System.IO.FileAccess]::Write,[System.IO.FileShare]::None)
try {
    $writer = New-Object System.IO.StreamWriter($stream,$utf8)
    try { $writer.Write($body); $writer.Flush() }
    finally { $writer.Dispose() }
} finally { $stream.Dispose() }
Write-Host 'Journal timeline: ' $report
Write-Host 'Sanitized Windows event IDs: ' $eventFile
Write-Host 'This is NOT evidence that a specific event caused Python to stop.'
