# FINAL-PAPER-49: metadata-only WER investigation around Application 1001.
# Read-only event query. NEVER save Event.Message, full EventData, XML,
# process command line, filenames, account IDs, API keys, or crash dumps.
# Provides correlations only; never clears virtual communication/risk latches.
[CmdletBinding()]
param(
    [string]$StateRoot = '',
    [datetime]$StartLocal = [datetime]'2026-11-18T13:30:00',
    [datetime]$EndLocal = [datetime]'2026-11-18T13:45:00'
)
$ErrorActionPreference = 'Stop'
if (-not $StateRoot) {
    $StateRoot = Join-Path $env:USERPROFILE 'Documents\FXForwardEvidence\final_virtual_paper'
}
if (-not (Test-Path -LiteralPath $StateRoot -PathType Container)) {
    throw 'Existing paper evidence directory missing. No writes to journal. NO_GO'
}
if ($EndLocal -le $StartLocal -or ($EndLocal-$StartLocal).TotalHours -gt 2) {
    throw 'Invalid event time scope; NO_GO'
}
$events = @()
$queryStatus = 'NOT_QUERIED'
try {
    $events = @(Get-WinEvent -FilterHashtable @{
        LogName = 'Application'
        Id = @(1000,1001,1002)
        StartTime = $StartLocal
        EndTime = $EndLocal
    } -MaxEvents 60 -ErrorAction Stop)
    $queryStatus = 'QUERY_COMPLETED'
} catch {
    # Get-WinEvent also throws if no records are returned.
    # Do not conflate no records with access denied or query failure.
    $queryStatus = 'NO_MATCH_OR_QUERY_UNAVAILABLE'
}
$sanitized = @()
foreach ($event in $events) {
    $provider = 'OTHER_OR_UNRECOGNIZED_PROVIDER'
    if ($event.ProviderName -eq 'Windows Error Reporting') {
        $provider = 'WINDOWS_ERROR_REPORTING'
    } elseif ($event.ProviderName -eq 'Application Error') {
        $provider = 'APPLICATION_ERROR'
    } elseif ($event.ProviderName -eq 'Application Hang') {
        $provider = 'APPLICATION_HANG'
    }
    $family = 'UNKNOWN_OR_OTHER'
    $problemType = 'UNCLASSIFIED'
    $xmlValid = $false
    try {
        [xml]$document = $event.ToXml()
        $xmlValid = $true
        $fields = @($document.Event.EventData.Data)
        foreach ($field in $fields) {
            if ($null -eq $field) { continue }
            $fieldName = [string]$field.GetAttribute('Name')
            # Only the canonical app-name-related structured fields are read.
            # Never inspect full Message or other EventData payloads.
            if ($fieldName -in @('P1','AppName','param1','FaultingApplicationName')) {
                $candidate = [string]$field.InnerText
                if ($candidate -match '(?i)(^|[\\/])pythonw?\.exe$') {
                    $family = 'PYTHON'
                } elseif ($candidate -match '(?i)(^|[\\/])(powershell|pwsh)\.exe$') {
                    $family = 'POWERSHELL'
                } elseif ($candidate -match '(?i)(^|[\\/])(windowsterminal|wt)\.exe$') {
                    $family = 'WINDOWS_TERMINAL'
                } elseif ($candidate -match '(?i)(^|[\\/])terminal(64)?\.exe$') {
                    $family = 'MT4_TERMINAL_POSSIBLE'
                }
            }
            if ($fieldName -in @('EventName','ProblemEventName')) {
                $candidate = [string]$field.InnerText
                if ($candidate -in @('APPCRASH','APPHANG','APPHANGB1',
                                     'BEX','BEX64','CLR20R3','LiveKernelEvent')) {
                    $problemType = $candidate.ToUpperInvariant()
                }
            }
        }
    } catch {
        $xmlValid = $false
        $family = 'UNKNOWN_OR_OTHER'
        $problemType = 'UNCLASSIFIED'
    }
    $sanitized += [pscustomobject]@{
        event_id = [int]$event.Id
        event_time_local = $event.TimeCreated.ToString('o')
        provider_category = $provider
        app_family_from_structured_event_fields_only = $family
        safe_problem_type = $problemType
        event_data_xml_parsed = $xmlValid
        event_message_examined = $false
        specific_python_exit_proven = $false
    }
}
$result = [ordered]@{
    schema = 'fx_final_paper_windows_wer_1001_metadata_v1'
    status = 'WER_METADATA_INSPECTION_ONLY_NO_GO'
    query_start_local = $StartLocal.ToString('o')
    query_end_local = $EndLocal.ToString('o')
    query_status = $queryStatus
    limited_to_latest_60_events = $true
    results = @($sanitized)
    event_messages_or_raw_xml_saved = $false
    command_lines_or_full_paths_saved = $false
    windows_1001_causally_explains_quote_gap = $false
    python_supervisor_exit_proven = $false
    root_cause_explained = $false
    existing_journal_or_risk_latch_modified = $false
    communication_latch_cleared = $false
    new_virtual_entries_permitted = $false
    new_paid_ai_calls_permitted = $false
    broker_orders_permitted = $false
    real_orders_permitted = $false
    runtime_go_no_go = 'NO_GO'
}
$out = Join-Path $StateRoot ('wer_1001_metadata_' +
    (Get-Date -Format 'yyyyMMdd_HHmmss_fff') + '.json')
$utf8 = [System.Text.UTF8Encoding]::new($false)
$body = ConvertTo-Json -InputObject $result -Depth 7
$stream = [System.IO.File]::Open($out,[System.IO.FileMode]::CreateNew,
    [System.IO.FileAccess]::Write,[System.IO.FileShare]::None)
try {
    $writer = [System.IO.StreamWriter]::new($stream,$utf8)
    try { $writer.Write($body); $writer.Flush() }
    finally { $writer.Dispose() }
} finally { $stream.Dispose() }
Write-Output $body
Write-Host ('No-release WER metadata saved: ' + $out)
