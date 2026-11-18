# DEMO-SPRINT-63: offline, read-only broker cash/lot/quote audit.
# Contains local DEMO account number in source CSV. NEVER paste raw CSV.
# No MT4 order, no API inference, no network, no trading permission.
[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$Mt4FilesDirectory)
$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $Mt4FilesDirectory -PathType Container)) {
    throw 'MT4 MQL4\Files folder missing. NO_GO'
}
$dir = (Resolve-Path -LiteralPath $Mt4FilesDirectory).Path.TrimEnd('\')
if (-not $dir.EndsWith('\MQL4\Files',
        [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Expected the exact local MT4 MQL4\Files folder. NO_GO'
}
$snapshots = @(Get-ChildItem -LiteralPath $dir -File -Filter 'FxDemoBrokerSafety_*.csv')
if ($snapshots.Count -eq 0) {
    throw 'No broker terms CSV. Run FxFinalDemoBrokerSafetyProbe on USDJPY H1.'
}
$latest = $snapshots | Sort-Object LastWriteTimeUtc -Descending |
    Select-Object -First 1
if ($latest.BaseName -notmatch '^FxDemoBrokerSafety_[0-9]{8}_[0-9]{6}$') {
    throw 'Unexpected broker CSV filename. NO_GO'
}
$root = Join-Path $env:USERPROFILE 'Documents\FXForwardEvidence'
if (-not (Test-Path -LiteralPath $root -PathType Container)) {
    throw 'Evidence folder missing. NO_GO'
}
$copyDir = Join-Path $root ('broker_terms_' +
    (Get-Date -Format 'yyyyMMdd_HHmmss_fff'))
New-Item -ItemType Directory -Path $copyDir -ErrorAction Stop | Out-Null
$copy = Join-Path $copyDir $latest.Name
Copy-Item -LiteralPath $latest.FullName -Destination $copy -ErrorAction Stop
$report = Join-Path $copyDir 'redacted_broker_terms_audit.json'
& python -m research.final_demo_broker_contract_audit --snapshot $copy --out $report
if ($LASTEXITCODE -ne 0) {
    throw 'Broker terms audit failed closed. No orders. Do not enable demo EA.'
}
Write-Host 'Broker-reported DEMO terms recorded (research HOLD only).'
Write-Host ('Redacted audit report: ' + $report)
Write-Host 'Do not share the original MT4 CSV because it includes the demo account number.'
