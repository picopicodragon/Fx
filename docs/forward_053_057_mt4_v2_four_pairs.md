# FX-FWD-053〜057 訂正記録（2026-11-10）：正式対象3ペアへの整合

このファイル名は既存参照への互換性のため維持する。過去の記載「正式4ペア」は誤り。**現行正式仕様はUSD/JPY・EUR/JPY・EUR/USDの3ペア**であり、README.md、MASTER_SPEC.mdの2026-11-04後続指示、DECISIONS.mdの新しい指定に一致する。旧Q3の4ペアは**歴史的決定**としてのみ保持する。GBP/USDとAUD/USDは取引・観測v2の対象外である。

## v2の現在の定義（FWD-058〜062訂正後）
- `research/mt4_readonly/FxForwardReadOnlyQuoteV2.mq4`：未配備の単発読み取り専用MQL4ソース。USDJPY/EURJPY/EURUSDのみ。DEMO判定、接続判定、Bid/Ask/最終ティックのサーバー内相対時刻差が要件を満たさない場合はCSV出力を中止する。
- `research.forward_mt4_v2_quote`：3ペア許可リスト、CSV10列、PC時計による`observed_at_utc`、`server_tick_time`、`server_now_time`、`tick_age_seconds`を厳密に検査。GBP/USD・AUD/USDは拒否する。
- `research.forward_mt4_v2_four_pair`：**モジュール名は旧バージョン互換のため残すが内容は3ペア照合**。レポートスキーマは`fx_forward_mt4_v2_three_pair_review_v1`、ステータスは`MT4_V2_THREE_PAIR_RESEARCH_HOLD_NO_GO`。旧4ペアレポートの暗黙変換・再利用は行わない。
- `research.forward_mt4_v2_source_contract`：MQL4静的ソースにUSDJPY/EURJPY/EURUSDを要求。古いGBPUSD/AUDUSDの取引・研究対象指定を受け入れない。

## MT4時刻に関する限界

`TimeGMT()`はPC時計から得るUTC相当時刻であり、`MODE_TIME`と`TimeCurrent()`は端末のサーバー時間を使用する。相対時刻差が小さくても配信停止時に両時刻が停止していれば鮮度は保証できない。サーバーのUTCオフセット、ブローカーの価格真正性、USDJPYを用いるEURUSD円換算係数、実行可能な証拠金・リスクは未検証。

## 改訂に関する扱い

今回のユーザー指示は現行正式通貨ペアの確認・修正であり、**ライブ・デモ注文許可、口座稼働、MT4へのスクリプト配置・コンパイル許可ではない**。全出力は`runtime_go_no_go=NO_GO`、`safety_hold_latched=true`、`real_orders_permitted=false`、デモ発注無効。

既存研究エンジンの`research.offline_backtest.PAIRS`はすでに正式3ペアと一致するため変更しない。相関/通貨別集中リスク、リスク上限、FX-SAF、G1〜G9未承認条件は従来どおり。
