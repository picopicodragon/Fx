# FWD-1361+ one-shot, non-trading Rakuten MT4 DEMO forward observation pilot.
# No MetaEditor/MT4 launch, no terminal MQL4 or account access, no network,
# no scheduler/background process, no order submission, no policy changes.
# Use with MANUALLY COPIED CSV session folders, never the live MT4 data folder.
[CmdletBinding()]
param(
  [ValidateSet('prepare', 'audit')]
  [string]$Mode = 'prepare',

  [string[]]$Session = @(),
  [string]$PlanFile = '',
  [string]$OutputDirectory = 'out',
  [string]$AsOfUtc = ''
)

$ErrorActionPreference = 'Stop'
if ($Mode -eq 'prepare' -and ($Session.Count -gt 0 -or $PlanFile)) {
  throw 'FWD pilot: prepare does not ingest session data. NO_GO'
}
if ($Mode -eq 'audit') {
  if (($Session.Count -eq 0 -and -not $PlanFile) -or
      ($Session.Count -gt 0 -and $PlanFile)) {
    throw 'FWD pilot: provide Session or PlanFile, but not both. NO_GO'
  }
}
if (-not (Test-Path -LiteralPath $OutputDirectory -PathType Container)) {
  throw 'FWD pilot: output directory does not exist. NO_GO'
}
if (-not $AsOfUtc) {
  $AsOfUtc = [DateTime]::UtcNow.ToString(
    'yyyy-MM-ddTHH:mm:ssZ', [Globalization.CultureInfo]::InvariantCulture)
}
$tag = [DateTime]::UtcNow.ToString(
  'yyyyMMdd_HHmmss_fff', [Globalization.CultureInfo]::InvariantCulture)
$dest = Join-Path $OutputDirectory ("mt4_noorder_pilot_" + $Mode + "_" + $tag + ".json")
if (Test-Path -LiteralPath $dest) {
  throw 'FWD pilot: output filename already exists; no overwrite. NO_GO'
}

$arguments = @('-m', 'research.forward_demo_pilot',
               '--mode', $Mode, '--asof-utc', $AsOfUtc,
               '--out', $dest)
if ($PlanFile) {
  if (-not (Test-Path -LiteralPath $PlanFile -PathType Leaf)) {
    throw 'FWD pilot: plan file not found. NO_GO'
  }
  $arguments += @('--plan-file', $PlanFile)
}
foreach ($entry in $Session) {
  if ($entry -notmatch '^[A-Za-z0-9][A-Za-z0-9_-]{0,39}=.+$') {
    throw 'FWD pilot: Session must be LABEL=EXISTING_COPIED_CSV_FOLDER. NO_GO'
  }
  $parts = $entry.Split('=', 2)
  if (-not (Test-Path -LiteralPath $parts[1] -PathType Container)) {
    throw 'FWD pilot: copied session folder is absent. NO_GO'
  }
  $arguments += @('--session', $entry)
}

# This is the ONLY executable subprocess. It reads local saved evidence and
# writes one new local report outside any original/capture source folder.
& python @arguments
if ($LASTEXITCODE -ne 0) {
  throw 'FWD pilot offline evidence audit failed closed. NO_GO'
}
Write-Output "FWD read-only observation pilot report: $dest"
Write-Output 'MT4/EA not launched. Human-controlled read-only DEMO observation only.'
Write-Output 'DEMO and LIVE orders still prohibited; safety hold remains latched.'
