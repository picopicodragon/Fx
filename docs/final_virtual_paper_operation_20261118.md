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


## FINAL-PAPER-12〜14：2026-11-18最終確認

- 読取専用EAの実機コンパイル／USDJPY H1でのタイマー起動／
  Python監視の初回実行は **Windows実機で未実証**。GitHub CIは成功したが
  ローカル実機の運用開始を代わりに認定しない。
- 3ペアのサーバー相対時計が不整合なquote CSVは取引シミュレーションを拒否する。
- 仮説構築AIのFLATを独立検証AIがAPPROVEDにした場合、次の新鮮な
  DEMO quoteで、該当ペアの **仮想ポジション** のみ決済する。
  BROKERへの決済注文は一切発行しない。
- 既に実機で確認された FxFinalDemoBrokerSafetyProbe.mq4 の
  0 errors / 0 warnings と3ペア研究用ブローカー観測監査は、
  **新しい** FxFinalPaperReadOnlyObserver.mq4 のコンパイル成功とは別。
- **ユーザー操作の最短ルート**：mainへは自動マージせず、作業ツリーを
  origin/feat/mt4-demo-final-e2e-20261117 に更新し、上記新EAを
  MetaEditorでコンパイルしてデモUSDJPY H1へ追加。AutoTrading OFFを維持。
  Expertsログに「FXPAPER: read-only 60-second DEMO observation enabled」
  が出た後、PowerShellで以下を開始する：

      .\scripts\start_final_paper_virtual.ps1 -Mt4FilesDirectory $mt4Files

  15秒ごとの監視で VIRTUAL_PAPER_CYCLE_RECORDED_RESEARCH_NO_GO を
  見るまでは**運用開始を実証したとしない**。
- 新規有料推論を利用する場合は最初から `-AllowPaidAi` と
  `-NewsBundle $bundles`、`-MaxPaidCallsLifetime 6`、
  明示した2つのOpenAIモデルを指定する。最大6APIコールは
  自動継続を制限する上限であり、毎月3,000円の厳密な円換算予算管理ではない。
- 現在は重要イベント±15分の**独立保証された将来カレンダー**が欠ける。
  そのため仮想結果は研究上のシミュレーションであって、
  完成版の全安全停止条件を検証済みとするものではない。


## FINAL-PAPER-16〜23：AI利用枠の台帳突合と既知マクロ発表停止

Windowsローカルで実測された初期運転：監査済み21サイクル、
仮想資金100,000円、保有・決済0、AI推論使用済み6/6回、
継続quote観測とSHA256ジャーナル照合が成立した。利益・収益性の
検証が成立したわけではない。無限有料AI稼働の許可でもない。

### AI台帳を料金ゼロで読み取り照合する

現在稼働中の監視は停止せず、**別の** PowerShellで以下を実行する：

    cd C:\Users\Suzuki\Documents\ChatGPT\Fx-MACRO-FWD-20261113
    .\scripts\final_paper_ai_continuation_audit_once.ps1

新しい research/final_paper_ai_continuation_audit.py はPythonジャーナルの
累計有料コール数と、ai_research/ai_*.json の完了二段階台帳
（各2コール）を照合する。以前のHTTP401など承認済み失敗は
合算に含めず、未照合pendingは新規呼び出し禁止とする。
実際の利用料金（日本円）はAPI回数から確定できず null とする。
監査成功でも budget_renewal_authorized=false、
new_paid_inference_allowed_by_this_audit=false。
**使用済み6回の枠をリセット・増額する機能ではない。**
月額AI予算3,000円の外部請求との照合・本人の追加課金許可なく
次の有料コールを自動で開始しない。

### 既知の重要マクロイベントだけを追加停止する（任意・読取専用）

research/final_paper_event_blackout.py はローカルで保存した
fx_final_paper_known_macro_blackout_v1 形式のイベント一覧を読み、
USD/EUR/JPYの重要発表±900秒に入ったサイクルでは、新規仮想
エントリーと有料AI分析を止める。仮想損切り・利確・決済は継続。
APIアクセス、MT4発注、Webカレンダー取得は行わない。

