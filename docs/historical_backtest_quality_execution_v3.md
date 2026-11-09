# FX-BT-003: 実履歴価格の品質監査とbid/ask約定モデル（研究専用）

## 改修の背景

2025Q1のユーザー提出バックテストJSONは33件、損益 -3,648.039円、最大観測DD約4.07%と報告した一方、土曜の新規エントリーなど通常のFX取引時間と矛盾する履歴があった。従前の`historical_replay`は週末も含めたDukascopy由来CSVの時間グリッドをそのまま処理し、約定時はbid/ask両側のOHLCをmidにまとめて1足固定スプレッドを当てていたため、実市場に対する判断には不適切だった。

## FX-BT-003が変更すること

- 過去データ6系列をUTC、H1単位でチェック後、**America/New_York基準・日曜17:00から金曜17:00まで**を取引セッションとする。NY夏時間に追随し、土曜・日曜の休場中の履歴足は**除外**する。除外足数は6系列ごとに`historical_research.weekend_candles_removed_by_pair_and_side`で明示する。元CSVを改変しない。
- 休場除外後にbid/ask 6系列を共通時間に整列し、差分/欠損の検査を継続する。特別休日・ブローカーごとの取引時間・長期異常停止は未検証であり、結果の`special_holidays_verified=false`に記録する。
- 約定価格を元の**bid/ask OHLC**に基づき直接計算。買い建てはask始値、売り建てはbid始値、買い決済はbid、売り決済はask。損切りと利確が1本のOHLCで両立する場合は損切り優先。OHLCの高安順序・実スリッページは再現不能。
- 週末ギャップをまたぐ古い`LONG/SHORT/FLAT`シグナルを次の足に持ち越さない。**すでに保有中のポジション**は週明け最初の気配でギャップ損失判定の対象にする。
- 新規売買拒否を`signals_rejected_by_reason`（DD停止、日次停止、過大スプレッド、リスク予算不足）で分類。`stale_gap_signals_suppressed`を独立して記録。追加項目は研究レポートのみで実売買の安全承認ではない。

## 依然としてできないこと

- 提供元データの真偽、元ティック順序、OHLC内の実約定、ブローカー別祝日、クリスマス/年末特別取引時間の確証
- スワップ、証拠金、レバレッジ/ロスカット、注文拒否、発注遅延、ニュース発表時スリッページ
- 公式のAIマクロ戦略（現在のリプレイ戦略はSMA10/30の研究用例示）
- 人間のP05承認・FX-SAF原議や本番GOの代替

## Windows上の再実行

mainに手動マージ後、`git switch main; git pull --ff-only origin main` を実行。**同じ6本の履歴CSV**を使い、`docs/historical_replay_h1_v2.md`記載の`python -m research.historical_replay`コマンドを再実行。以前のレポートとの差を明示するため、出力ファイル名は`out/historical_backtest_2025Q1_v3.json`を推奨。価格ファイルは`data/raw/`内のままでありGit管理しない。

出力に`historical_research.weekend_candles_removed_by_pair_and_side`、`historical_research.fill_model=actual_bid_ask_OHLC_stop_first_ambiguous`、`signals_rejected_by_reason`があることを確認。価格・期間・SHA256が前回と同じなら、週末除外によって取引件数、最終損益、DD停止日時が変わるのは**期待される仕様差**。それを改善実績や正式AI戦略の精度向上と解釈しない。

## 安全境界

`runtime_go_no_go=NO_GO`、`safety_hold_latched=true`、実取引/デモ注文/楽天MT4/EA接続は禁止。P05およびFORM認可証跡を捏造・編集・自動承認しない。1PR集約だがmainマージだけは人間が実施する。
