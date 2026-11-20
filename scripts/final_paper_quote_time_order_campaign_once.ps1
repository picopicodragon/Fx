# FINAL-PAPER-158: classify all original tick-time inversions read only.
# Existing Python, MT4 EA, journal and risk latches are NEVER changed.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$Mt4FilesDirectory,
    [int]$MaxFiles=10080,
    [string]$StateRoot=''
)
$ErrorActionPreference='Stop'
if (-not $StateRoot) {
    $StateRoot=Join-Path $env:USERPROFILE 'Documents\FXForwardEvidence\final_virtual_paper'
}
if (-not (Test-Path -LiteralPath $StateRoot -PathType Container)) {
    throw 'Existing paper evidence root required. NO_GO'
}
$mt4=(Resolve-Path -LiteralPath $Mt4FilesDirectory -ErrorAction Stop).Path.TrimEnd('\')
if (-not $mt4.EndsWith('\MQL4\Files',[StringComparison]::OrdinalIgnoreCase)) {
    throw 'Actual DEMO MQL4\Files only. NO_GO'
}
if ($MaxFiles -lt 2 -or $MaxFiles -gt 10080) {
    throw 'Only bounded original snapshots 2..10080 permitted. NO_GO'
}
$out=Join-Path $StateRoot ('quote_time_order_campaign_'+
    (Get-Date -Format 'yyyyMMdd_HHmmss_fff')+'.json')
& python -m research.final_paper_quote_time_order_campaign --mt4-files $mt4 --max-files $MaxFiles --out $out
if ($LASTEXITCODE -ne 0) {
    throw 'Read-only time ordering campaign failed closed. Preserve originals.'
}
Write-Host ('Original source clock-ordering report: '+$out)
Write-Host 'All original invalid files remain preserved and not promoted to trading GO.'
Write-Host 'No MT4 restart, EA replacement, journal write, paid API call or broker order.'