カレンダーを手元で公式原本と照合できた場合、起動コマンドへ
-EventBlackoutFile <検証済みJSONのローカルパス> を追加できる。
JSONトップレベル必須：schema、captured_at_utc_pc（UTC時刻）、
scope=OPERATOR_SAVED_RESEARCH_ONLY、events配列。イベント要素は
id、currency（USD/EUR/JPY）、scheduled_at_utc（UTC時刻）、
source_url（許可済み公的ドメイン）、importance（HIGH/CRITICAL）。
JSON自体に個人情報・APIキーを入れない。未照合原本や架空の日付を
公式カレンダーとして入力しない。

ファイルが提供されなかった場合、既知ブラックアウトは起動しないが
independent_future_event_calendar_attested=false を出し続ける。
ファイルを渡しても**3通貨全イベントの網羅性・情報取得時刻・
ブローカー時計の独立証明は行われない**。そのため、仮想損益は
研究結果であって完成版のイベント停止条件の合格とは認定しない。
渡したファイルが不正、期限切れ、不明ソースの場合はFail Closed。

現状のWindows監視プロセスは、ソースを更新しても自動的に
新機能へ切り替わらない。既存の監視を維持し、次の停止・起動時に
最新版でオプションを使用する。例外停止した場合はロックや
有料AI台帳を削除しない。


## FINAL-PAPER-25〜27：106サイクル・AI 6/6回到達後の無課金監視と再確認

利用者実機から報告された2026-11-18 13:09時点の台帳監査は
PAPER_AI_COUNTER_RECONCILED_BILLING_UNVERIFIED_NO_GO、
journal_cycles=106、completed_two_model_ledgers=3、
paid_calls_recorded_in_journal=6、paid_calls_in_completed_ledgers=6、
previous_401_rejections_manually_reviewed=0（**本paper用台帳のみ**）、
remaining_calls_under_existing_limit=0。課金推定額は未立証。

本変更は運用ステータスの無料読み取りに次を追加するだけ。
既存のSHA256チェーン・仮想ポジション・有料AI台帳は変更しない。

- last_recorded_quote_age_seconds_pc_derived：最後の保存済quoteの
  観測時刻と現PC時計の差。PC時計の独立認証は行わない。
- price_stream_warning_level_pc_derived：quote未捕捉時NO_CAPTURE、
  60秒未満FRESH、60〜599秒LEVEL1、600秒以上LEVEL2。
- paid_ai_calls_remaining_under_current_limit：上限6回の未使用件数。
  6/6なら0。api_cost_jpy_verified=false、
  api_budget_renewal_authorized=false、new_paid_ai_calls_authorized_by_status=false。
- quote_recent_enough_for_further_paper_evaluationは観測鮮度と
  状態ラッチから導いた参考診断であり、AI呼出し許可・発注許可
  または取引シグナルではない。
- 監視中に古い価格が継続した場合は再度statusでLEVEL1/LEVEL2を
  確認する。STATUSコマンド自体は通信停止ラッチを永続化しない。
  次に新しいquoteが到着した際、既存paper engineがgap>=600秒を
  検出して通信停止ラッチを立てる。手動でのラッチ解除は行わない。

利用者のWindows監視稼働中のオリジナル作業ツリーを更新しない。
**別途作成済みFx-PAPER-NEXT-20261118** だけを更新して、
以下で読み取り専用の監視状況を確認する。

    cd C:\Users\Suzuki\Documents\ChatGPT\Fx-PAPER-NEXT-20261118
    if (@(git status --porcelain).Count -gt 0) { throw '作業ツリーがdirty' }
    git fetch origin
    if ($LASTEXITCODE -ne 0) { throw 'fetch失敗' }
    git switch --detach origin/feat/mt4-demo-final-e2e-20261117
    if ($LASTEXITCODE -ne 0) { throw 'checkout失敗' }
    python -m unittest discover -s tests -p 'test_final_paper*.py'
    if ($LASTEXITCODE -ne 0) { throw '単体テスト失敗' }
    .\scripts\final_paper_status_once.ps1

同時監視プロセスを増やさず、追加有料AI呼び出しを行わない。


## FINAL-PAPER-29〜31：2026-11-18 13:42 実機の2020秒quote停止調査

