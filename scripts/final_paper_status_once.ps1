# FINAL-PAPER-12: local virtual-portfolio health and no-order evidence.
[CmdletBinding()]
param([string]$StateRoot = '')
$ErrorActionPreference='Stop'
if (-not $StateRoot) {
    $StateRoot=Join-Path $env:USERPROFILE 'Documents\FXForwardEvidence\final_virtual_paper'
}
if (-not (Test-Path -LiteralPath $StateRoot -PathType Container)) {
    throw 'Virtual-paper state not initialized. Start read-only observer and paper supervisor.'
}
$out=Join-Path $StateRoot ('status_'+(Get-Date -Format 'yyyyMMdd_HHmmss_fff')+'.json')
& python -m research.final_paper_status --state-root $StateRoot --out $out
if ($LASTEXITCODE -ne 0) {
    throw 'Virtual paper evidence audit failed. NO_GO; no broker actions.'
}
Write-Host ('Virtual-only status saved: '+$out)
