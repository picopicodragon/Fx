# Compile V2 READ-ONLY MQ4 into a NEW isolated Windows folder.
# DOES NOT install EX4, touch MQL4\Experts, change charts or stop terminal.
# Operator must explicitly invoke with -ApproveIsolatedCompile.
[CmdletBinding(DefaultParameterSetName='Compile')]
param(
    [Parameter(ParameterSetName='Compile',Mandatory=$true)][string]$MetaEditorExe,
    [Parameter(ParameterSetName='Compile',Mandatory=$true)][switch]$ApproveIsolatedCompile,
    [Parameter(ParameterSetName='Inspect',Mandatory=$true)][string]$InspectExistingDirectory,
    [string]$StateRoot=''
)
$ErrorActionPreference='Stop'
# A single-file MetaEditor CLI may return ExitCode=1 on SUCCESS.
# Authoritative evidence: freshly created compiler log says 0 errors,
# resulting EX4 exists, and the original MQ4 copy is unchanged.
if (-not $StateRoot) {
    $StateRoot=Join-Path $env:USERPROFILE 'Documents\FXForwardEvidence\final_virtual_paper'
}
if (-not (Test-Path -LiteralPath $StateRoot -PathType Container)) {
    throw 'Existing paper evidence root missing.'
}
if ($PSCmdlet.ParameterSetName -eq 'Compile') {
    if (-not $ApproveIsolatedCompile.IsPresent) {
        throw 'This isolated MetaEditor compilation requires explicit opt-in.'
    }
    $exe=(Resolve-Path -LiteralPath $MetaEditorExe -ErrorAction Stop).Path
    if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) {
        throw 'MetaEditor executable not found.'
    }
    if ((Split-Path -Leaf $exe) -notmatch '^metaeditor(64)?\.exe$') {
        throw 'Only actual MetaEditor executable permitted.'
    }
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
if ($PSCmdlet.ParameterSetName -eq 'Compile') {
    $dir=Join-Path $StateRoot ('metaeditor_v2_candidate_'+(Get-Date -Format 'yyyyMMdd_HHmmss_fff'))
    if (Test-Path -LiteralPath $dir) {
        throw 'Compile evidence directory already exists. NO_GO.'
    }
    New-Item -ItemType Directory -Path $dir -ErrorAction Stop | Out-Null
    $mq4=Join-Path $dir 'FxFinalPaperReadOnlyObserver.mq4'
    Copy-Item -LiteralPath $source -Destination $mq4 -ErrorAction Stop
    $before=(Get-FileHash -LiteralPath $mq4 -Algorithm SHA256).Hash
    Write-Host ('Compiling isolated V2 source: '+$dir)
    $arg=('/compile:"'+$mq4+'" /log')
    $proc=Start-Process -FilePath $exe -ArgumentList $arg -Wait -PassThru
    $metaEditorExitCode=$proc.ExitCode
    Write-Host ('MetaEditor exit code (informational only): '+$metaEditorExitCode)
} else {
    $dir=(Resolve-Path -LiteralPath $InspectExistingDirectory -ErrorAction Stop).Path
    $expectedParent=(Resolve-Path -LiteralPath $StateRoot -ErrorAction Stop).Path.TrimEnd('\')
    if (-not [string]::Equals(
        [System.IO.Path]::GetDirectoryName($dir.TrimEnd('\')),
        $expectedParent,
        [System.StringComparison]::OrdinalIgnoreCase)) {
        throw 'Existing compile evidence must be a DIRECT CHILD of StateRoot. NO_GO.'
    }
    if ((Split-Path -Leaf $dir) -notmatch '^metaeditor_v2_candidate_[0-9]{8}_[0-9]{6}_[0-9]{3}$') {
        throw 'Unexpected compile evidence directory. NO_GO.'
    }
    $mq4=Join-Path $dir 'FxFinalPaperReadOnlyObserver.mq4'
    $metaEditorExitCode=$null
    Write-Host ('Inspecting preserved compile evidence WITHOUT running MetaEditor: '+$dir)
}
if (-not (Test-Path -LiteralPath $mq4 -PathType Leaf)) {
    throw ('Isolated MQ4 copy missing. Evidence directory: '+$dir)
}
$after=(Get-FileHash -LiteralPath $mq4 -Algorithm SHA256).Hash
$actualSource=(Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash
if ($after -ne $actualSource) {
    throw ('Isolated source SHA256 differs from current V2 candidate. Evidence directory: '+$dir)
}
if ($PSCmdlet.ParameterSetName -eq 'Compile' -and $before -ne $after) {
    throw ('Source changed during compile. Evidence directory: '+$dir)
}
$log=Join-Path $dir 'FxFinalPaperReadOnlyObserver.log'
$ex4=Join-Path $dir 'FxFinalPaperReadOnlyObserver.ex4'
Write-Host ('Compiler log path: '+$log)
Write-Host ('EX4 output path: '+$ex4)
Write-Host ('MetaEditor exit code: '+$(if($null -eq $metaEditorExitCode){'NOT_RE-RUN_INSPECTION'}else{$metaEditorExitCode}))
if (-not (Test-Path -LiteralPath $log -PathType Leaf)) {
    throw 'MetaEditor compile log missing. Exit code alone is NOT proof of success.'
}
$logInfo=Get-Item -LiteralPath $log -ErrorAction Stop
if ($logInfo.Length -le 0 -or $logInfo.Length -gt 500000) {
    throw 'MetaEditor log size invalid. NO_GO.'
}
$text=Get-Content -LiteralPath $log -Raw -ErrorAction Stop
if ($text -notmatch '(?i)\b[0-9]+\s+errors?\b' -and $text -match [char]0) {
    # Some MetaEditor releases write a UTF-16LE log without a BOM.
    $text=[System.Text.Encoding]::Unicode.GetString(
        [System.IO.File]::ReadAllBytes($log))
}
$summaryLines=@($text -split '\r?\n' | Where-Object {
    $_ -match '(?i)\b[0-9]+\s+errors?\b'
})
if ($summaryLines.Count -eq 0) {
    throw 'Cannot identify a MetaEditor compiler error summary. Inspect the original log.'
}
$lastSummary=[string]$summaryLines[-1]
Write-Host ('Last compiler result: '+$lastSummary.Trim())
if ($lastSummary -notmatch '(?i)\b0\s+errors?\b') {
    throw 'MetaEditor compiler log reports errors (or no final 0-error result). NO_GO.'
}
if (-not (Test-Path -LiteralPath $ex4 -PathType Leaf)) {
    throw 'No newly created EX4 exists. A zero-error log alone is insufficient.'
}
$ex4Info=Get-Item -LiteralPath $ex4 -ErrorAction Stop
if ($ex4Info.Length -le 0 -or $ex4Info.Length -gt 2000000) {
    throw 'Compiled EX4 size unreasonable. NO_GO.'
}
# Both files originated inside a unique empty compile folder. For
# inspection, source and output must be co-located; never accept the
# presence of an EX4 somewhere under the running MT4 terminal.
Write-Host 'ISOLATED_MQ4_COMPILE_ZERO_ERRORS_EX4_PRESENT_NO_GO'
Write-Host ('Source SHA256: '+$after)
Write-Host ('EX4 SHA256: '+(Get-FileHash -LiteralPath $ex4 -Algorithm SHA256).Hash)
Write-Host ('MetaEditor evidence folder: '+$dir)
Write-Host 'No EA installed, no chart attachment, no journal/risk/AI/MT4 action.'
) {
        throw 'Only actual MetaEditor executable permitted.'
    }
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
if ($PSCmdlet.ParameterSetName -eq 'Compile') {
    $dir=Join-Path $StateRoot ('metaeditor_v2_candidate_'+(Get-Date -Format 'yyyyMMdd_HHmmss_fff'))
    if (Test-Path -LiteralPath $dir) {
        throw 'Compile evidence directory already exists. NO_GO.'
    }
    New-Item -ItemType Directory -Path $dir -ErrorAction Stop | Out-Null
    $mq4=Join-Path $dir 'FxFinalPaperReadOnlyObserver.mq4'
    Copy-Item -LiteralPath $source -Destination $mq4 -ErrorAction Stop
    $before=(Get-FileHash -LiteralPath $mq4 -Algorithm SHA256).Hash
    Write-Host ('Compiling isolated V2 source: '+$dir)
    $arg=('/compile:"'+$mq4+'" /log')
    $proc=Start-Process -FilePath $exe -ArgumentList $arg -Wait -PassThru
    $metaEditorExitCode=$proc.ExitCode
    Write-Host ('MetaEditor exit code (informational only): '+$metaEditorExitCode)
} else {
    $dir=(Resolve-Path -LiteralPath $InspectExistingDirectory -ErrorAction Stop).Path
    $expectedParent=(Resolve-Path -LiteralPath $StateRoot -ErrorAction Stop).Path.TrimEnd('\')
    if (-not [string]::Equals(
        [System.IO.Path]::GetDirectoryName($dir.TrimEnd('\')),
        $expectedParent,
        [System.StringComparison]::OrdinalIgnoreCase)) {
        throw 'Existing compile evidence must be a DIRECT CHILD of StateRoot. NO_GO.'
    }
    if ((Split-Path -Leaf $dir) -notmatch '^metaeditor_v2_candidate_[0-9]{8}_[0-9]{6}_[0-9]{3}$') {
        throw 'Unexpected compile evidence directory. NO_GO.'
    }
    $mq4=Join-Path $dir 'FxFinalPaperReadOnlyObserver.mq4'
    $metaEditorExitCode=$null
    Write-Host ('Inspecting preserved compile evidence WITHOUT running MetaEditor: '+$dir)
}
if (-not (Test-Path -LiteralPath $mq4 -PathType Leaf)) {
    throw ('Isolated MQ4 copy missing. Evidence directory: '+$dir)
}
$after=(Get-FileHash -LiteralPath $mq4 -Algorithm SHA256).Hash
$actualSource=(Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash
if ($after -ne $actualSource) {
    throw ('Isolated source SHA256 differs from current V2 candidate. Evidence directory: '+$dir)
}
if ($PSCmdlet.ParameterSetName -eq 'Compile' -and $before -ne $after) {
    throw ('Source changed during compile. Evidence directory: '+$dir)
}
$log=Join-Path $dir 'FxFinalPaperReadOnlyObserver.log'
$ex4=Join-Path $dir 'FxFinalPaperReadOnlyObserver.ex4'
Write-Host ('Compiler log path: '+$log)
Write-Host ('EX4 output path: '+$ex4)
Write-Host ('MetaEditor exit code: '+$(if($null -eq $metaEditorExitCode){'NOT_RE-RUN_INSPECTION'}else{$metaEditorExitCode}))
if (-not (Test-Path -LiteralPath $log -PathType Leaf)) {
    throw 'MetaEditor compile log missing. Exit code alone is NOT proof of success.'
}
$logInfo=Get-Item -LiteralPath $log -ErrorAction Stop
if ($logInfo.Length -le 0 -or $logInfo.Length -gt 500000) {
    throw 'MetaEditor log size invalid. NO_GO.'
}
$text=Get-Content -LiteralPath $log -Raw -ErrorAction Stop
if ($text -notmatch '(?i)\b[0-9]+\s+errors?\b' -and $text -match [char]0) {
    # Some MetaEditor releases write a UTF-16LE log without a BOM.
    $text=[System.Text.Encoding]::Unicode.GetString(
        [System.IO.File]::ReadAllBytes($log))
}
$summaryLines=@($text -split '\r?\n' | Where-Object {
    $_ -match '(?i)\b[0-9]+\s+errors?\b'
})
if ($summaryLines.Count -eq 0) {
    throw 'Cannot identify a MetaEditor compiler error summary. Inspect the original log.'
}
$lastSummary=[string]$summaryLines[-1]
Write-Host ('Last compiler result: '+$lastSummary.Trim())
if ($lastSummary -notmatch '(?i)\b0\s+errors?\b') {
    throw 'MetaEditor compiler log reports errors (or no final 0-error result). NO_GO.'
}
if (-not (Test-Path -LiteralPath $ex4 -PathType Leaf)) {
    throw 'No newly created EX4 exists. A zero-error log alone is insufficient.'
}
$ex4Info=Get-Item -LiteralPath $ex4 -ErrorAction Stop
if ($ex4Info.Length -le 0 -or $ex4Info.Length -gt 2000000) {
    throw 'Compiled EX4 size unreasonable. NO_GO.'
}
# Both files originated inside a unique empty compile folder. For
# inspection, source and output must be co-located; never accept the
# presence of an EX4 somewhere under the running MT4 terminal.
Write-Host 'ISOLATED_MQ4_COMPILE_ZERO_ERRORS_EX4_PRESENT_NO_GO'
Write-Host ('Source SHA256: '+$after)
Write-Host ('EX4 SHA256: '+(Get-FileHash -LiteralPath $ex4 -Algorithm SHA256).Hash)
Write-Host ('MetaEditor evidence folder: '+$dir)
Write-Host 'No EA installed, no chart attachment, no journal/risk/AI/MT4 action.'
