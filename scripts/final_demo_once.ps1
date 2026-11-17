# DEMO-SPRINT-09: explicit one-shot official feed -> 2-model AI -> DEMO MT4 handoff.
# All switches OFF by default; never launches MT4 or schedules tasks.
[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)][int]$ExpectedDemoAccount,
  [Parameter(Mandatory=$true)][string]$AnalystModel,
  [Parameter(Mandatory=$true)][string]$ReviewerModel,
  [switch]$AllowOfficialFeedNetwork,
  [switch]$AllowPaidAi,
  [switch]$EnableDemoIntent,
  [string]$Mt4FilesDir = ''
)
$ErrorActionPreference = 'Stop'
if ($ExpectedDemoAccount -le 0 -or $ExpectedDemoAccount -gt 999999999) {
  throw 'Valid DEMO account PIN required. NO_GO'
}
if ($AnalystModel -eq $ReviewerModel) {
  throw 'Distinct AI model IDs required. NO_GO'
}
if ($EnableDemoIntent) {
  if (-not $Mt4FilesDir -or -not (Test-Path -LiteralPath $Mt4FilesDir -PathType Container)) {
    throw 'Existing MT4 MQL4\Files path required. NO_GO'
  }
  $canonical = (Resolve-Path -LiteralPath $Mt4FilesDir).Path.TrimEnd('\')
  if (-not $canonical.EndsWith('\MQL4\Files', [System.StringComparison]::OrdinalIgnoreCase)) {
    throw 'Selected folder must be this MT4 MQL4\Files. NO_GO'
  }
} elseif ($Mt4FilesDir) {
  throw 'Do not provide MT4 path unless explicitly enabling DEMO intent. NO_GO'
}
$root = Join-Path $env:USERPROFILE 'Documents\FXForwardEvidence'
$store = Join-Path $root 'macro_forward_journal'
$ledgers = Join-Path $root 'final_demo_ai_ledgers'
if (-not (Test-Path -LiteralPath $store -PathType Container)) {
  throw 'Real observation journal absent. NO_GO'
}
if (-not (Test-Path -LiteralPath $ledgers)) {
  New-Item -ItemType Directory -Path $ledgers -ErrorAction Stop | Out-Null
}
if ($AllowOfficialFeedNetwork) {
  $stamp = Get-Date -Format 'yyyyMMdd_HHmmss_fff'
  $archive = Join-Path $root ('demo_feed_' + $stamp)
  python -m research.forward_macro_feed_once --store $store --out-dir $archive --allow-network --feed fed_policy --feed bls_cpi --feed bls_empsit
  if ($LASTEXITCODE -ne 0) {
    throw 'Official feed intake failed. No automatic retry. NO_GO'
  }
}
$argv = @(
  '-m','research.final_demo_cycle',
  '--store',$store,
  '--ledger-dir',$ledgers,
  '--expected-demo-account',"$ExpectedDemoAccount",
  '--analyst-model',$AnalystModel,
  '--reviewer-model',$ReviewerModel
)
if ($AllowPaidAi) {
  if (-not $env:OPENAI_API_KEY) {
    throw 'Explicit API opt-in but OPENAI_API_KEY missing. NO_GO'
  }
  $argv += @('--allow-external-api','--max-api-calls','2')
}
if ($EnableDemoIntent) {
  $argv += @('--operator-enable-demo-intent','--terminal-files',$Mt4FilesDir)
}
python @argv
if ($LASTEXITCODE -ne 0) {
  throw 'DEMO cycle evidence or AI validation failed. NO_GO'
}
Write-Host 'DEMO cycle ended. This PowerShell script did not send orders.'
