# FINAL-PAPER: no-order source-linked offline E2E replay.
# Preserve the existing supervisor and the complete 6/6 AI ledger.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$Mt4FilesDirectory,
    [Parameter(Mandatory=$true)][string]$H1Snapshot,
    [Parameter(Mandatory=$true)][string]$Pair,
    [Parameter(Mandatory=$true)][string[]]$NewsBundle,
    [string]$EventBlackoutFile = '',
    [string]$StateRoot = ''
)
$ErrorActionPreference = 'Stop'
if (-not $StateRoot) {
    $StateRoot = Join-Path $env:USERPROFILE 'Documents\FXForwardEvidence\final_virtual_paper'
}
$mt4 = (Resolve-Path -LiteralPath $Mt4FilesDirectory -ErrorAction Stop).Path
$h1 = (Resolve-Path -LiteralPath $H1Snapshot -ErrorAction Stop).Path
if (-not $mt4.EndsWith('\MQL4\Files',[StringComparison]::OrdinalIgnoreCase)) {
    throw 'DEMO MT4 MQL4\Files path required. NO_GO'
}
if ($Pair -notin @('USD/JPY','EUR/JPY','EUR/USD')) {
    throw 'One of the three official FX pairs is required.'
}
if (@($NewsBundle).Count -lt 1 -or @($NewsBundle).Count -gt 5) {
    throw 'Original one to five archived official news bundles required.'
}
$out = Join-Path $StateRoot ('source_linked_e2e_'+
    (Get-Date -Format 'yyyyMMdd_HHmmss_fff')+'.json')
$argsList = @('-m','research.final_paper_e2e_replay',
    '--state-root',$StateRoot,'--mt4-files',$mt4,
    '--h1-snapshot',$h1,'--pair',$Pair,'--out',$out)
foreach ($bundle in $NewsBundle) {
    $resolved = (Resolve-Path -LiteralPath $bundle -ErrorAction Stop).Path
    $argsList += @('--news-bundle',$resolved)
}
if ($EventBlackoutFile) {
    $eventPath=(Resolve-Path -LiteralPath $EventBlackoutFile -ErrorAction Stop).Path
    $argsList+=@('--event-blackout-file',$eventPath)
}
& python @argsList
if ($LASTEXITCODE -ne 0) {
    throw 'Source-linked historical replay denied. Journal/lock must remain unchanged.'
}
Write-Host ('Offline hypothetical replay report: '+$out)
Write-Host 'No new paid AI, broker order, or live virtual permission was created.'
