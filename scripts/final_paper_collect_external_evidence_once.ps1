# FINAL-PAPER-127: one command to collect available live/non-live evidence.
# Never stops or starts MT4/Python, never updates a latch, never sends orders.
# External public snapshots and provider costs are separately opted in.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$Mt4FilesDirectory,
    [string]$StateRoot='',
    [switch]$AllowPublicNetwork,
    [switch]$ReadOpenAICosts
)
$ErrorActionPreference='Stop'
if (-not $StateRoot) {
    $StateRoot=Join-Path $env:USERPROFILE 'Documents\FXForwardEvidence\final_virtual_paper'
}
if ($ReadOpenAICosts -and -not $AllowPublicNetwork) {
    throw 'Provider costs requires -AllowPublicNetwork. NO_GO'
}
$mt4=(Resolve-Path -LiteralPath $Mt4FilesDirectory -ErrorAction Stop).Path
if (-not $mt4.TrimEnd('\').EndsWith('\MQL4\Files',[StringComparison]::OrdinalIgnoreCase)) {
    throw 'Existing DEMO MQL4\Files only. NO_GO'
}
Write-Host '1/4 Windows and MT4 process/quote evidence (read only)'
& "$PSScriptRoot\final_paper_local_machine_handoff_once.ps1" -Mt4FilesDirectory $mt4 -StateRoot $StateRoot
# PowerShell script invocation does not reliably set $LASTEXITCODE.
# Reading its previous native-program value here produced a false warning
# despite successful forensic capture. Throwing errors propagate directly.
Write-Host '2/4 Python journal / MT4 producer-consumer diagnosis (read only)'
try {
    & "$PSScriptRoot\final_paper_stream_diagnostic_once.ps1" -Mt4FilesDirectory $mt4 -StateRoot $StateRoot
} catch {
    Write-Warning 'Stream diagnostic incomplete; NO_GO. No restart attempted.'
}
Write-Host '3/4 Combined five-gate readiness (read only)'
try {
    & "$PSScriptRoot\final_paper_live_supervisor_check_once.ps1" -Mt4FilesDirectory $mt4 -StateRoot $StateRoot
} catch {
    Write-Warning 'Five-gate review incomplete; NO_GO. No restart attempted.'
}
if ($AllowPublicNetwork) {
    Write-Host '4/4 Fetch six public official sources (bounded, immutable local copies)'
    $archive=Join-Path $StateRoot ('official_public_capture_'+(Get-Date -Format 'yyyyMMdd_HHmmss_fff'))
    & python -m research.final_paper_public_source_snapshot --allow-network --out-dir $archive
    if ($LASTEXITCODE -ne 0) {
        Write-Warning 'Some public official sources were unavailable. Incomplete evidence stays NO_GO.'
    }
    Write-Host ('Public official archive: '+$archive)
} else {
    Write-Host '4/4 External source downloads skipped (explicit opt-in absent)'
}
if ($ReadOpenAICosts) {
    if (-not $env:OPENAI_ADMIN_KEY) {
        Write-Warning 'OPENAI_ADMIN_KEY not present locally. Provider costs skipped, NO_GO.'
    } else {
        $costOut=Join-Path $StateRoot ('provider_usd_costs_'+(Get-Date -Format 'yyyyMMdd_HHmmss_fff')+'.json')
        & python -m research.final_paper_openai_costs_readonly --allow-network --out $costOut
        if ($LASTEXITCODE -ne 0) {
            Write-Warning 'Read-only provider cost evidence unavailable. NO_GO.'
        } else {
            Write-Host ('Read-only USD provider costs: '+$costOut)
        }
    }
}
Write-Host 'Handoff complete; all gates remain fail closed.'
Write-Host 'No broker order, AI inference, permission renewal, state repair, or latch clear.'
