# Fully automated AI virtual FX PAPER: final human-gated launch package

Status: SOURCE/CI REVIEW CANDIDATE ONLY. The running Rakuten DEMO MT4
and Windows Python supervisor remain in their original worktree.

## Actual Windows baseline, 2026-11-20

At 16:16 JST: journal 802 cycles; 6/6 old paid calls reconciled;
all six official original hashes intact; communication_latched=true.
Original quote monitoring: 3,020 CSV, 3,016 valid, four original
1-second broker-versus-tick time inversions; preserve ALL originals.
Real new AI inferences 0, real new virtual entries 0, DEMO/real MT4
orders 0. MQL4 V2 candidate not yet compiled or deployed.

## Entire new engineering batch

1. research/final_paper_go_live_acceptance.py verifies two live Windows
   snapshots, same supervisor and advancing quote/journal; rescans 3,020
   ORIGINAL quote bytes against the fixed name/SHA256 chain; reconciles
   the complete 6/6 paid AI ledger and official six archived originals;
   requires the actual no-order clock-freeze V2 source SHA and prints
   outstanding external evidence and operator approvals. A supervisor
   may legitimately append journal entries during an audit; it accepts
   only a monotonic consistent newer head.
2. scripts/final_paper_go_live_acceptance_once.ps1 collects two
   independent snapshots 75 seconds apart with ONE command. It does
   not restart/stop MT4 or Python, nor change any historical source.
3. scripts/final_paper_metaeditor_v2_compile_candidate_once.ps1 is an
   explicitly opt-in ISOLATED MetaEditor compile of a COPY of candidate
   MQ4. It verifies a 0-error log, EX4 existence/size and hashes.
   It does not install EX4 into a live terminal or touch running EAs.
4. research/final_paper_current_incident_release.py plus
   scripts/final_paper_stage_current_comm_release_once.ps1 implement
   human-approved current-incident-specific, one-use communication
   latch release. Unlike the old 2026-11-18 approval, it recognizes
   the most recent recorded >600s gap AFTER cycle 107. Approval is
   bound to journal cycles, head SHA, gap and exact operator intent,
   must be staged while old supervisor is stopped and lock absent,
   and expires in 300 seconds. The next fresh quote can consume it
   once. Any later long interruption re-latches automatically.
   This never approves billable AI, macro/clock/cost or broker orders.
5. Tests include source tamper, exact ledger hashes, missing approvals,
   risk re-latch and MQL4/PowerShell parser checks.

## Windows acceptance, from NEW worktree, no disruption

    cd "$env:USERPROFILE\Documents\ChatGPT\Fx-PAPER-INTEGRATED-REVIEW-20261120"
    git fetch origin
    if ($LASTEXITCODE -ne 0) { throw 'Git fetch failed' }
    $tree=Join-Path $env:USERPROFILE 'Documents\ChatGPT\Fx-PAPER-LAUNCH-REVIEW-20261120'
    if (Test-Path -LiteralPath $tree) { throw 'Target folder already exists' }
    git worktree add --detach $tree origin/feat/final-paper-launch-acceptance-package-20261120
    if ($LASTEXITCODE -ne 0) { throw 'Worktree creation failed' }
    Set-Location $tree
    .\scripts\final_paper_go_live_acceptance_once.ps1 -Mt4FilesDirectory $mt4Files

This requires the previously saved final_virtual_paper evidence folder,
the original quote_time_order_campaign_20261120_140145_466.json and
official_public_capture_20261120_113041_303 directory. If missing,
FAIL CLOSED, never regenerate fake prior evidence.

Successful acceptance is:
GO_LIVE_EVIDENCE_VERIFIED_OPERATOR_GATES_REMAIN_NO_GO.
It is NOT full automatic AI virtual trading permission.

## MetaEditor V2 compile, optional operator-initiated step

Find the actual MetaEditor executable from Rakuten MT4 installation.
After explicit operator decision, compile only an ISOLATED COPIED source:

    .\scripts\final_paper_metaeditor_v2_compile_candidate_once.ps1 -MetaEditorExe '<actual absolute metaeditor.exe path>' -ApproveIsolatedCompile

The command does not remove/replace or attach any EA. Manually review
the 0-error MetaEditor log, MQ4 SHA, new EX4 SHA, and old EA version.
Separately plan intended old EA stop, preserve its Experts log,
check DEMO/JPY account, USDJPY/H1, AutoTrading OFF and no orders,
and attach exactly ONE newly compiled V2 observer. Save new
FXPAPER-CLOCKFREEZE-20261120-V2 Experts start marker and UTC time.
No second observer, no double Python supervisor.

MetaQuotes documents /compile:<path> /log CLI:
https://www.metatrader5.com/en/metaeditor/help/beginning/integration_ide
https://www.metatrader4.com/en/trading-platform/help/autotrading/metaeditor

## Current communications incident approval: NEVER automatic

Review the latest journal gap and physical MT4 and process continuity.
Only AFTER the current Python supervisor is intentionally stopped,
its process independently absent, and its lock absent, a human may
explicitly stage ONE incident-specific virtual-only approval:

    .\scripts\final_paper_stage_current_comm_release_once.ps1 -Mt4FilesDirectory $mt4Files -OperatorApproval 'APPROVE_20261120_INCIDENT_INTERNAL_VIRTUAL_COMMUNICATION_RELEASE_ONLY'

