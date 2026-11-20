# FINAL-PAPER-147: real multi-day three-pair quote stress + six original
# official-source hash audit. Does not touch Python supervisor, MT4, paper
# journal, communication latch or billing; all reports are local new files.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$Mt4FilesDirectory,
    [Parameter(Mandatory=$true)][string]$OfficialArchiveDirectory,
    [string]$StateRoot='',
    [ValidateRange(2,10080)][int]$MaxFiles=10080
)
$ErrorActionPreference='Stop'
if (-not $StateRoot) {
    $StateRoot=Join-Path $env:USERPROFILE 'Documents\FXForwardEvidence\final_virtual_paper'
}
if (-not (Test-Path -LiteralPath $StateRoot -PathType Container)) {
    throw 'Original state root not found. NO_GO'
}
$mt4=(Resolve-Path -LiteralPath $Mt4FilesDirectory -ErrorAction Stop).Path.TrimEnd('\')
if (-not $mt4.EndsWith('\MQL4\Files',[StringComparison]::OrdinalIgnoreCase)) {
    throw 'Expected existing DEMO MT4 MQL4\Files. NO_GO'
}
$archive=(Resolve-Path -LiteralPath $OfficialArchiveDirectory -ErrorAction Stop).Path
if (-not (Split-Path -Leaf $archive).StartsWith('official_public_capture_')) {
    throw 'Expected an original immutable official_public_capture_* folder. NO_GO'
}
$stamp=Get-Date -Format 'yyyyMMdd_HHmmss_fff'
$outMarket=Join-Path $StateRoot ('multiday_stress_'+$stamp+'.json')
$outOriginal=Join-Path $StateRoot ('official_integrity_'+$stamp+'.json')
Write-Host '1/2 Auditing original three-pair MT4 quotes across NY17 days'
& python -m research.final_paper_multiday_quote_stress --mt4-files $mt4 --max-files $MaxFiles --out $outMarket
if ($LASTEXITCODE -ne 0) {
    throw 'Multi-day quote research failed closed. No trading state changed.'
}
Write-Host '2/2 Verifying six saved official original source hashes'
& python -m research.final_paper_official_archive_integrity --archive $archive --out $outOriginal
if ($LASTEXITCODE -ne 0) {
    throw 'Official original hash audit failed closed. Do not trust archive.'
}
Write-Host ('Multi-day quote profile: '+$outMarket)
Write-Host ('Six-original byte integrity: '+$outOriginal)
Write-Host 'Neither report independently attests official event completeness, broker clock or execution cost.'
Write-Host 'Risk latches, paid-AI 6/6 and no-broker-order conditions remain unchanged.'