本人のローカルread-only statusは、
completed_cycles=106、paid_ai_calls_lifetime=6/6、
last_recorded_quote_age_seconds_pc_derived=2020、
price_stream_warning_level_pc_derived=LEVEL2、
quote_recent_enough_for_further_paper_evaluation=false、
communication_latched=falseだった。

この場合、保存済みのjournalが正常であることと、
**継続した価格供給・仮想評価が正常であることは別**。
停止ラッチは新しいquoteが到着した次のpaper engineサイクルで
ギャップを計測するため、単にstatus照合しても更新されない。
既存監視プロセスは停止・重複起動・ロック削除しない。

独立したread-only切り分けツールを追加した。
既存のFx-PAPER-NEXT-20261118ワークツリーだけを最新化した後、
MT4のMQL4\Filesの実パスを指定して実行する。

    .\scripts\final_paper_stream_diagnostic_once.ps1 -Mt4FilesDirectory $mt4Files

出力に含むのは journal最終処理quoteのPC由来経過秒数、
MT4側最新FxPaperQuote CSVのPC由来経過秒数、OSファイル変更時刻、
running状態未証明のlock存在有無、6回利用枠は新規課金なし、
売買許可なしといった診断メタデータのみ。

診断の主なパターン：

- MT4_OBSERVER_QUOTE_STREAM_STALE：最も新しいMT4 quote CSV自体が
  600秒以上古い。楽天デモMT4の接続・Expertsログ・USDJPY H1の
  FxFinalPaperReadOnlyObserverが起動中か確認。価格が途絶える理由は
  実機ログがない限り確定できない。
- FRESH_MT4_QUOTES_NOT_PROCESSED_BY_PYTHON：最新CSVは120秒以内だが、
  journalがそれを処理していない。Python監視を表示している
  PowerShellウィンドウの終了・FAIL_CLOSED・ロック存在を確認。
  **ロックがあるだけではプロセス稼働証拠にはならない**。
  journal/AIの再送・再起動は手動監査が済むまで禁止。
- UNPROCESSED_MT4_QUOTES_ALREADY_STALE：最新CSVが処理されず、
  既に120秒を超えている。MT4/監視の双方を確認する。
- MT4_OBSERVER_HAS_NO_QUOTE_CSV：quote CSVなし。EA装着・MetaEditor
  コンパイル・Expertsログ、指定した正しいデモMQL4\Filesを確認。
- LATEST_MT4_QUOTE_ALREADY_PROCESSED：最新のCSVがjournalに反映済み。
  **今も稼働中かどうかは別途実機確認が必要**。
- QUOTE_ARCHIVE_BEHIND_JOURNAL_REVIEW：入力フォルダーを含む
  ローカル証拠が逆行しているため、ファイルの差し替えや
  MT4別フォルダーへの接続を疑い、操作を止めて照合する。

新ツールは読み取り専用であり、停止ロック・台帳・通信障害ラッチの
解除、未知AI課金の再試行、デモ/実口座の注文を行わない。
既存の6/6回有料推論上限も不変。正常復旧の前に新規エントリーを
始めないこと。MetaEditorの実機確認・専門家ログはユーザーが実施。


## FINAL-PAPER-33〜36：2026-11-18 13:54のPython消費側停止後の安全な初期復旧

利用者の読み取り専用診断で確定した範囲：

- diagnosis=FRESH_MT4_QUOTES_NOT_PROCESSED_BY_PYTHON
- journal_cycles=106、Python最終処理時刻は2713秒前
- MT4生CSVは13秒前に新規保存、前回ジャーナルより新しい
- runtime_lock_present_not_process_proof=false
- MT4注文ゼロ、AI追加ゼロ、既存有料AI累計6/6

従って**MT4観測側のCSV生成は継続し、Python監視側が最新CSVを
消費していない**。ただし、Pythonプロセスが実際に終了しているか、
なぜ停止したのかはログがない限り確定しない。

別PowerShellで更新済みの Fx-PAPER-NEXT-20261118 作業ツリーを使用：

    .\scripts\final_paper_free_resume_preflight_once.ps1 -Mt4FilesDirectory $mt4Files

