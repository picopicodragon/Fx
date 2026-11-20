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
$marketExit = $LASTEXITCODE
if ($marketExit -ne 0) {
    Write-Warning 'Original quote scan stopped safely. Inspect diagnostic_reason_code and source_file_basename above.'
}
# The two proof sets are independent. Audit the originals even if a
# historical quote is invalid; never declare an overall pass in that case.
Write-Host '2/2 Verifying six saved official original source hashes'
& python -m research.final_paper_official_archive_integrity --archive $archive --out $outOriginal
$archiveExit = $LASTEXITCODE
if ($archiveExit -ne 0) {
    Write-Warning 'Official original hash audit stopped safely. Archive is not verified.'
}
if ($marketExit -eq 0) {
    Write-Host ('Multi-day quote profile: '+$outMarket)
}
if ($archiveExit -eq 0) {
    Write-Host ('Six-original byte integrity: '+$outOriginal)
}
Write-Host 'Neither report independently attests official event completeness, broker clock or execution cost.'
Write-Host 'Risk latches, paid-AI 6/6 and no-broker-order conditions remain unchanged.'
if ($marketExit -ne 0 -or $archiveExit -ne 0) {
    throw 'One or both independent evidence checks remain NO_GO. Do not remove any quote evidence.'
}
