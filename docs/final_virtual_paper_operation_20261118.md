# FINAL-PAPER：楽天MT4 DEMOレートで仮想売買（Jevなし）

採用判断 FX-AI-ARCH-003: 最終テスト版と完成版の双方でJevを利用しない。
対象: USD/JPY、EUR/JPY、EUR/USD。OpenAI構築AI gpt-6.1-sol、独立検証 gpt-6-astra。
**実際のMT4発注はゼロ。デモでも実口座でもOrderSendしない。**
Python内部仮想資金は100,000円（ユーザーの楽天デモ口座5,000,000円とは完全に独立）。
本書は最終テスト版の立ち上げ手順で、実売買の安全性承認ではない。

## 1. Windows作業ツリーを最新化

    cd C:\Users\Suzuki\Documents\ChatGPT\Fx-MACRO-FWD-20261113
    if (@(git status --porcelain).Count -gt 0) { throw 'ローカル変更あり。中止' }
    git fetch origin
    if ($LASTEXITCODE -ne 0) { throw 'fetch失敗' }
    git switch --detach origin/feat/mt4-demo-final-e2e-20261117
    if ($LASTEXITCODE -ne 0) { throw '切替失敗' }
    python -m unittest discover -s tests -p "test_final_paper*.py"
    if ($LASTEXITCODE -ne 0) { throw '仮想売買テスト失敗' }

## 2. 楽天MT4デモ端末に読み取り専用EAを配置

プロジェクトの mt4/read_only/FxFinalPaperReadOnlyObserver.mq4 を
既存の楽天デモMT4のデータフォルダー内 MQL4/Experts に手動コピー。
MetaEditorのF7でコンパイルし、**0 errors / 0 warnings**を確認してから
**USDJPY H1**チャートに取り付ける。

- AutoTradingボタンはOFF、EAプロパティの自動売買許可もOFF。
- 既存の実デモ注文EA FxFinalTestDemoExecutor は使わない。
- Expertsログで以下を確認する:
  FXPAPER: read-only 60-second DEMO observation enabled; orders=0.
- 起動から約1分後、MQL4/FilesにFxPaperQuote_YYYYMMDD_HHMMSS.csvが
  1ファイル以上、同一時刻のFxDemoH1_USDJPY/ EURJPY/ EURUSDの
  120確定H1足CSVが3ファイル生成される。
- 口座番号はここでは使用しないが、デモ端末であることをEAが検査する。
  独立したサーバー時刻の真正性は未証明。

## 3. API費用ゼロで仮想売買監視を開始

既存PowerShellの $mt4Files はこのMT4の MQL4/Files の絶対パス。

    .\scripts\start_final_paper_virtual.ps1 -Mt4FilesDirectory $mt4Files

このスクリプトはユーザーのWindowsで継続稼働する。15秒ごとに
ローカルCSVを確認し、新しい1分周期の観測だけについて
仮想評価額・ポジション・決済・リスクを更新する。
成功メッセージ VIRTUAL_PAPER_CYCLE_RECORDED_RESEARCH_NO_GO が出た時点で
**仮想監視のローカル運転開始を実証できる**。初回の仮想残高は100,000円。
APIを許可しない場合は市場データ監視のみで、仮想エントリーの判断は
まだ供給されず、建玉ゼロから始まる。NO_GOは実注文禁止の意味。

Ctrl+Cで監視を安全終了。Windowを閉じると監視が停止する。
例外停止ではロックが残り、再開前の台帳・API課金確認が必要。

## 4. OpenAI二段階AIを追加して仮想売買

公式ニュースの保存済みバンドル変数 $bundles とプロセス内
OPENAI_API_KEY が存在する場合に限り、初回から明示オプトインできる。
既に無料監視中ならCtrl+Cで終了してから、同時起動せずに実行。

    .\scripts\start_final_paper_virtual.ps1 `
      -Mt4FilesDirectory $mt4Files `
      -NewsBundle $bundles `
      -AllowPaidAi `
      -MaxPaidCallsLifetime 6 `
      -AnalystModel "gpt-6.1-sol" `
      -ReviewerModel "gpt-6-astra"

最大6回は**この仮想ポートフォリオを通じた有料推論の累計上限**。
無制限の継続課金は行わない。円での料金上限ではないため
OpenAI Usageで請求見積りを確認。月額3,000円の設定を無条件に
満たす保証ではない。AI結果とAPI台帳を同一サイクルで厳格保存し、
未照合pendingなら自動リトライを禁止する。

独立検証APPROVEDかつLONG/SHORTのときだけ仮想候補にする。
**判断後の次の新しい見積もり**で仮想ポジションを開く。
APPROVED/HOLD、REVISION、REJECTED、PENDINGは売買しない。
Jev/Decisions APIへの呼び出しはない。

## 5. 仮想結果・残高の表示

別PowerShellウィンドウで、同じ開発ディレクトリに移動して実行:

    .\scripts\final_paper_status_once.ps1

証拠出力 Documents/FXForwardEvidence/final_virtual_paper/ に、
改ざん検知用チェーン付き journal/00000001.json 等と
status_*.jsonを保存する。取引損益・勝敗・停止状態・AI回数を確認。

## 実装済みの仮想安全条件

1取引の想定損失最大0.5%、同時合計1.0%、最大2ポジション。
NY17をDST考慮で日次区切り、日次損失1.5%で仮想全決済、
DD4%で新規停止、DD5%で仮想全決済と停止ラッチ。
10分超の観測途絶で新規エントリー停止ラッチ。
成行仮想約定は実bid/ask、各側に1pip仮定のスリッページ。
ストップとターゲットは観測価格で判定（ギャップは不利に反映）。
既存ポジションの仮想トレーリングは実注文でなくローカル計算だけ。

## 未達・制限

- MT4ブローカー時計・取引条件の第三者検証、全重要イベント発表前後
  15分停止の網羅性、実スワップや追加手数料の金額、取引コストの実測。
- 重要イベントの公式カレンダーおよび市場予想の事前原本保存不足。
- AI長期API料金の厳密な3,000円上限制御、1日毎の自動有料予算更新。
- 本来10秒のトレーリング監視は60秒スナップショットに限定。
- 相関に基づく3通貨ペアの詳細集中リスクは保守的な最大2件・
  合計1%だけを実装。予測利益や完成版収益は証明しない。
- 長期無人復旧、ユーザーによるフェーズ受入、MT4 MetaEditor
  実コンパイルとWindows上の実運転は別途必要。

## 安全・エラー対応

- PAPER_WAITING_FOR_FIRST_DEMO_QUOTE：EAのタイマー・Expertsログを確認。
- PAPER_WAITING_FOR_NEXT_QUOTE：新しい観測CSVが届くまで待機。
- PAPER_RUNTIME_FAIL_CLOSED_REVIEW_LOCK_AND_LEDGER：台帳・APIの課金状態を
  照合するまでロックやpendingレコードを削除せず、再起動しない。
- 既存のデモ執行EAを使わない。AutoTradingはOFFを維持し、
  テストに使うのは価格情報だけ。実デモ売買や本番売買は今回未承認。
