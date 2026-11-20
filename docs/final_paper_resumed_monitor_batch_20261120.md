# FINAL-PAPER-138〜146: Python監視再開後の継続性・価格実測・AI隔離

ベースはPR #295。監視は2026-11-20にユーザーが手動再開したとの申告があり、
GitHub接続ではWindowsプロセスを直接参照できないため、稼働中の証明は別途必要。

## 統合した実装

1. Windowsローカル監視の前後2時点証拠
   - scripts/final_paper_verify_resumed_monitor_once.ps1 が
     同じread-only machine handoffを75秒間隔で2回採取。
   - Python紙上監視1プロセスのPID/開始時刻、MT4 terminal1、
     lock、journal最終ファイルSHA256、最新quote hash/時刻を収集。
   - research/final_paper_resumed_continuity.py が前後2点を比較し、
     同じプロセスで60〜900秒以内にquote・journalが増加したこと、
     journalハッシュ整合とAI6/6照合、通信ラッチ維持、建玉0を再監査。
   - PIDとPC時計だけで外部独立認証はできない。安全GOを出さない。

2. research/final_paper_runtime.py のAI隔離
   - 公式イベント網羅・独立時刻が未立証、通信ラッチが残存、
     600秒超gap、既知重要イベント停止中は、
     保存済み二段階AI台帳も有料AIも評価しない。
   - 価格CSVとjournal書込を優先し、H1元データ保存は続行。
   - ai_signal_pipeline_skipped_by_unattested_safety_holdで監査可能。
   - 将来の手動解除で過去H1判断の無条件再利用はしない。

3. 3通貨のquote・broker時計プロファイル
   - research/final_paper_quote_regime_profile.py では本当のMQL4/Files
     の最大240件からUSD/JPY, EUR/JPY, EUR/USDのspread
     min/median/p95/max、broker tick age、PC対broker時計差とジッター、
     最大欠測、UTC時間帯とNY17日の観測範囲を測定。
   - 3通貨原本の同時capture timestampとcontract列を厳格検証。
     不正ならfail closed。合成欠損の補完やAI課金はしない。
   - 手数料・滑り・スワップ、将来のspread、独立時刻は未証明。
     本実装からは新規virtual-entry GOを出さない。

## Windowsからのread-only確認

監視は止めない。現在Pythonが起動された作業ツリーが不明なため、
**既存Fx-PAPER-REVIEW-20261118のブランチを切り替えず**、
独立した新しいGit作業ツリーを作る。新規フォルダが既に存在したら中止：

    cd C:\Users\Suzuki\Documents\ChatGPT\Fx-PAPER-REVIEW-20261118
    git fetch origin
    if ($LASTEXITCODE -ne 0) { throw 'Fetch failed. NO_GO' }
    $newTree=Join-Path $env:USERPROFILE 'Documents\ChatGPT\Fx-PAPER-OBSERVE-REVIEW-20261120'
    if (Test-Path -LiteralPath $newTree) { throw 'Target worktree exists. NO_GO' }
    git worktree add --detach $newTree origin/feat/final-paper-resumed-continuity-20261120
    if ($LASTEXITCODE -ne 0) { throw 'Worktree creation failed. NO_GO' }
    Set-Location $newTree

過去のmt4Files変数がDEMO MQL4/Filesを指すなら、
この別PowerShellの独立レビュー用作業ツリーで：

    .\scripts\final_paper_verify_resumed_monitor_once.ps1 -Mt4FilesDirectory $mt4Files
    .\scripts\final_paper_quote_regime_once.ps1 -Mt4FilesDirectory $mt4Files

最初のスクリプトは75秒かけて2回観測し、
Python/MT4を停止/再起動しない。変化が不十分ならNO_GO。
550周期からjournalが単調増加しているかとリスク停止維持を確認する。

## 安全条件

初期10万円、1取引0.5%、同時1.0%、日次1.5%、DD4/5%、
NY17区切り、重要イベント前後15分停止、通信レベル1/2、
本人の明示解除承認を維持。
旧6/6有料AI上限は不変、MT4デモ/実口座注文は禁止。
mainマージには本人承認が必要。
