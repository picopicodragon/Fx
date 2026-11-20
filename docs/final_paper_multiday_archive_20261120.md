# FINAL-PAPER-147〜155：再開後の複数日実価格と公式原本の保全検査

## 2026-11-20 12:31 JST 実機での結果

- Python監視1プロセス/MT4 terminal1プロセスが75秒の2点で同一。
- 576→578の2周期をjournalに追記、先頭からハッシュ整合。
- 有料AI台帳6/6、通信ラッチtrue、他リスク停止なし。
- 240周期CSVは全て60秒間隔で欠測なし。
- broker時計とPC captureの見かけ差は7200秒固定。独立時刻証明ではない。
- NY17取引日バケットは1件のみ。
- USD/JPY: median 0.5pips、最大1.6pips（3.2倍）
- EUR/JPY: median 1.0pips、最大2.4pips（2.4倍）
- EUR/USD: median 0.5pips、最大1.1pips（2.2倍）
- 今回観測最大値は将来スプレッドの上限保証でも実約定コストでもない。

## 実装

1. research/final_paper_multiday_quote_stress.py
   - 元MQL4/FilesのCSVを最大10080周期まで読み取り、全件で
     3通貨ペア、同一PC capture、bid/ask、broker contractを元validatorで検査。
   - 全体のspread min/median/p95/p99/max、中央値2倍以上の出現回数、
     最大連続周期数、broker tick age、PC対broker offset/jitter、
     quote gapの90秒/600秒超回数、NY17別の観測回数とspread、
     UTC観測時間帯の広がりを算出。
   - 3 NY17日と12 UTC時間帯は研究カバレッジ指標。GO判定ではない。

2. research/final_paper_official_archive_integrity.py
   - 取得済み6原本（BLS ICS、FRB、ECB、日銀、楽天ルール、
     楽天のスプレッド・スワップ公開資料）を保存manifestと突合。
   - 原ID、元URL、保存長、SHA256、PC保存時刻、重複・追加ファイル、
     シンボリックリンクを検査。不一致・部分欠損はfail closed。
   - 原本のローカルハッシュは発行主体の独立認証、重要経済イベントの
     完全網羅、発表前consensusの存在証明と同じではない。

3. scripts/final_paper_multiday_macro_integrity_once.ps1
   - Windowsの別PowerShellから両検査を1回実行し、報告JSONを2件保存。
   - 停止中の安全ラッチや監視プロセスを変更せず、API0、注文0。

## Windows操作

**稼働中監視と既存の観測レビュー用worktreeを切り替えず**
別worktreeを作る。最初のPowerShell:

    cd C:\Users\Suzuki\Documents\ChatGPT\Fx-PAPER-OBSERVE-REVIEW-20261120
    git fetch origin
    if ($LASTEXITCODE -ne 0) { throw 'Fetch failed' }
    $tree=Join-Path $env:USERPROFILE 'Documents\ChatGPT\Fx-PAPER-MULTIDAY-REVIEW-20261120'
    if (Test-Path -LiteralPath $tree) { throw 'Destination exists' }
    git worktree add --detach $tree origin/feat/final-paper-multiday-macro-provenance-20261120
    if ($LASTEXITCODE -ne 0) { throw 'Worktree creation failed' }
    Set-Location $tree

過去と同じ $mt4Files が実DEMO MQL4/Filesを指している場合：

    $official=Join-Path $env:USERPROFILE 'Documents\FXForwardEvidence\final_virtual_paper\official_public_capture_20261120_113041_303'
    .\scripts\final_paper_multiday_macro_integrity_once.ps1 -Mt4FilesDirectory $mt4Files -OfficialArchiveDirectory $official

元のMT4 CSVが240周期分でも実行可能。データが増えれば
研究カバレッジも伸ばせるが、それだけでGOにはならない。

## 現在も未達

- 通信ラッチは新38時間停止に対する解除承認がなく有効。
- 重要イベントの独立した全網羅・発表前consensus・安全停止前後15分。
- ブローカー時刻の第三者照合。7200秒の一定offsetは独立証明ではない。
- 実約定の滑り・スワップ、完全な取引コスト。
- 有料AI上限6/6、実際の月3000円API費用と新予算の明示承認。
- 新規仮想ポジション、デモ・実注文はNO_GO。

mainマージ、ジャーナル変更、監視停止、無断AI課金、ブローカー発注なし。
