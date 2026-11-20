# FINAL-PAPER-157: Invalid original MT4 contract field investigation

## Actual Windows observations (2026-11-20)
- The long-run 3-pair source scan accepted 1,512 original quotes and failed
  on source ordinal 1513, FxPaperQuote_20261119_035152.csv.
- First-level code: QUOTE_OR_CONTRACT_INVALID in VALIDATE_ORIGINAL_QUOTE.
  The real failing pair and field are not yet known.
- Six saved official public originals independently passed LOCAL SHA checks.
  This is not macro schedule completeness or publisher-time attestation.

## New strict read-only classifier
- research/final_paper_quote_contract_forensics.py checks each of the
  3 original pair rows against the exact virtual-engine invariants.
- Detects crossed bid/ask, broker vs tick gap >30s, tick future,
  invalid lot minimum/maximum or step, nonpositive/invalid broker contract
  decimals, mismatched source capture and file clock, non-atomic clocks.
- Records only row number, known symbol, field name and fixed reason code,
  plus SHA256 of original bytes and nearby original verdicts.
- Never outputs raw quote values, account data, keys or absolute paths.
- Original CSV is never edited or skipped. Overall status stays NO_GO.
- Live virtual-entry engine, communication latch, paid AI 6/6, journal
  and MT4 processes are not modified.

## Windows one-shot from a separate worktree
    cd C:\Users\Suzuki\Documents\ChatGPT\Fx-PAPER-FAIL-DIAG-REVIEW-20261120
    git fetch origin
    if ($LASTEXITCODE -ne 0) { throw 'fetch failed' }
    $tree=Join-Path $env:USERPROFILE 'Documents\ChatGPT\Fx-PAPER-CONTRACT-REVIEW-20261120'
    if (Test-Path -LiteralPath $tree) { throw 'Destination exists' }
    git worktree add --detach $tree origin/feat/final-paper-invalid-contract-source-forensics-20261120
    if ($LASTEXITCODE -ne 0) { throw 'worktree failed' }
    Set-Location $tree
    .\scripts\final_paper_quote_contract_forensics_once.ps1 -Mt4FilesDirectory $mt4Files

Review issues_without_source_values for code/field/symbol/row_ordinal.
The classifier output is forensic evidence only: any original-source invalidity
continues to block STRICT multiday validation and any new virtual entry.
