# FWD-058〜062：正式3ペアへの是正・監査・回帰防止（2026-11-10）

## 正式仕様（本人再確認）

**現行の研究・将来の正式FX取引対象は次の3ペアのみ：**

| 通貨ペア | MT4想定表示名 | 適用 |
|---|---|---|
| USD/JPY | USDJPY | 対象 |
| EUR/JPY | EURJPY | 対象 |
| EUR/USD | EURUSD | 対象 |

GBP/USD・AUD/USDは**現行対象外**。MASTER_SPEC.mdの古いQ3 4ペアは歴史的記録として保持し、2026-11-04の後続正式3ペア指定、および2026-11-10の再確認を適用する。

## 実施工程

| 工程 | 修正・追加 |
|---|---|
| FWD-058 | 未配備MQL4 v2ソースをUSDJPY/EURJPY/EURUSDに変更。EUR/USDのみ、研究用のUSDJPY換算値を取得 |
| FWD-059 | v2 CSV入力の許可リストを3ペアに修正。旧4ペアを拒否。v2集約のレポートを3ペアに変更 |
| FWD-060 | v2静的ソース契約で3ペア必須、GBPUSD/AUDUSDの追加を拒否。既存のv2単体テストを修正 |
| FWD-061 | `research.forward_active_pair_scope` を追加。研究基盤の既存PAIRS、v2入力、MQL4ソースが同じ3ペアであるか検査 |
| FWD-062 | MASTER_SPEC/README/DECISIONSへの再確認追記、文書訂正、3ペアの回帰試験を追加 |

### 互換性

過去の`research.forward_mt4_v2_four_pair`というファイル名は既存インポートを不用意に壊さないため**維持するが、処理内容は3ペアに変更**。`schema=fx_forward_mt4_v2_three_pair_review_v1`、`status=MT4_V2_THREE_PAIR_RESEARCH_HOLD_NO_GO`であり、**旧4ペア形式との意味的互換性は認めない**。既存の研究エンジン`research.offline_backtest.PAIRS`、MT4 v1、FWD-043〜052は最初から正式3ペアと一致しており、こちらは変更不要。旧4ペアの合成試験があれば過去の範囲の証拠に留め、現在の承認には利用しない。

### 実行例（Windows PowerShell、外部通信なし）
```powershell
python -m research.forward_active_pair_scope `
  --source research/mt4_readonly/FxForwardReadOnlyQuoteV2.mq4 `
  --out out/active_pair_scope_001.json

python -m research.forward_mt4_v2_source_contract `
  --source research/mt4_readonly/FxForwardReadOnlyQuoteV2.mq4 `
  --out out/three_pair_v2_static_001.json
```
出力上書き禁止。MQL4実機コンパイル・デモセッション起動・価格取得は実行しない。

## 安全条件・未完了事項

最新の通貨ペア指定は**対象範囲の確認であり、発注許可ではない**。G1主要契約属性3×5=15項目は未実測（0/15）。正式な0.5%/1.0%/日次1.5%/DD2〜5%およびG1〜G9、FX-SAFの審査は別途必要。ブローカーの時刻・ティック、PC時計、配信ライセンス、USDJPY円換算、相関・通貨集中リスクはいずれも未実機検証。

全結果の`NO_GO`、`safety_hold_latched=true`、`real_orders_permitted=false`、デモ注文無効は変更しない。楽天MT4へソースを自動配置・コンパイル・実行しない。GitHubのCI成功は実運用の安全認証ではない。
