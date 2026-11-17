# DEMO-SPRINT-27: one operator-run, actual H1/archived news periodic analysis.
# Never places MT4 orders, enables AutoTrading, or schedules unattended tasks.
[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)][string]$H1CopiedDirectory,
  [Parameter(Mandatory=$true)][string[]]$NewsBundle,
  [string[]]$Pair = @('USD/JPY','EUR/JPY','EUR/USD'),
  [switch]$AllowPaidAi,
  [string]$AnalystModel = '',
  [string]$ReviewerModel = '',
  [string]$OutputDirectory = ''
)
$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $H1CopiedDirectory -PathType Container)) {
  throw 'Missing manually copied three-pair CLOSED H1 CSV directory. NO_GO'
}
if (-not $NewsBundle -or $NewsBundle.Count -gt 5) {
  throw '1..5 immutable official news bundles required. NO_GO'
}
foreach ($bundle in $NewsBundle) {
  if (-not (Test-Path -LiteralPath $bundle -PathType Container)) {
    throw 'Missing official saved news bundle. NO_GO'
  }
}
if (@($Pair | Select-Object -Unique).Count -ne $Pair.Count -or
    @($Pair | Where-Object {$_ -notin @('USD/JPY','EUR/JPY','EUR/USD')}).Count -gt 0) {
  throw 'Invalid/repeated FX pair. NO_GO'
}
if ($AllowPaidAi) {
  if (-not $AnalystModel -or -not $ReviewerModel -or
      $AnalystModel -eq $ReviewerModel -or -not $env:OPENAI_API_KEY) {
    throw 'Two distinct API model IDs and OPENAI_API_KEY required. NO_GO'
  }
} elseif ($AnalystModel -or $ReviewerModel) {
  throw 'Do not set model IDs without explicit paid-AI opt-in. NO_GO'
}
$root = Join-Path $env:USERPROFILE 'Documents\FXForwardEvidence'
if (-not $OutputDirectory) {
  $OutputDirectory = Join-Path $root 'final_demo_periodic'
}
if (-not (Test-Path -LiteralPath $OutputDirectory)) {
  New-Item -ItemType Directory -Path $OutputDirectory -ErrorAction Stop | Out-Null
}
# Prior ambiguous/pending ledger blocks new billable cycles unless a specific
# HTTP401 analyst rejection was manually reviewed, hash-bound and authenticated.
if ($AllowPaidAi) {
  & python -m research.final_demo_http401_recovery --check-directory $OutputDirectory
  if ($LASTEXITCODE -ne 0) {
    throw 'Prior paid AI dispatch unresolved. No new billable retry. NO_GO'
  }
}
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss_fff'
foreach ($pairName in $Pair) {
  $tag = $pairName.Replace('/','')
  if ($AllowPaidAi) {
    $ledger = Join-Path $OutputDirectory ('ai_'+$tag+'_'+$stamp+'.json')
    $arguments = @('-m','research.final_demo_periodic_ai',
      '--captures',$H1CopiedDirectory,'--pair',$pairName,
      '--ledger',$ledger,'--analyst-model',$AnalystModel,
      '--reviewer-model',$ReviewerModel,
      '--allow-external-api','--max-api-calls','2')
  } else {
    $out = Join-Path $OutputDirectory ('periodic_'+$tag+'_'+$stamp+'.json')
    $arguments = @('-m','research.final_demo_periodic',
      '--captures',$H1CopiedDirectory,'--pair',$pairName,'--out',$out)
  }
  foreach ($bundle in $NewsBundle) {
    $arguments += @('--news-bundle',$bundle)
  }
  & python @arguments
  if ($LASTEXITCODE -ne 0) {
    throw ('Periodic research HOLD / evidence rejected for ' + $pairName +
      '. No automatic retry. Check logs/ledger before restarting.')
  }
}
Write-Host 'All selected periodic AI research cycles finished. No MT4 orders sent.'