このコマンドはWindowsのWin32_Processで全python/pythonw/pyプロセスを
列挙し、research.final_paper_runtimeに一致する実行中プロセスが
**一つでもあれば即停止**。列挙権限不足でもfail-closed。
単独運用ロックが残っていれば停止し、削除しない。
次に既存の読取専用診断・AI台帳照合・ジャーナル状態を再評価し、
120秒以内の最新quote、仮想ポジション0件、AI台帳整合を要求。
既存のAPI累計6/6は更新しない。新規有料AIを許可しない。
監査結果は既存のjournalやai_researchを書き換えず、
free_resume_preflight_*.jsonを新しく保存する。

FREE_OBSERVATION_ONLY_RESTART_CANDIDATE_NO_GOが得られ、
既存の監視PowerShellが終了していることも操作者が確認できた場合は、
**無料の監視だけ**を自分の判断で再開することができる：

    .\scripts\start_final_paper_virtual.ps1 -Mt4FilesDirectory $mt4Files

この再開では新しいquoteを1件処理し、保存済みquoteとのギャップが
600秒を超えるため VIRTUAL_COMMUNICATION_LEVEL2_LATCHED が
ジャーナルに永続化されることが予想される。
**人間承認を要する通信停止ラッチを自動で解除しない**。
そのまま無料の観測・証拠保全は継続できるが、新規仮想
ポジションは開かない。通信回復後の新規売買再許可は
別途本人承認・停止原因分析・安全審査が必要。

Ctrl+C停止からの予定どおりの終了だった場合も同様に、
以前の空白期間をなかったことにせずラッチを維持。
既存paperのデータ・API台帳・ロックを手動削除しない。


## FINAL-PAPER-38〜41：121サイクル到達後の通信停止解除前審査（読取専用）

2026-11-18 14:20頃のユーザー実機監査：
completed_cycles=121、last_recorded_quote_age_seconds_pc_derived=51、
price_stream_warning_level_pc_derived=FRESH、
communication_latched=true、取引0件、cash/equity=100,000円、
AI利用6/6回、追加API許可なし、MT4発注0件。

106回から121回へ15サイクル増加したことは、価格供給・journal
追加が正常に復旧したことの証拠。ただし FRESH=価格が新しい
だけで、障害原因の究明・解除許可・AI費用の承認を意味しない。

最新版worktree Fx-PAPER-NEXT-20261118 で、既存の監視PowerShellを
止めずに別ウィンドウから以下を実行：

    .\scripts\final_paper_comm_recovery_review_once.ps1

審査は先頭から全journal SHA256チェーンを読み取り検証し、
最後の10件以上の連続記録（30〜90秒の観測間隔、既存ラッチがtrue）、
直近quoteがPC時計由来で120秒以内、他の損失/DDラッチ不発動、
未決済仮想建玉なし、保留AIシグナルなしを確認する。

- status=COMM_RECOVERY_EVIDENCE_REVIEW_ONLY_NO_GO
- ready_for_manual_root_cause_review=true となっても
  **通信停止解除が承認されたわけではない**。
- root_cause_explained=false、通信ラッチはtrue、実/デモ注文は禁止。
- API利用6/6回・未検証の月額料金・独立未検証の経済カレンダーなどの
  未達事項は別の承認条件。審査が新しい有料API呼出しを許可しない。
- 停止ロック、journal、仮想ポジション、運用ラッチ、
  AI台帳は読み取りのみ。出力先に別名の監査レポートJSONを新規作成。
- エラー・データ競合・元データ破損はfail closed。
- 停止原因（Ctrl+C、Windowsターミナル終了、Python例外、その他）
  はログから別途特定する。自動ラッチ解除は設計・実装しない。

現在の最終テスト版は「無料価格観測復旧済み／新規仮想売買停止中」の
状態を維持する。理由が不明な停止を再発させないための開発が必要。


## FINAL-PAPER-43〜47：138サイクル復旧審査後のPython監視停止原因の証拠収集

利用者が実機で確認：最終テスト63件成功、
communication recovery review: journal_cycles=138、
直近連続10件合格、最終quote経過55秒（FRESH）、
ready_for_manual_root_cause_review=true、communication_latched=true、
root_cause_explained=false、paid_ai_calls_lifetime=6/6、
仮想建玉/保留シグナル0、デモ/実売買注文0。

