# FINAL-AI-INTEGRATION：AI判断、安全停止、仮想売買、AI費用管理の一括接続（2026-11-20）

## 現状とゴール

実機の最終テストV1はWindowsで14:46 JSTに稼働確認済み。
ジャーナルは711→712、Python監視・MT4各1プロセス、AI既存6/6、
通信停止ラッチ有効、実仮想建玉0。
過去のMT4原本3,020件に時刻逆転4件。修正版EA V2はまだ実機未導入。
取得済みBLS/FOMC/ECB/BOJ/楽天×2の公式原本6件はローカルSHA一致。
これらを「完全AI仮想売買GO」と混同しない。

今回の新実装は、**すでに存在する**closed-H1→公式RSS/ニュース原本→
2モデル分析・レビュー→承認シグナル→3通貨ペア仮想ポジション計算
の連結を、包括的なNO_GOゲート・費用境界・実機証拠診断により補強する。

## コード変更

- research/final_paper_integrated_control.py
  - USDJPY/EURJPY/EURUSDの各通貨について、価格時刻逆転・>600秒欠測、
    重要指標の前後15分、USD/EUR/JPY公式重要イベント網羅、
    発表前コンセンサス証拠時刻、broker/PC独立時刻、
    spread/slippage/swap費用モデル、候補EA V2単独起動証明を要求。
  - 通信ラッチ、DD4%、DD5%、日次損失停止のすべてを評価。
  - 旧AI 6/6は不変。新しい有料2モデルの呼び出しには、月額上限の
    本人承認、provider側hard cap、円建て実請求の独立照合、
    次2呼出しの**最悪額**を差し引いた予算、月次呼び出し上限を別管理。
  - 月額3,000円は過去方針の設計上限。**新API費用の承認ではない**。
    模擬テストで条件Trueを指定しても、実際のdispatcher許可は返さない。

- research/final_paper_runtime.py
  - 現在の稼働スーパー バイザの**将来の実行コード**に統合ゲートを組込み。
    既存の証拠不足を入力した結果、AI保存シグナル評価・新規有料AI呼び出しを
    さらにfail-closedで遮断。元のpaper.stepとリスク構造・journalスキーマは
    変更しない。
  - 実機稼働中のPythonプロセスはGitHubへのコミットだけでは変わらない。
    この修正を実機へ反映するには、別途安全な停止/再開と既存ジャーナル検査が必要。
  - コード上の独立 verifier がまだない限り、
    calendar/clock/consensus/cost/EA識別を全てFalse扱いする。
    これを環境変数・手書きJSON・API opt-inだけで解除できない。

- research/final_paper_integrated_rehearsal.py
  - 実MT4原本を読み、closed source verificationを通した後、
    合成2モデル承認シグナル形式を3通貨ペア別に仮想risk engineへ入力する。
  - AIの判断ではなく**独立メモリのみ**の機能テスト。
    仮想建玉が生じる場合も、本物のjournalに書かず、API/発注0。
  - Unit testsで完全仮説証拠を注入した成功ケース、
    指標ブラックアウト、通信/DD停止、DD・日次上限、
    0.5% riskと1%合計上限を検査できる。

- research/final_paper_integrated_readiness.py
  - 動いているjournalのハッシュ連鎖、旧有料AI6/6 ledgerと完了状態、
    現在の実価格CSV、公式6原本のSHA一致を再検証。
  - 具体的な未充足ゲートを一覧化するread-only JSON。
    保存済み公式文書のハッシュだけで「イベント網羅・発表前予想」
    が証明されたとは扱わない。

- scripts/final_paper_integrated_ai_virtual_once.ps1
  - Windowsから実機の現在のAI運用準備判定＋
    元CSVによる3通貨の隔離シミュレーションを連続で実施。
  - どちらか失敗したら全体NO_GO。新JSONだけを作る。
  - 二重Python起動、EA切替、通信ラッチ解除、AI課金、broker発注はしない。

## 実施できない安全解除と運用移行

**現時点では完全AI仮想売買の新規ポジションは依然禁止**。
なぜなら実機に客観的な独立イベント全網羅/コンセンサス、
clock、spread/slippage/swap、V2 MetaEditor compilation、
通信38時間停止の正式な最新解除、provider実請求と新予算承認がないから。

AIを動かす前に：
1. MT4候補V2のMetaEditor 0 errors、旧EA単独停止、1個の新EA起動、
   ExpertsログのV2識別タグと開始時刻を保存。
2. 実測イベント・事前コンセンサス・時計・費用の**外部真正性**を
   ソースと時刻に紐づけて検証する検証器を実装、最新証拠でテスト。
3. 旧38時間通信停止を、過去106→107番の停止とは分離して審査し
   本人の当該事故限定の解除承認を受ける。
4. 新API月額/2モデル呼出しの本人承認、provider cap、
   provider実費照合と最悪額予約を実装、実請求上限を証明。
5. 全本番インストール後の再開計画とhead整合をレビュー。
   この段階で初めて有料AIや仮想建玉への実際の許可を検討する。

## Windows側の読取実行

    cd C:\Users\Suzuki\Documents\ChatGPT\Fx-PAPER-FINAL-TEST-REVIEW-20261120
    git fetch origin
    if ($LASTEXITCODE -ne 0) { throw 'fetch failed' }
    $tree=Join-Path $env:USERPROFILE 'Documents\ChatGPT\Fx-PAPER-INTEGRATED-REVIEW-20261120'
    if (Test-Path -LiteralPath $tree) { throw 'Destination exists. Stop.' }
    git worktree add --detach $tree origin/feat/final-paper-integrated-ai-gates-budget-20261120
    if ($LASTEXITCODE -ne 0) { throw 'worktree failed' }
    Set-Location $tree
    .\scripts\final_paper_integrated_ai_virtual_once.ps1 -Mt4FilesDirectory $mt4Files

結果はfinal_integrated_readiness_*.json、
final_integrated_rehearsal_*.jsonの2ファイル。
提出するのはmetadata-onlyの全体ステータスと
remaining_independent_review_requirements、three_pair_statusesなどでよい。

mainマージは有人承認のみ。リアルデモ/本番への発注は禁止。
既存監視を止めない。必要性のない新規有料AI呼出しをしない。
