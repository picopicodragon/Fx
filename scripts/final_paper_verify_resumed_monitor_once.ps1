# FINAL-PAPER-138: read-only post-restart two-point observation check.
# Checks 75 seconds apart. No Python process start/stop or latch clearing.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$Mt4FilesDirectory,
    [string]$StateRoot=''
)
$ErrorActionPreference='Stop'
if (-not $StateRoot) {
    $StateRoot=Join-Path $env:USERPROFILE 'Documents\FXForwardEvidence\final_virtual_paper'
}
if (-not (Test-Path -LiteralPath $StateRoot -PathType Container)) {
    throw 'Paper state root unavailable. NO_GO'
}
$mt4=(Resolve-Path -LiteralPath $Mt4FilesDirectory -ErrorAction Stop).Path.TrimEnd('\')
if (-not $mt4.EndsWith('\MQL4\Files',[StringComparison]::OrdinalIgnoreCase)) {
    throw 'Existing DEMO MQL4\Files required. NO_GO'
}
function New-ReadOnlySnapshot {
    $before=@(Get-ChildItem -LiteralPath $StateRoot -File -Filter 'local_machine_handoff_*.json' | ForEach-Object {$_.Name})
    & "$PSScriptRoot\final_paper_local_machine_handoff_once.ps1" -Mt4FilesDirectory $mt4 -StateRoot $StateRoot
    $after=@(Get-ChildItem -LiteralPath $StateRoot -File -Filter 'local_machine_handoff_*.json' | Where-Object { $_.Name -notin $before })
    if ($after.Count -ne 1) {
        throw 'Unexpected count of local handoff snapshots. NO_GO'
    }
    return $after[0].FullName
}
Write-Host 'Read-only checkpoint 1/2; leave MT4/Python running.'
$first=New-ReadOnlySnapshot
Start-Sleep -Seconds 75
Write-Host 'Read-only checkpoint 2/2; checking uninterrupted observation.'
$second=New-ReadOnlySnapshot
$out=Join-Path $StateRoot ('resumed_continuity_'+(Get-Date -Format 'yyyyMMdd_HHmmss_fff')+'.json')
& python -m research.final_paper_resumed_continuity --state-root $StateRoot --first $first --second $second --out $out
if ($LASTEXITCODE -ne 0) {
    throw 'Restart continuity not verified. NO_GO, do not clear any latch.'
}
Write-Host ('Two-snapshot observer proof: '+$out)
Write-Host 'Continuous quotation evidence is NOT permission for entry or paid AI.'
Write-Host 'Current communication latch and all risk stop approvals remain unchanged.'
