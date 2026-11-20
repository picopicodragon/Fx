# FINAL-AUTO: MANUALLY START a paid internal VIRTUAL-only monitor after
# separate stop review, full official+clock+cost evidence, current incident
# approval and new <=JPY3000 budget. This script DOES NOT stop/restart
# existing MT4/Python, clear risk latches, or touch broker order APIs.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$Mt4FilesDirectory,
    [Parameter(Mandatory=$true)][string[]]$NewsBundle,
    [Parameter(Mandatory=$true)][string]$EntryEvidenceFile,
    [Parameter(Mandatory=$true)][string]$OfficialArchiveDirectory,
    [Parameter(Mandatory=$true)][string]$BudgetAuthorizationFile,
    [Parameter(Mandatory=$true)][string]$AnalystModel,
    [Parameter(Mandatory=$true)][string]$ReviewerModel,
    [Parameter(Mandatory=$true)][string]$OperatorPaidConsent,
    [string]$StateRoot=''
)
$ErrorActionPreference='Stop'
$consent='I_ACCEPT_NEW_PAID_AI_USAGE_FROM_APPROVED_JPY_BUDGET'
if ($OperatorPaidConsent -cne $consent) {
    throw 'Separate explicit consent for NEW billed AI calls is required. NO_GO.'
}
if (-not $StateRoot) {
    $StateRoot=Join-Path $env:USERPROFILE 'Documents\FXForwardEvidence\final_virtual_paper'
}
if (-not (Test-Path -LiteralPath $StateRoot -PathType Container)) {
    throw 'Existing 6/6 legacy journal root required. NO_GO'
}
if (Test-Path -LiteralPath (Join-Path $StateRoot '.single_operator.lock')) {
    throw 'Existing supervisor lock present. STOP: never run two monitors.'
}
# Fail closed if any current Python is already executing this paper module.
# Process absence outside our own Windows host is NOT independently attested.
$running=@(Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='pythonw.exe'" |
    Where-Object { $_.CommandLine -match 'research[.]final_paper_runtime' })
if ($running.Count -ne 0) {
    throw 'A paper Python supervisor is already running. NO_GO.'
}
if ([string]::IsNullOrWhiteSpace($env:OPENAI_API_KEY)) {
    throw 'An API key is required for this separately approved paid run.'
}
if (-not $NewsBundle -or $NewsBundle.Count -eq 0 -or $NewsBundle.Count -gt 5) {
    throw 'One to five already saved official news bundles required.'
}
if ($AnalystModel -ceq $ReviewerModel -or
    [string]::IsNullOrWhiteSpace($AnalystModel) -or
    [string]::IsNullOrWhiteSpace($ReviewerModel)) {
    throw 'Distinct analyst and reviewer model IDs required.'
}
$mt4=(Resolve-Path -LiteralPath $Mt4FilesDirectory -ErrorAction Stop).Path.TrimEnd('\')
if (-not $mt4.EndsWith('\MQL4\Files',[StringComparison]::OrdinalIgnoreCase)) {
    throw 'Original DEMO MQL4\Files path required. NO_GO'
}
$evidence=(Resolve-Path -LiteralPath $EntryEvidenceFile -ErrorAction Stop).Path
$official=(Resolve-Path -LiteralPath $OfficialArchiveDirectory -ErrorAction Stop).Path
$budget=(Resolve-Path -LiteralPath $BudgetAuthorizationFile -ErrorAction Stop).Path
$bundlePaths=@()
foreach($bundle in $NewsBundle) {
    $bundlePaths+=@((Resolve-Path -LiteralPath $bundle -ErrorAction Stop).Path)
}
# Two new accounting directories are separate from OLD 6/6 AI ledgers.
# This is the only mutation performed before the explicit preflight.
foreach($name in @('auto_budget_journal','auto_ai_research')) {
    $dir=Join-Path $StateRoot $name
    if (-not (Test-Path -LiteralPath $dir)) {
        New-Item -Path $dir -ItemType Directory -ErrorAction Stop | Out-Null
    }
}
$report=Join-Path $StateRoot ('final_auto_preflight_'+
    (Get-Date -Format 'yyyyMMdd_HHmmss_fff')+'.json')
Write-Host 'Read-only preflight: legacy 6/6, current stop consent, official sources, independent clock review and paid budget.'
& python -m research.final_paper_final_auto_preflight --state-root $StateRoot --mt4-files $mt4 --evidence $evidence --official-archive $official --budget-authorization $budget --analyst-model $AnalystModel --reviewer-model $ReviewerModel --out $report
if ($LASTEXITCODE -ne 0) {
    throw 'Full auto VIRTUAL preflight incomplete. No paid inference launched.'
}
# Re-check process and lock after the slow full journal audit.
if (Test-Path -LiteralPath (Join-Path $StateRoot '.single_operator.lock')) {
    throw 'Concurrent monitor lock appeared during preflight. NO_GO'
}
$running=@(Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='pythonw.exe'" |
    Where-Object { $_.CommandLine -match 'research[.]final_paper_runtime' })
if ($running.Count -ne 0) {
    throw 'Concurrent Python paper supervisor appeared. NO_GO.'
}
Write-Host ('Human-reviewed final auto preflight: '+$report)
Write-Host 'Starting ONLY internal virtual FX portfolio; NO MT4/DEMO/real broker order.'
Write-Host 'NEW potentially billed two-model inference uses separate human-approved JPY reserves.'
$cmd=@('-m','research.final_paper_runtime',
    '--mt4-files',$mt4,'--state-root',$StateRoot,
    '--final-auto-evidence-file',$evidence,
    '--final-auto-official-archive',$official,
    '--final-auto-budget-authorization',$budget,
    '--allow-final-paid-ai',
    '--analyst-model',$AnalystModel,
    '--reviewer-model',$ReviewerModel,
    '--interval-seconds','15','--watch')
foreach ($source in $bundlePaths) {
    $cmd+=@('--news-bundle',$source)
}
& python @cmd
if ($LASTEXITCODE -ne 0) {
    throw 'Automatic virtual monitor failed closed. PRESERVE lock, evidence and ledgers.'
}
Write-Host 'Internal virtual-only operator stopped. No broker order capability.'