Do not run until that approval has been explicitly granted.
This does NOT restart Python. On an independently controlled restart
within the permit time/quote bounds, the next fresh quote may consume
it exactly once. Otherwise no latch release. It neither enables AI
payments nor entries without independently verified evidence.

## Provider spend control, verified 2026-11-20

OpenAI API now offers a separate enforceable MONTHLY hard spending
limit for organization or project, distinct from mere advisory alerts.
The vendor states enforcement is not instantaneous: slight overrun
may occur. Thus both provider hard cap and local worst-case
two-model-cost reservation are necessary, not guaranteed precise
cost ceilings.
https://developers.openai.com/api/docs/guides/spend-limits

The ¥3,000/month planning amount is not a signed approval to spend
or an actual provider USD hard cap. Operator approval is needed for
new model API calls, project limit and expected FX conversion; paid
provider usage/invoices must reconcile in JPY. Existing 6/6 historical
AI calls MUST never reset. Ambiguous paid requests are never retried.

## Real outstanding GO conditions

- Verified complete USD/EUR/JPY high impact calendar and +/-15 minute
  blackout (six stored original SHA matches alone do not prove this).
- Point-in-time consensus prior to release, with source/time evidence.
- PC clock vs Rakuten broker independent reference verification.
- Broker contract and real spread/slippage/commission/swap modeled.
- Evidence that V2 built, old EA exited and one new read-only DEMO EA
  alone is running. Old four invalid quote originals remain intact.
- Operator-approved release for the exact 2026-11-20 communications
  incident, provider hard cap, JPY budget and call cap review.
- New paid API remains unauthorized until explicit user budget consent.

Only after these are genuinely verified and approved may a separately
reviewed runtime permit AI-generated virtual entries. Broker MT4 orders
are permanently disabled. Source/CI success is not operational GO.
Main merge is operator-controlled.


## 2026-11-20 17:04 JST: Windows first-handoff false failure fixed

The first Windows read-only handoff successfully saved a JSON:

- local_machine_handoff_20261120_170435_039.json
- exactly one paper supervisor and one MT4 terminal; journal 850;
  newest original FxPaperQuote_20261120_080356.csv.
- Previous parent script incorrectly used inherited $LASTEXITCODE after
  calling a PowerShell child. That child runs w32tm.exe /query /status as
  an optional observation, so the nonzero LASTEXITCODE described only the
  local Windows time service diagnostic, not a failure to write the handoff.
- Parent now validates **exactly one newly created JSON** and explicit
  handoff schema, process count, supervisor lock and NO_GO restrictions.
  It still fails closed when an evidence file is absent, invalid or unsafe.
- The actual w32tm status is not rewritten or claimed as clock attestation.
  The running Python/MT4 remains untouched, all approval and billing
  requirements are unchanged.
- Retrieve the latest PR branch in the existing separate REVIEW worktree:

    git fetch origin
    if ($LASTEXITCODE -ne 0) { throw 'Git fetch failed' }
    git switch --detach origin/feat/final-paper-launch-acceptance-package-20261120
    if ($LASTEXITCODE -ne 0) { throw 'Review checkout failed' }
    .\scripts\final_paper_go_live_acceptance_once.ps1 -Mt4FilesDirectory $mt4Files

This checkout is only the dedicated review worktree, not the original
running supervisor checkout. Never modify or check out the active process
working tree. The saved first snapshot stays intact; rerun produces two
new distinct samples and is safe and read only.


## 2026-11-20: MetaEditor returned nonzero after isolated V2 compile

Actual first Windows compile printed Compiling ONE isolated V2 source only
then stopped on nonzero MetaEditor process exit. This only proves a
nonzero native status, NOT that MQL4 failed.

MetaEditor build 6230 can return the NUMBER of files successfully
compiled (single successful source returns 1). MetaQuotes documentation
specifies /compile:"..." /log with logs next to the source.
Check the last Result: N errors line and a new isolated EX4, not solely
native exit status.

The script now supports read-only inspection of the EXISTING isolated
compile folder WITHOUT launching MetaEditor again:

    $root=Join-Path $env:USERPROFILE 'Documents\FXForwardEvidence\final_virtual_paper'
    $last=Get-ChildItem -LiteralPath $root -Directory -Filter 'metaeditor_v2_candidate_*' |
        Sort-Object Name -Descending | Select-Object -First 1
    if ($null -eq $last) { throw 'No isolated compile evidence folder' }
    .\scripts\final_paper_metaeditor_v2_compile_candidate_once.ps1 -InspectExistingDirectory $last.FullName

Inspection verifies current V2 MQ4 SHA matches the copied source, final
compiler zero-error summary, EX4 existence/size and EX4 SHA.
A missing log or EX4 stays NO_GO. Read-only inspection never changes
any old file. When compiling a new isolated folder, the native
MetaEditor exit code is informational only; log and actual EX4 decide.

Even a genuine compiled EX4 does not authorize installation into
running Rakuten DEMO MT4 without separate operator approval,
exclusive-EA Expert log evidence and full pretrade safety checks.

References:
https://www.metatrader5.com/en/metaeditor/help/beginning/integration_ide
https://www.mql5.com/en/articles/23991