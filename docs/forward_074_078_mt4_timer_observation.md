# FWD-074〜078：既存楽天MT4デモ3ペア・継続読み取り専用観測（準備のみ）

## 初回実測（ユーザー提供 2026-11-10）
既存単一の楽天MT4デモターミナルでMQL4 v3単発CSVを3つ生成。以下は**ユーザーが貼り付けた**値であり、こちらは元CSVのバイト列、口座ログイン状態、時刻ソースを独立認証していない。

| ペア | UTC自己申告観測時刻 | Bid / Ask | スプレッド | サーバー相対tick_age |
| --- | --- | --- | --- | --- |
| USD/JPY | 05:33:32Z | 157.940 / 157.945 | 0.5 pip | 1s |
| EUR/JPY | 05:32:34Z | 177.361 / 177.371 | 1.0 pip | 0s |
| EUR/USD | 05:33:28Z | 1.12280 / 1.12285 | 0.5 pip | 1s |

USDJPY価格参照157.941はEURUSD観測時の自己申告。USDJPY個別観測より4秒早く、完全同期の裁定価格テストには使用しない。記録上 server_now_time がPC由来のobserved_at_utcより約2時間進んでいるが、ブローカーUTCオフセットの正式確認ではない。価格列は既存厳格パーサで受入済み。遅れて再検査すると3ペアともSTALEになるのは現在価格として扱えないためであり、歴史的な観測証拠を破棄する理由ではない。

## 今回の開発（実機未実行）
- **FWD-074:** `FxForwardDemoTimerObserver.mq4`。従来の単発Scriptとは別に、USDJPYチャートに1個だけアタッチする読み取り専用Expert Advisorソース。既存デモ口座、接続、チャートをOnInitとOnTimerで検査する。EAには取引API、DLL、WebRequestはない。AutoTradingをOFFに維持。
- **FWD-075:** `research.forward_mt4_timer_observer_review`。注文APIや共通フォルダー、対象外通貨ペア、上書き防止欠落、タイマー停止欠落などを静的検査する。ただしソーステキスト上の検査はコンパイル・実動作証明ではない。
- **FWD-076:** MQL4のEventSetTimer(60)によって**60秒ごと、最大30タイマー周期だけ**実行。3ペア全ての価格/ティックが整合しない周期は全スキップ。出力先は既存端末内のMQL4/Filesで、個別CSVのファイル名が衝突した場合は周期をスキップする。ディスク障害時は一部ペアだけファイルが残り得るため、欠損をPython側で検出する。
- **FWD-077:** 生成する3ペア分CSVは従来v3/v2パーサと同じ10列。円換算のUSDJPYは同一タイマー周期のBidを用い、PC由来TimeGMTをUTC自己申告として記録。タイマー停止/再接続の完全性は実機未検証。
- **FWD-078:** スコープ/ソース・禁止API・タイマー/期間上限・上書き拒否の回帰テスト。GitHub ActionsはMQL4の本物のMetaEditorコンパイルではない。

MQL4公式仕様：
- OnTimerは**Expert Advisorsおよびインジケーターのみ**で使える。Scriptsでは使えない。<https://docs.mql4.com/basis/function/events>
- EventSetTimerはOnInit、EventKillTimerはOnDeinitで処理する。<https://docs.mql4.com/eventfunctions/eventsettimer>
- MT4「自動売買を許可」OFFでもEAの分析処理は稼働し、取引操作は禁じられる。<https://www.metatrader4.com/ja/trading-platform/help/autotrading/experts/experts_setup>

## マージ後のWindows＋MT4を1工程として実施（実機アクセスはユーザー側）

0. 今回のPRを本人がマージしてからWindows PowerShellで:
```powershell
cd C:\Users\Suzuki\Documents\ChatGPT\Fx
git switch main
git pull --ff-only origin main
python -m research.forward_mt4_timer_observer_review --source research/mt4_readonly/FxForwardDemoTimerObserver.mq4 --out out/mt4_timer_observer_source_review_001.json
```
出力先がすでに存在する場合は別の未使用ファイル名を指定する。static_preflight_passed=trueとNO_GOを確認。

1. 既存の**一つの楽天MT4デモ端末**で「ファイル→データフォルダを開く→MQL4→Experts」を確認。通常の`Scripts`ではない。既存EA（MACD Sampleなど）の動作状態、建玉/未約定注文、端末「自動売買」OFF、口座がDEMOであることを明示的に確認する。別端末/別口座の同時ログインは禁止。
2. `research/mt4_readonly/FxForwardDemoTimerObserver.mq4`のソース・SHA256・注文APIなしを目視し、`MQL4/Experts`へ**手動コピー**する。同名ソースが既にあれば確認せず上書きしない。
3. MetaEditorから対象ソースを開きF7コンパイル。**0 errors**を確認。EX4が生成されたことと最新版のソースを使ったことを確認。エラーや想定外の警告があれば使用しない。
4. MT4のUSDJPYチャート**1枚だけ**に「ナビゲーター→エキスパートアドバイザ」から`FxForwardDemoTimerObserver`を手動アタッチする。ほかの2チャートに同時アタッチしない。AutoTradingはOFFのまま、DLL/外部通信許可はOFF。
5. タイマーは60秒ごと。最大30タイマー周期後はEventKillTimerにより停止。Expertsログの`FXFWD_OBSERVER`メッセージ、MQL4/Filesの`FxFwdV3_USDJPY_*`,`FxFwdV3_EURJPY_*`,`FxFwdV3_EURUSD_*`の生成を観察。通信断・価格停止・タイムゾーン異常でファイルが生成されない場合は原因を記録。既存のv3単発CSVは上書きしない。
6. 観測終了時にEAをチャートから**手動で外す**。3ペアのCSVを端末外のプロジェクト`out`以下へ手動コピーし、既存`research.forward_mt4_v2_series`で履歴時系列検証。生成ファイルが正常でも発注許可しない。

**重要：** 端末を30分間完全に放置する運用を推奨するものではない。初回は数分間の目視監視でタイマー発火・3ペアのファイル出力・停止を試験する。以後、連続観測の実機ゲートが通過してから拡張を判断する。

## 未解消とNO_GO
- PCのTimeGMT()とサーバー時刻のUTC真正性、タイマーの実際のスケジュール/停止動作、3ペアのMarket Watch可用性、ディスク保存の永続性はこのPRで確認できない。
- 同時ファイル書込、3ペア同期の正しさ、価格の第三者照合、実際の長時間停止時の復旧、G1 3×5=15項目、G1〜G9、FX-SAFは未検証。
- 自己申告したデモ口座タイプは独立認証されない。
- デモ/実注文は禁止：`runtime_go_no_go=NO_GO`、`safety_hold_latched=true`、`real_orders_permitted=false`。

このPRのマージは、自動売買開始、実機観測の完了、リスク/安全ゲート承認を意味しない。
