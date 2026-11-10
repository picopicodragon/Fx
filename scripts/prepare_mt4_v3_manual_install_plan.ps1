# FWD-071: NO-COPY preparation report for an existing single MT4 installation.
# The operator explicitly provides the MT4 DATA DIRECTORY and source path.
# Does not install MQL4, compile via MetaEditor, launch MT4, read accounts,
# enable AutoTrading, change Windows policy, or submit any trade.
param(
  [Parameter(Mandatory=$true)][string]$Mql4Source,
  [Parameter(Mandatory=$true)][string]$Mt4DataDirectory,
  [Parameter(Mandatory=$true)][string]$PlanOutput
)
$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $Mql4Source -PathType Leaf)) {
  throw 'FWD-071 MQL4 source not found. NO_GO'
}
if (-not (Test-Path -LiteralPath $Mt4DataDirectory -PathType Container)) {
  throw 'FWD-071 MT4 data directory not found. NO_GO'
}
if (Test-Path -LiteralPath $PlanOutput) {
  throw 'FWD-071 output exists; will not overwrite. NO_GO'
}
$source = (Resolve-Path -LiteralPath $Mql4Source).Path
$mt4Dir = (Resolve-Path -LiteralPath $Mt4DataDirectory).Path
$scriptsDir = Join-Path $mt4Dir 'MQL4\Scripts'
$filesDir = Join-Path $mt4Dir 'MQL4\Files'
if (-not (Test-Path -LiteralPath $scriptsDir -PathType Container) -or
    -not (Test-Path -LiteralPath $filesDir -PathType Container)) {
  throw 'FWD-071 specified directory is not a prepared MQL4 data folder. NO_GO'
}
$target = Join-Path $scriptsDir 'FxForwardReadOnlyQuoteV3.mq4'
if (Test-Path -LiteralPath $target) {
  throw 'FWD-071 script already exists in terminal; inspect manually. NO_GO'
}
$sha = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLowerInvariant()
$plan = [ordered]@{
  schema = 'fx_forward_mt4_manual_install_plan_v1'
  status = 'MT4_MANUAL_INSTALL_PLAN_NO_GO'
  source_sha256 = $sha
  source = $source
  proposed_target = $target
  expected_terminal_files_dir = $filesDir
  manual_copy_performed = $false
  metaeditor_compilation_performed = $false
  mt4_script_execution_performed = $false
  mt4_broker_authenticated = $false
  approved_pairs = @('USD/JPY','EUR/JPY','EUR/USD')
  demo_order_execution_enabled = $false
  runtime_go_no_go = 'NO_GO'
  safety_hold_latched = $true
  real_orders_permitted = $false
}
# No write to the terminal: only the operator-selected plan output is written.
$plan | ConvertTo-Json -Depth 4 | Out-File -LiteralPath $PlanOutput -Encoding utf8 -NoClobber
Write-Output 'FWD-071 planning report created. Manual review required. NO_GO.'
