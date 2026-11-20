# Compile V2 READ-ONLY MQ4 into a NEW isolated Windows folder.
# DOES NOT install EX4, touch MQL4\Experts, change charts or stop terminal.
# Operator must explicitly invoke with -ApproveIsolatedCompile.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$MetaEditorExe,
    [Parameter(Mandatory=$true)][switch]$ApproveIsolatedCompile,
    [string]$StateRoot=''
)
$ErrorActionPreference='Stop'
if (-not $ApproveIsolatedCompile.IsPresent) {
    throw 'This isolated MetaEditor compilation requires explicit operator opt-in.'
}
if (-not $StateRoot) {
    $StateRoot=Join-Path $env:USERPROFILE 'Documents\FXForwardEvidence\final_virtual_paper'
}
if (-not (Test-Path -LiteralPath $StateRoot -PathType Container)) {
    throw 'Existing paper evidence root missing.'
}
$exe=(Resolve-Path -LiteralPath $MetaEditorExe -ErrorAction Stop).Path
if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) {
    throw 'MetaEditor executable not found.'
}
if ((Split-Path -Leaf $exe) -notmatch '^metaeditor(64)?\.exe$') {
    throw 'Only actual MetaEditor executable permitted.'
}
$source=Join-Path (Split-Path -Parent $PSScriptRoot) 'mt4\read_only\FxFinalPaperReadOnlyObserver.mq4'
if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
    throw 'Read-only V2 source absent. NO_GO.'
}
$read=Get-Content -LiteralPath $source -Raw
if ($read -notmatch 'FXPAPER-CLOCKFREEZE-20261120-V2') {
    throw 'Expected V2 build tag missing. NO_GO.'
}
foreach ($unsafe in @('OrderSend(', 'OrderModify(', 'OrderClose(', 'WebRequest(', '#import')) {
    if ($read.Contains($unsafe)) { throw 'Disallowed trading/network instruction. NO_GO.' }
}
$dir=Join-Path $StateRoot ('metaeditor_v2_candidate_'+(Get-Date -Format 'yyyyMMdd_HHmmss_fff'))
if (Test-Path -LiteralPath $dir) { throw 'Compile evidence directory already exists. NO_GO.' }
New-Item -ItemType Directory -Path $dir -ErrorAction Stop | Out-Null
$mq4=Join-Path $dir 'FxFinalPaperReadOnlyObserver.mq4'
Copy-Item -LiteralPath $source -Destination $mq4 -ErrorAction Stop
$before=(Get-FileHash -LiteralPath $mq4 -Algorithm SHA256).Hash
Write-Host 'Compiling ONE isolated V2 source only. Live terminal remains unchanged.'
$arg=('/compile:"'+$mq4+'" /log')
$proc=Start-Process -FilePath $exe -ArgumentList $arg -Wait -PassThru
if ($proc.ExitCode -ne 0) { throw 'MetaEditor process returned error. Inspect local compile log.' }
$after=(Get-FileHash -LiteralPath $mq4 -Algorithm SHA256).Hash
if ($before -ne $after) { throw 'Source changed during compile. NO_GO.' }
$log=Join-Path $dir 'FxFinalPaperReadOnlyObserver.log'
$ex4=Join-Path $dir 'FxFinalPaperReadOnlyObserver.ex4'
if (-not (Test-Path -LiteralPath $log -PathType Leaf)) {
    throw 'MetaEditor local compile log missing. NO_GO.'
}
$text=Get-Content -LiteralPath $log -Raw
if ($text -notmatch '\b0\s+errors?\b') {
    throw 'MetaEditor log does not explicitly report zero errors. NO_GO.'
}
if (-not (Test-Path -LiteralPath $ex4 -PathType Leaf)) {
    throw 'Compiled EX4 missing. NO_GO.'
}
$size=(Get-Item -LiteralPath $ex4).Length
if ($size -le 0 -or $size -gt 2000000) {
    throw 'Compiled EX4 size unreasonable. NO_GO.'
}
Write-Host ('ISOLATED_MQ4_COMPILE_ZERO_ERRORS_EX4_PRESENT_NO_GO')
Write-Host ('Source SHA256: '+$after)
Write-Host ('EX4 SHA256: '+(Get-FileHash -LiteralPath $ex4 -Algorithm SHA256).Hash)
Write-Host ('MetaEditor evidence folder: '+$dir)
Write-Host 'No EA installed, no chart attachment, no journal/risk/AI/MT4 action.'
