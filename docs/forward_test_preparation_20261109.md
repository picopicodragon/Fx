# FX-FWD-001：フォワードテスト準備フェーズ（研究専用、発注禁止）

## フェーズ移行と分離した安全境界

2026-11-09、主軸を歴史イベントの拡張バックテストから**時点情報を凍結するローカル・フォワード観測基盤の準備**へ変更する。2025年データ、AIプロバイダー比較は回帰テスト・研究資料として保持する。

新設`research/forward_observation.py`は以下のみを行う。

1. 現在時点で受領した価格見積（bid/ask/円換算）、公開マクロニュース、AIマクロ仮説、独立審査をローカルに**受領時刻付きで記録**。
2. 観測内容を限定されたスキーマに従って検証し、1件1ファイルで排他的に記録、SHA-256ハッシュ連鎖を保存。再読込で改竄、欠番、時計逆行、リンク未解決を停止。
3. ニュース→仮説→独立レビューの参照元ハッシュを検証。仮説やAPPROVEDレビューは**研究上の見解**としてのみ記録し、注文承認・売買シグナルにはしない。
4. ローカルの入力スナップショットを監査する。一般的なAPIキー・口座識別子の誤混入を拒否（完全な機密スキャナーではない）。
5. 外部ネットワークアクセス、OpenAIへの課金、TypeSafeへの課金、MT4/EAへの接続、仮想損益、実注文、デモ注文はいずれも**行わない**。

本ツールは**ライブデータ収集器ではない**。ユーザーが受け取った情報のローカル保存契約を整える準備段階。現時点ではデータ真正性・配信遅延・取引可能価格・取引可能時間を保証できない。次工程で、規約に適合する公式経済カレンダー、価格配信、MT4デモの**読み取り専用**アダプターを個別に調査・実装してから、認証/時刻/障害回復をテストする。

## 対象とデータ契約

正式3ペア：USD/JPY、EUR/JPY、EUR/USD。現時点では入力の信用レベルは`USER_SUPPLIED_UNVERIFIED`のみ。コードがURLを自動取得することはない。受領時刻`captured_at_utc`はローカルUTC時計、`observed_at_utc`は情報提供者が申告する観測UTC時刻であり、両者の意味は異なる。UTC時計の補正・逆行は停止。ローカル時計同期の正確性は別途評価が必要。

イベント種別：

- `PRICE_QUOTE`：`pair`、`bid`、`ask`、`quote_to_jpy`、`source_status`
- `MACRO_EVENT`：`pair`、`title`、`source_url`、`published_at_utc`、`content`、`consensus`、`released_value`、`source_status`
- `MACRO_HYPOTHESIS`：`pair`、`direction`（LONG/SHORT/HOLD）、`thesis`、`counterevidence`、`model_id`、`basis_sha256`（既存MACRO_EVENT記録hash）、`research_only=true`
- `INDEPENDENT_REVIEW`：`pair`、`review_of_sha256`（既存仮説記録hash）、`verdict`（APPROVED/REVISION/REJECTED/PENDING）、`rationale`、`model_id`、`research_only=true`

同じPythonモジュールで取り込んだ観測を独立検証するため、すべて入力時に文字長・型・許可enum・価格side・時刻を確認する。正確な通貨ペアや約定有効性まで検証するものではない。

**注意**：記録済みファイルやディレクトリをリネーム・編集・削除しないこと。現在のSHA-256連鎖は事故・偶発的改竄・部分破損検知用であり、署名や外部タイムスタンプによる強い改竄耐性を保証しない。管理者によるジャーナル全体の書き換えや単調時計の復元は別途検出策が必要。単一Windows PC・単一MT4前提を維持し、並行MT4ログインや別口座を要求しない。

## Windows PowerShell：無料の初期化と動作試験

### 1. ブランチ取得とテスト

```powershell
cd C:\Users\Suzuki\Documents\ChatGPT\Fx
git fetch origin
git switch --detach origin/feat/forward-observation-research-no-go
python -m unittest discover -s tests -p "test*.py"
```

### 2. ローカル観測セッションを初期化

```powershell
python -m research.forward_observation `
  --store out/forward_observation_20261109 `
  --init `
  --session forward_20261109
```

既存の同名ディレクトリがある場合は上書きを拒否します。新規セッション名/保存先を別途採用してください。

### 3. ローカルの明示的なテスト入力（架空の価格、実レートではありません）

UTC時刻は実行時に生成します。表示値は**テスト用の架空相場**であり、現実の市場価格だとは解釈しません。

```powershell
$nowUtc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
@{
  schema = "fx_forward_observation_v1"
  kind = "PRICE_QUOTE"
  observed_at_utc = $nowUtc
  source_id = "manual_fixture"
  payload = @{
    pair = "USD/JPY"
    bid = "150.001"
    ask = "150.012"
    quote_to_jpy = "1"
    source_status = "USER_SUPPLIED_UNVERIFIED"
  }
} | ConvertTo-Json -Depth 8 |
  Set-Content -Path out/forward_demo_quote_fixture.json -Encoding UTF8

python -m research.forward_observation `
  --store out/forward_observation_20261109 `
  --ingest out/forward_demo_quote_fixture.json
```

### 4. ローカル監査

```powershell
python -m research.forward_observation `
  --store out/forward_observation_20261109 `
  --audit `
  --report out/forward_observation_20261109_audit.json
```

期待される`record_count=1`、`by_kind.PRICE_QUOTE=1`、`real_orders_permitted=false`。コマンドに`--allow-external-api`は存在しない。外部接続はまったく行わない。監査レポートも既存ファイルへの上書きを拒否する。

## 次工程の受入ゲート

| ゲート | 設備・基準 | 状態 |
|---|---|---|
| FWD-01 | ローカル観測記録、完全性・UTCの照合 | 実装・CIテスト対象 |
| FWD-02 | 価格配信・公式マクロ情報の契約/出典/タイムスタンプ検証 | PENDING |
| FWD-03 | 速報前後のデータ遅延/欠落/改訂の検知 | PENDING |
| FWD-04 | 承認済み主AI・独立反証AIの実時間読み取り専用連携 | PENDING |
| FWD-05 | 決定論的リスク管理に接続しない仮想注文・仮想決済・損益の整合試験 | PENDING |
| FWD-06 | MT4デモへのアカウント識別/発注前の読み取り専用監視、安全停止・競合防止 | PENDING |
| FWD-07 | 別途承認されるMT4デモ専用発注権限の安全レビュー | NOT AUTHORIZED |
| FWD-08 | 人間によるモジュール/フェーズ・本番採用判断 | PENDING |

## 安全・費用

- `runtime_go_no_go=NO_GO`, `safety_hold_latched=true`, `real_orders_permitted=false`を維持。
- 本番ロット・SL・サーバ側SL、DD5%、1取引0.5%、日次1.5%、イベント前後停止、Q109/Q110の受入ゲートを変更しない。
- プログラムは`research/`の隔離された記録ツールのみであり、MT4のEA設定や自動売買ボタンを操作しない。出力を外部AIに自動送信しない。運用時のAPI課金もない。
- 仮想取引の実装やMT4デモ接続を、今工程のテスト成功によって無断で解放しない。

これにより、次段階での実時間インテークに先立って、観測・監査記録の不変条件と検証手順を固定する。
