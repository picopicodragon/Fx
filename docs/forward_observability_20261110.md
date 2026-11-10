# FX-FWD-018〜021：フォワード研究観測の安全性と欠損監視

## 実装内容
- **FWD-018**: `research.forward_observability` で複数周期の観測遅延、周期欠落、仮想資産の既存リスク警報を統合する。監視対象は外部認証されていない研究報告であり、常に`NO_GO`。
- **FWD-019**: `research.forward_quote_continuity` でFWD-01のハッシュ連鎖監査済みジャーナルから、正式3ペア（USD/JPY、EUR/JPY、EUR/USD）のBid/Ask観測時刻、欠落、連続同値、90秒超の鮮度、周期間ギャップを検知する。価格は手動申告等のローカル値。オンライン価格ストリームや利用ライセンスの認定にはならない。
- **FWD-020**: BLS/FED/ECB/BOJの4区分についてオペレーターが別途取得・用意した予定スナップショットを研究専用で検査する。区分が揃っても網羅的な経済カレンダーとは認定しない。現時点ではBLSの既存ICS取得以外の公式ソース用自動アダプタは未実装。
- **FWD-021**: `research.forward_mt4_static_audit` で読み取り専用MQL4ソースの危険APIトークンと必須DEMO/接続ガードを静的検査する。MetaEditorコンパイルや楽天MT4実機での実行確認ではない。

## 安全境界
ネット接続、外部有料API、MT4スクリプト配置、MT4口座接続、売買許可、Windows常駐・タスク登録を一切行わない。全出力は`runtime_go_no_go=NO_GO`、`safety_hold_latched=true`、`real_orders_permitted=false`、デモ注文無効。

研究データの欠損検知は実際の稼働・配信保障を意味せず、内部ハッシュ整合性は外部の価格真正性を証明しない。4区分のスナップショット内の事象がゼロでも、予定無しや安全な取引時間帯とは判断しない。

## Windowsコマンド

```powershell
python -m research.forward_observability `
  --multicycle out/multicycle_report_001.json `
  --asof-utc 2026-11-10T01:00:00Z `
  --out out/forward_observability_001.json

python -m research.forward_quote_continuity `
  --store out/forward_observation_20261109 `
  --asof-utc 2026-11-10T01:00:00Z `
  --out out/forward_quote_continuity_001.json

python -m research.forward_mt4_static_audit `
  --source research/mt4_readonly/FxForwardReadOnlyQuote.mq4 `
  --out out/mt4_static_audit_001.json
```

日付は書式例であり、実観測結果を意味しない。各出力先は新規作成専用で、上書きを禁止する。

## FWD-020の任意JSON入力

```json
{
  "schema": "fx_forward_schedule_snapshot_v1",
  "source_key": "US_BLS",
  "retrieved_at_utc": "2026-11-10T00:50:00Z",
  "source_status": "PUBLISHED_SCHEDULE_UNVERIFIED",
  "runtime_go_no_go": "NO_GO",
  "real_orders_permitted": false,
  "source_authenticity_verified": false,
  "events": [
    {
      "title": "illustrative event",
      "scheduled_at_utc": "2026-11-10T01:00:00Z",
      "source_url": "https://www.bls.gov/example",
      "source_status": "PUBLISHED_SCHEDULE_UNVERIFIED"
    }
  ]
}
```

このJSONは**架空の形式例**であり、掲載の日時や内容が公式発表予定であるという意味ではない。`--schedule out/snapshot.json` を複数回指定できる。未確認ソース、古いスナップショット、±15分の予定は保留理由となる。信頼性・出典・予想値・対象ペアへの波及関係は別途審査が必要。

## 残課題
1. FWD-019: 許諾を確認したライブ相場フィードとティック時刻の独立照合、再接続、実運用時の欠損検出。
2. FWD-020: 日銀・ECB・FRB公式の未来予定をそれぞれ正しい時刻体系で収集し、改訂予定を差分監査する。公式URL、仕様とアクセス条件の事前確認が必要。
3. FWD-021: Windows上のMetaEditorコンパイル、楽天デモMT4端末の実機実証、ローカルファイル読み込みの権限分離。別口座や同時接続は行わない。
4. FWD-022以降: 安全制約を外さない監視オーケストレーション、長時間シャドー運用実績、実口座とは独立したデモ売買承認審査。

これらの未完了工程を実装済みとみなさない。

## FWD-022: デモフォワード運用の事前不足条件

`research.forward_demo_readiness` は、FWD-018/019/021の研究レポートを入力として、欠損と未承認条件を表示する**オフラインのチェックリスト**。楽天MT4への接続・インストール・プログラム実行・注文は一切しない。自己申告が全部YESでも、独立したデモ口座認証、価格/時計認証、正式承認がないため`NO_GO`は変わらない。

```powershell
python -m research.forward_demo_readiness `
  --observability out/forward_observability_001.json `
  --quote out/forward_quote_continuity_001.json `
  --mt4-static out/mt4_static_audit_001.json `
  --out out/forward_demo_readiness_001.json
```

追加のオペレーター申告ファイルは任意（`--operator-declaration`）。正式デモ口座であるかは本人の申告のみでは証明できず、注文実行許可とは無関係。既存の口座を安全に維持し、デモ口座の複数新設・複数端末同時ログインを要求しない。
