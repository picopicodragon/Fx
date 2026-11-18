# FINAL-PAPER-10: operator starts local continuous VIRTUAL-only monitoring.
# FX MT4 observer itself must be separately compiled/attached in the DEMO terminal.
# AutoTrading OFF is required; never submit or modify broker orders.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$Mt4FilesDirectory,
    [string[]]$NewsBundle = @(),
    [switch]$Once,
    [switch]$AllowPaidAi,
    [int]$MaxPaidCallsLifetime = 0,
    [string]$AnalystModel = '',
    [string]$ReviewerModel = '',
    [string]$StateRoot = ''
)
$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $Mt4FilesDirectory -PathType Container)) {
    throw 'MT4 DEMO MQL4\Files folder missing. NO_GO'
}
$mt4 = (Resolve-Path -LiteralPath $Mt4FilesDirectory).Path.TrimEnd('\')
if (-not $mt4.EndsWith('\MQL4\Files',
        [System.StringComparison]::OrdinalIgnoreCase)) {
    throw 'Selected folder is not the current MT4 MQL4\Files. NO_GO'
}
if ($AllowPaidAi) {
    if ($MaxPaidCallsLifetime -lt 2 -or $MaxPaidCallsLifetime -gt 6 -or
        $MaxPaidCallsLifetime % 2 -ne 0 -or
        [string]::IsNullOrWhiteSpace($env:OPENAI_API_KEY) -or
        [string]::IsNullOrWhiteSpace($AnalystModel) -or
        [string]::IsNullOrWhiteSpace($ReviewerModel) -or
        $AnalystModel -eq $ReviewerModel -or @($NewsBundle).Count -eq 0) {
        throw 'For explicit paid AI, supply 2 models, official news, key, and a 2/4/6-call maximum. NO_GO'
    }
} elseif ($MaxPaidCallsLifetime -ne 0 -or $AnalystModel -or $ReviewerModel) {
    throw 'AI model or budget flags cannot be given without -AllowPaidAi. NO_GO'
}
foreach ($bundle in $NewsBundle) {
    if (-not (Test-Path -LiteralPath $bundle -PathType Container)) {
        throw 'Archived official news bundle missing. NO_GO'
    }
}
if (-not $StateRoot) {
    $StateRoot = Join-Path $env:USERPROFILE 'Documents\FXForwardEvidence\final_virtual_paper'
}
$parent = Split-Path -Parent $StateRoot
if (-not (Test-Path -LiteralPath $parent -PathType Container)) {
    throw 'Expected FXForwardEvidence parent folder missing. NO_GO'
}
Write-Host 'LOCAL VIRTUAL FX ONLY: starting capital JPY 100,000.'
Write-Host 'No MT4 broker orders, no Jev and no real account access.'
Write-Host 'AutoTrading must remain OFF. Ctrl+C stops this local supervisor.'
$cmd = @('-m','research.final_paper_runtime',
    '--mt4-files',$mt4,'--state-root',$StateRoot,
    '--interval-seconds','15')
foreach ($bundle in $NewsBundle) {
    $cmd += @('--news-bundle',$bundle)
}
if ($AllowPaidAi) {
    $cmd += @('--allow-paid-ai',
        '--max-paid-calls-lifetime',"$MaxPaidCallsLifetime",
        '--analyst-model',$AnalystModel,
        '--reviewer-model',$ReviewerModel)
}
if (-not $Once) { $cmd += '--watch' }
& python @cmd
if ($LASTEXITCODE -ne 0) {
    throw 'Virtual paper supervisor halted fail-closed. Review evidence and lock before any restart.'
}
Write-Host 'Virtual paper supervisor ended; no MT4 order was submitted.'
