# One complete no-order acceptance run before fully autonomous PAPER launch.
# Running Python / MT4 never stopped or restarted. V2 is source ONLY.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$Mt4FilesDirectory,
    [string]$StateRoot='',
    [string]$OfficialArchiveDirectory='',
    [string]$BaselineReport=''
)
$ErrorActionPreference='Stop'
if (-not $StateRoot) {
    $StateRoot=Join-Path $env:USERPROFILE 'Documents\FXForwardEvidence\final_virtual_paper'
}
if (-not $OfficialArchiveDirectory) {
    $OfficialArchiveDirectory=Join-Path $StateRoot 'official_public_capture_20261120_113041_303'
}
if (-not $BaselineReport) {
    $BaselineReport=Join-Path $StateRoot 'quote_time_order_campaign_20261120_140145_466.json'
}
if (-not (Test-Path -LiteralPath $StateRoot -PathType Container)) {
    throw 'Historical paper evidence root required. No action.'
}
$mt4=(Resolve-Path -LiteralPath $Mt4FilesDirectory -ErrorAction Stop).Path.TrimEnd('\')
if (-not $mt4.EndsWith('\MQL4\Files',[StringComparison]::OrdinalIgnoreCase)) {
    throw 'Actual DEMO MT4 MQL4\Files required. No action.'
}
$archive=(Resolve-Path -LiteralPath $OfficialArchiveDirectory -ErrorAction Stop).Path
$baseline=(Resolve-Path -LiteralPath $BaselineReport -ErrorAction Stop).Path
$candidate=Join-Path (Split-Path -Parent $PSScriptRoot) 'mt4\read_only\FxFinalPaperReadOnlyObserver.mq4'
if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) {
    throw 'V2 EA candidate source missing. No action.'
}
function New-SafetySample {
    $before=@(Get-ChildItem -LiteralPath $StateRoot -File -Filter 'local_machine_handoff_*.json' | ForEach-Object {$_.Name})
    # The child writes its own JSON report and finishes with Write-Host.
    # It also intentionally probes w32tm.exe, which can leave a NONZERO
    # $LASTEXITCODE when the Windows time service is unavailable. That
    # diagnostic is NOT the child's exit status. Never use inherited
    # $LASTEXITCODE as proof that this PowerShell script failed/succeeded.
    & "$PSScriptRoot\final_paper_local_machine_handoff_once.ps1" -Mt4FilesDirectory $mt4 -StateRoot $StateRoot
    $added=@(Get-ChildItem -LiteralPath $StateRoot -File -Filter 'local_machine_handoff_*.json' |
        Where-Object { $_.Name -notin $before })
    if ($added.Count -ne 1) {
        throw 'Expected precisely one new read-only snapshot. NO_GO'
    }
    # A new file alone is not sufficient: explicitly validate the emitted
    # handoff schema, intended NO_GO status, process counts and booleans.
    $proof=Get-Content -LiteralPath $added[0].FullName -Raw -ErrorAction Stop |
        ConvertFrom-Json -ErrorAction Stop
    if ($proof.schema -cne 'fx_final_paper_local_machine_handoff_v1' -or
        $proof.status -cne 'READ_ONLY_LOCAL_EVIDENCE_NOT_LIVE_TRADE_APPROVAL' -or
        $proof.runtime_go_no_go -cne 'NO_GO' -or
        $proof.paper_supervisor_process_count -ne 1 -or
        $proof.mt4_terminal_process_count -ne 1 -or
        $proof.runtime_lock_present_not_process_proof -ne $true -or
        $proof.new_paid_ai_calls_authorized -ne $false -or
        $proof.new_virtual_positions_permitted -ne $false -or
        $proof.demo_orders_permitted -ne $false -or
        $proof.real_orders_permitted -ne $false) {
        throw 'New snapshot reported an invalid process or safety state. NO_GO'
    }
    return $added[0].FullName
}
Write-Host 'Final AI virtual PAPER acceptance: first READ-ONLY snapshot'
$first=New-SafetySample
Start-Sleep -Seconds 75
Write-Host 'Final AI virtual PAPER acceptance: second READ-ONLY snapshot'
$second=New-SafetySample
$out=Join-Path $StateRoot ('final_go_live_acceptance_'+(Get-Date -Format 'yyyyMMdd_HHmmss_fff')+'.json')
Write-Host 'Verifying 3020 historical raw files, 6 official originals, AI ledger, current supervisor and V2 source.'
& python -m research.final_paper_go_live_acceptance --state-root $StateRoot --mt4-files $mt4 --official-archive $archive --baseline-report $baseline --candidate-mq4 $candidate --first-snapshot $first --second-snapshot $second --out $out
if ($LASTEXITCODE -ne 0) {
    throw 'Full acceptance failed closed. Never modify an original, process, or latch.'
}
Write-Host ('Verified research-only go-live evidence: '+$out)
Write-Host 'External evidence and explicit operator approvals remain outstanding.'
Write-Host 'No billable AI requests, virtual entries, or broker orders.'
