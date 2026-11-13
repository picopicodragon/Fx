# FWD-1401: explicit one-shot start/step/status of immutable NO-ORDER shadow.
# No broker/MT4, no scheduler, no AI API, no automatic price/macro fetch.
# The operator chooses already-copied and unchanged MT4 3-pair CSV folders.
[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)]
  [ValidateSet('start','step','status')]
  [string]$Mode,

  [Parameter(Mandatory=$true)]
  [string]$StateDirectory,

  [string[]]$Session = @(),

  [string]$PlanFile = '',

  [string]$AsOfUtc = ''
)
$ErrorActionPreference = 'Stop'
if (($Session.Count -gt 0 -and $PlanFile) -or
    ($Mode -eq 'status' -and ($Session.Count -gt 0 -or $PlanFile)) -or
    ($Mode -ne 'status' -and $Session.Count -eq 0 -and -not $PlanFile)) {
  throw 'FWD shadow: supply named new CSV sessions OR full plan for start/step, neither for status. NO_GO'
}
if ($Mode -eq 'start') {
  if (Test-Path -LiteralPath $StateDirectory) {
    throw 'FWD shadow: state directory exists; never overwrite. NO_GO'
  }
  $parent = Split-Path -Path $StateDirectory -Parent
  if (-not $parent) { $parent = '.' }
  if (-not (Test-Path -LiteralPath $parent -PathType Container)) {
    throw 'FWD shadow: state directory parent missing. NO_GO'
  }
} elseif (-not (Test-Path -LiteralPath $StateDirectory -PathType Container)) {
  throw 'FWD shadow: saved state directory missing. NO_GO'
}
$arguments = @('-m', 'research.forward_shadow_start',
               '--mode', $Mode, '--state-dir', $StateDirectory)
if ($AsOfUtc) {
  $arguments += @('--asof-utc', $AsOfUtc)
}
if ($PlanFile) {
  if (-not (Test-Path -LiteralPath $PlanFile -PathType Leaf)) {
    throw 'FWD shadow: plan file not found. NO_GO'
  }
  $arguments += @('--plan-file', $PlanFile)
}
foreach ($value in $Session) {
  if ($value -notmatch '^[A-Za-z0-9][A-Za-z0-9_-]{0,39}=.+$') {
    throw 'FWD shadow: session must be LABEL=COPIED_CSV_FOLDER. NO_GO'
  }
  $parts = $value.Split('=', 2)
  if (-not (Test-Path -LiteralPath $parts[1] -PathType Container)) {
    throw 'FWD shadow: copied CSV session folder not found. NO_GO'
  }
  $arguments += @('--session', $value)
}
& python @arguments
if ($LASTEXITCODE -ne 0) {
  throw 'FWD shadow safety audit or local write-once record failed closed. NO_GO'
}
Write-Output "FWD shadow $Mode complete as research-only HOLD; no order permission."
