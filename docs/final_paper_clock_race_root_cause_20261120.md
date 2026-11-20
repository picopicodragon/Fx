# FINAL-PAPER-158〜163: Original MT4 DEMO quote clock race

## User's physical evidence, 2026-11-20

- Original failing file: FxPaperQuote_20261119_035152.csv
- SHA256: 3b272c81b794a12776319c8947d813f82540067b17049f022e33761833ca9505
- Total original bytes: 626
- The 1,513th file failed after 1,512 validated originals.
- Row 1 USDJPY: TICK_TIME_AFTER_BROKER_TIME
- Row 2 EURJPY: TICK_TIME_AFTER_BROKER_TIME
- Row 3 EURUSD had no reported timing violation.
- Adjacent original 4 files validated individually; all preserved.
- All six saved official public documents passed local SHA comparison.
- Real new virtual entries and paid AI remain NO_GO.

## Source-level root cause *candidate*

Existing mt4/read_only/FxFinalPaperReadOnlyObserver.mq4 used
OnTimer() brokerNow=TimeCurrent(), then checked MODE_TIME per pair in one
pass, and later called MarketInfo(MODE_TIME) AGAIN during FileWrite.

MQL4 TimeCurrent in OnTimer is the latest Market Watch quote timestamp,
whereas MODE_TIME is the specific symbol's last incoming tick timestamp.
An intervening market tick may update MODE_TIME between validation and
write. The CSV can then contain a tick time beyond the earlier sampled
brokerNow despite the first check passing.

References (official MetaQuotes):
- https://docs.mql4.com/en/dateandtime/timecurrent
- https://docs.mql4.com/en/constants/environment_state/marketinfoconstants

This is an observed source-code time-of-check/time-of-use risk that
explains the user anomaly, but cannot prove the precise hardware event
without independent MT4 trace logs.

## Proposed EA correction (SOURCE CODE ONLY, NOT DEPLOYED)

- Keep the identical external CSV header, file naming and DEMO H1 scope.
- Read each market bid, ask, MODE_TIME, MODE_TICKVALUE, MODE_TICKSIZE,
  MINLOT/STEP/MAXLOT, POINT and DIGITS once into local arrays.
- Sample TimeCurrent *after* three pair values have been collected.
- Reject the entire snapshot if any tick is ahead of the final broker
  reference timestamp or older than 30 seconds. Do not create CSV.
- Write precisely the cached validated values; NO live MarketInfo calls
  inside the FileWrite loop.
- Retain IsDemo, IsConnected, account JPY, USDJPY H1, local-only I/O,
  no OrderSend/OrderClose/DLL/WebRequest and fail-closed behavior.
- No on-machine recompilation or hot replacement has been performed.
  GitHub Python CI is NOT MetaEditor/MQL4 compilation. Any future demo
  install, manual compile, EA replacement and process handoff require
  separate operator authorization and original EA shutdown plan. Never
  attach two observers simultaneously to the same MQL4/Files folder.

## Research-only full original timestamp campaign

Use the new final_paper_quote_time_order_campaign read-only tool:

- Validate up to 10,080 original 3-pair quote CSV files.
- Count ALL future tick vs recorded broker-time anomalies by symbol,
  and give max derived lead seconds without raw timestamps/prices.
- List only the first 25 invalid original names + SHA256 and issue codes.
- Count invalid originals and valid contiguous segments separated by
  missing minutes (>90 seconds) and invalid files.
- Create a single ordered SHA256 fingerprint over all selected originals.
- Keep all original files in place. Continue scanning after a bad file
  FOR DIAGNOSTICS only, never to silently approve the overall dataset.
- Even 0 anomalies does not independently verify broker clock,
  macro consensus, simulated fill costs or market data completeness.
- Final status remains RESEARCH_NO_GO and no virtual entry permission.

## Windows no-process-change read-only handoff

Do not switch branches in any worktree from which the existing Python
monitor or MT4 EA is being run. A new separate worktree is safe:

    cd C:\Users\Suzuki\Documents\ChatGPT\Fx-PAPER-CONTRACT-REVIEW-20261120
    git fetch origin
    if ($LASTEXITCODE -ne 0) { throw 'fetch failed' }
    $tree=Join-Path $env:USERPROFILE 'Documents\ChatGPT\Fx-PAPER-CLOCK-REVIEW-20261120'
    if (Test-Path -LiteralPath $tree) { throw 'destination exists' }
    git worktree add --detach $tree origin/fix/final-paper-mt4-quote-snapshot-race-20261120
    if ($LASTEXITCODE -ne 0) { throw 'worktree add failed' }
    Set-Location $tree
    .\scripts\final_paper_quote_time_order_campaign_once.ps1 -Mt4FilesDirectory $mt4Files

Output: quote_time_order_campaign_*.json within existing state root.
Sharing the printed summary's invalid source count, per pair future
tick counts, derived leads, and first anomalies does not require sharing
raw broker quotes or credentials.

## Firm NO_GO constraints

Communication latch for the previous 38h interruption remains set,
original AI budget 6/6 remains exhausted, the independent clock, full
USD/EUR/JPY event+pre-release consensus calendar, real transaction
costs and approved live virtual signals are not attested.
No actual demo/real orders or unauthorized paid calls.
Main merges require explicit user action.
