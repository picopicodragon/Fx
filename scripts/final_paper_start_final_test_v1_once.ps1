# FINAL-TEST-V1: one command to certify existing no-order DEMO observation.
# NO new process launch, EA hot swap, paid AI, latch change, journal write, order.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$Mt4FilesDirectory,
    [string]$OfficialArchiveDirectory='',
    [string]$StateRoot=''
)
$ErrorActionPreference='Stop'
if (-not $StateRoot) {
    $StateRoot=Join-Path $env:USERPROFILE 'Documents\FXForwardEvidence\final_virtual_paper'
}
if (-not $OfficialArchiveDirectory) {
    $OfficialArchiveDirectory=Join-Path $StateRoot 'official_public_capture_20261120_113041_303'
}
if (-not (Test-Path -LiteralPath $StateRoot -PathType Container)) {
    throw 'Existing paper root unavailable. DO NOT start another monitor.'
}
$mt4=(Resolve-Path -LiteralPath $Mt4FilesDirectory -ErrorAction Stop).Path.TrimEnd('\')
if (-not $mt4.EndsWith('\MQL4\Files',[StringComparison]::OrdinalIgnoreCase)) {
    throw 'Expected actual DEMO MT4 MQL4\Files. NO_GO'
}
$official=(Resolve-Path -LiteralPath $OfficialArchiveDirectory -ErrorAction Stop).Path
if (-not (Split-Path -Leaf $official).StartsWith('official_public_capture_')) {
    throw 'Expected saved immutable six-original archive. NO_GO'
}
function Invoke-ReadOnlySnapshot {
    $before=@(Get-ChildItem -LiteralPath $StateRoot -File -Filter 'local_machine_handoff_*.json' | ForEach-Object {$_.Name})
    & "$PSScriptRoot\final_paper_local_machine_handoff_once.ps1" -Mt4FilesDirectory $mt4 -StateRoot $StateRoot
    $after=@(Get-ChildItem -LiteralPath $StateRoot -File -Filter 'local_machine_handoff_*.json' | Where-Object { $_.Name -notin $before })
    if ($after.Count -ne 1) {
        throw 'Unable to identify one local read-only snapshot. NO_GO'
    }
    return $after[0].FullName
}
Write-Host 'FINAL TEST V1 NO-ORDER: checking existing live DEMO observer and Python.'
Write-Host '1/3 First read-only snapshot. No monitor launch.'
$first=Invoke-ReadOnlySnapshot
Start-Sleep -Seconds 75
Write-Host '2/3 Second read-only snapshot: verifying quote/journal progression.'
$second=Invoke-ReadOnlySnapshot
Write-Host '3/3 Official archive, AI 6/6, journal and synthetic OFFLINE risk checks.'
$out=Join-Path $StateRoot ('final_test_v1_operation_'+(Get-Date -Format 'yyyyMMdd_HHmmss_fff')+'.json')
& python -m research.final_paper_final_test_operation --state-root $StateRoot --mt4-files $mt4 --first $first --second $second --official-archive $official --out $out
if ($LASTEXITCODE -ne 0) {
    throw 'FINAL TEST observer assessment NO_GO. No state was changed.'
}
Write-Host ('Final test V1 NO-ORDER observation report: '+$out)
Write-Host 'Observation and in-memory synthetic mechanics only; approved AI virtual entries remain NO_GO.'
Write-Host 'No MT4 orders, paid inference, monitor restart, communication clearance or journal edit.'
