# FINAL-PAPER-88: free, read-only MT4 DEMO quote/contract evidence sampling.
# Never changes live supervisor, risk latch, quote CSV or AI call cap.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$Mt4FilesDirectory,
    [string]$StateRoot = ''
)
$ErrorActionPreference='Stop'
if (-not $StateRoot) {
    $StateRoot=Join-Path $env:USERPROFILE 'Documents\FXForwardEvidence\final_virtual_paper'
}
if (-not (Test-Path -LiteralPath $StateRoot -PathType Container)) {
    throw 'Paper evidence directory missing; NO_GO'
}
if (-not (Test-Path -LiteralPath $Mt4FilesDirectory -PathType Container)) {
    throw 'MT4 Files directory missing; NO_GO'
}
$mt4=(Resolve-Path -LiteralPath $Mt4FilesDirectory).Path.TrimEnd('\')
if (-not $mt4.EndsWith('\MQL4\Files',[StringComparison]::OrdinalIgnoreCase)) {
    throw 'Expected DEMO MQL4\Files folder; NO_GO'
}
$report=Join-Path $StateRoot ('mt4_quote_contract_audit_' +
    (Get-Date -Format 'yyyyMMdd_HHmmss_fff') + '.json')
& python -m research.final_paper_quote_contract_evidence --mt4-files $mt4 --out $report
if ($LASTEXITCODE -ne 0) {
    throw 'MT4 quote/contract sampling failed closed. No safe-release claim.'
}
Write-Host ('Read-only DEMO MT4 quote/contract report: ' + $report)
Write-Host 'Observed spread is NOT independently verified total transaction cost.'