この結果は**新規仮想売買を再許可する承認ではない**。
重要なのは、Python監視の約45分の停止が何によるものか
実機で原因証拠を集めること。停止の背景について、
CLIによるCtrl+C終了、PowerShellウィンドウ終了、Python例外、
Windows再起動、その他のいずれかを断定しない。

最新ソースを安全な別ワークツリーに取得したあと、
監視中のターミナルを閉じずに、別PowerShellから実施する。

    .\scripts\final_paper_interruption_forensics_once.ps1

当該スクリプトは既存のハッシュ鎖を読取検証し、
直近最大1024サイクル内に記録された最新の600秒超の欠測について、
停止直前・再開直後のPC時刻および欠測秒数を特定する。
その時刻周辺のWindows Systemイベント
（41、1074、6005、6006、6008）と
Applicationイベント（1000、1001）の**IDと発生時刻だけ**を
ローカルで抽出・保存する。イベントのメッセージ本文、ユーザー名、
APIキー、プロセスのコマンドラインは保存・公開しない。

出力は以下の2ファイルに分ける。
- interruption_timeline_*.json：
  ジャーナル上の欠測箇所、秒数、最新の安全停止状態。
- interruption_windows_events_*.json：
  WindowsログのイベントID・時刻・照会可否のみ。

「Windowsイベントの存在」はPythonの異常終了の直接の証明ではなく、
同時刻周辺に発生した現象を示すのみ。何も出ない場合も
ログの閲覧許可や記録有無の違いがあり、正常終了を断定しない。
Linux CIとWindows CIの通過は実機イベント取得の成功ではない。

**停止ラッチ解除、Pythonプロセス再起動、MT4注文、有料AI呼び出し、
運用journal・AI台帳・単独運用ロックの変更を一切実施しない。**
根本原因が判明しない場合は unknown のまま停止ラッチ維持。


## FINAL-PAPER-49〜52：2026-11-18 13:38 のApplicationイベントID1001の限定調査

ユーザーがWindows実機から報告したCSV・journal照合情報：
- 106→107サイクル間の無観測は3420秒（57分）。
- 直近153サイクル、復旧後の47サイクル観測、latest quote47秒。
- Applicationログ：2026-11-18T13:38:04.122+09:00、
  13:38:06.196+09:00 にEvent ID1001が2件。
- Systemログ：NO_MATCH_OR_NOT_ACCESSIBLEであり、
  「該当イベントなし」と「読み取りできない」を区別できない。
- Windowsアプリ1001はWER等が記録することがあり、イベント
  IDだけではPythonプロセスの異常終了は証明できない。
- 欠測直前のquote時刻13:08:51 JST、再開直後14:05:51 JSTであり、
  Application 1001は欠測の約29分後に発生、直後の障害ではない。

次の追加調査は、Windows Applicationログの13:30〜13:45について
Event ID 1000/1001/1002の発行元カテゴリと、
XML EventDataの限られたAppName/P1/param1等の要素から
匿名化したアプリ種別だけを抽出する。

    .\scripts\final_paper_wer_1001_focus_once.ps1

出力：wer_1001_metadata_*.json。保存するものはイベントID、
ローカル時刻、発行元カテゴリ、既知プロセスの種別
(PYTHON/POWERSHELL/WINDOWS_TERMINAL/MT4_TERMINAL_POSSIBLEなど)、
許可済みのイベント種類だけ。イベント本文・元のXML・フルパス、
コマンドライン、ダンプ情報、固有識別子を保存しない。
イベントID1000などが当該時間帯にない場合も、取りこぼしなく
「全Windowsログを検証した」とはみなさない。

診断スクリプトは既存のMT4、Python監視、journal、単独ロック、
通信ラッチ、API台帳、仮想証拠へ変更を加えない。
判定は WER_METADATA_INSPECTION_ONLY_NO_GO であり、
root_cause_explained=false、通信停止ラッチ=true維持、
AI利用6/6で追加課金なし、実/デモ売買も禁止。

EventID 1001 と実際のPython停止との因果関係が確定できない場合は
原因 UNKNOWN のまま安全停止を継続する。
