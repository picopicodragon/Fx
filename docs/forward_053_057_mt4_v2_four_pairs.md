# FX-FWD-053〜057：4ペア・ティック時刻対応、読み取り専用MT4 v2

## 重要な仕様差分
旧研究用バックテストやシャドー監視が使う `PAIRS` は `USD/JPY, EUR/JPY, EUR/USD` の3ペアである。しかし**正式なFX取引対象**は `USD/JPY, EUR/JPY, GBP/USD, AUD/USD` の4ペアである。旧3ペアへの互換性を壊す一括置換は行わず、まず独立した**4ペア用読み取り専用観測v2**を用意した。旧研究基盤が4ペアに対応したという意味ではない。今後はバックテスト・建玉リスク・仮説・保護停止・経済イベントの全経路で、明示的な4ペアへの移行とテストが必要。

| 工程 | 実装 | 保証しないこと |
| --- | --- | --- |
| FWD-053 | `research/mt4_readonly/FxForwardReadOnlyQuoteV2.mq4`。4ペア、単発手動CSV出力、DEMO/接続ガード、MODE_TIMEとTimeCurrentの差からサーバー内相対ティック経過秒を算出。90秒超は出力しない | MetaEditorでのコンパイル、楽天MT4実機動作、ブローカー時刻のUTC変換・真偽 |
| FWD-054/055 | `research.forward_mt4_v2_quote`。v2専用CSV10列、口座DEMO自己申告、両側レート、ペア、PC時刻、サーバー内ティック差、JPY換算研究値を厳密検証 | ライブレート、独立時計、配信契約、取引可能なレート品質 |
| FWD-056 | `research.forward_mt4_v2_four_pair`。4ペアのスナップショット重複・欠損・鮮度検査。良好な入力でも常時NO_GO | 旧バックテストの4ペア対応、実建玉連動 |
| FWD-057 | `research.forward_mt4_v2_source_contract`。MQL4ソースに必要な関数、列定義、危険API混入を静的に検査する | 実機バイナリの動作やMQL4コンパイラの安全性 |

## 注意：MT4のTimeGMTとTimeCurrentの性質
- `TimeGMT()`はPC時計から得たUTC相当の値。外部時計との同期は独立検証されていない。
- `MODE_TIME`は指定シンボルの最終ティック時刻、`TimeCurrent()`は端末に見えているブローカーサーバー時間である。同一時間基準と仮定した差分で、古いティックを検出する。
- ただし市場停止、配信障害、端末オフラインなどでは**両方のサーバー時刻が止まり、差分が小さいままでも古い価格を新鮮と誤認し得る**。v2はPC側のUTCを別に確認するが、サーバー時間とPC UTCの独立した相関を証明できないため、発注判断には一切使わない。
- USD/JPYからのGBP/USD・AUD/USD換算値も未認証の研究用参考値。運用中の正式リスク円換算に使わない。

## Windowsでのコード側の事前検証
```powershell
python -m research.forward_mt4_v2_source_contract `
  --source research/mt4_readonly/FxForwardReadOnlyQuoteV2.mq4 `
  --out out/fwd_v2_source_contract_001.json

python -m research.forward_mt4_v2_quote `
  --csv out/manual_mt4_v2_example.csv `
  --asof-utc 2026-11-10T03:00:00Z `
  --out out/v2_quote_report_001.json
```
入力ファイルと日時は**形式例**。偽の価格・時刻を実際の観測と扱わない。新しい入力CSVは次の列順で作る必要がある：

```text
observed_at_utc,pair,bid,ask,quote_to_jpy,server_tick_time,server_now_time,tick_age_seconds,account_type,origin
```

`server_tick_time`と`server_now_time`はオフセットを持たないサーバー側ローカル時計の表記。UTCとして誤読してはならない。

## 実機着手条件
GitHub CIはWindowsのPythonを実行するが、**ユーザーの楽天MT4/MetaEditorを操作しない**。新しいMQL4をローカルに配置・コンパイル・実行するのは、ユーザーの既存デモ口座と単一端末で安全性と出力先を確認できた後の別工程。AutoTradingはOFFを維持し、いかなる注文も実施しない。勝手にタスク登録、並列ログイン、別デモ口座作成をしない。

全レポート `runtime_go_no_go=NO_GO`、`safety_hold_latched=true`、`real_orders_permitted=false`、`demo_order_execution_enabled=false`。
