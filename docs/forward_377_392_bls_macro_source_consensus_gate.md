# FWD-377〜392：BLS保存原本と発表前コンセンサスを分離して判定する研究ゲート

## 実機で確認した前提

2026-11-13ユーザーWindowsのFWD-361〜376実行結果：
- BLSのICS/HTMLの原本整合性検査は合格。
- 保存済みICSはイベント4件、HTMLは同一期間5件、同時刻の4件が一致。
- 差異は2026-11-20T15:00:00ZでHTML原本に「Total Factor Productivity for Major Industries for Annual 2025」の追加候補。
- ローカル同時取得時刻は2026-11-13T01:48:45Z（時計の独立認証なし）。
- 既存のHTMLとICSは同じBLS発行元からの情報。独立した第三者認証ではない。
- 15分間の発表前後停止窓の実運用や、海外・日本・中央銀行の網羅性はこの取得だけでは証明できない。

## 目的

情報源の照合不一致と発表前コンセンサス未取得を、**別々の保留理由として表示する**。
本番移行のGO条件を解除する機能ではなく、研究用の不備チェックのみを実装する。

## 実装

新モジュール：`research.forward_bls_macro_source_gate`

```powershell
python -m research.forward_bls_macro_source_gate `
    --snapshot-dir $originalBundle `
    --asof-utc "2026-11-13T02:00:00Z"
```

- `--snapshot-dir` の原本4ファイルをSHA256・保存マニフェスト・ICS再パース結果で検証し、
  取得HTMLのDate/Time/Release表とICSの日時の件数比較を再実行。
- `BLS_ICS_HTML_SCHEDULE_COUNT_DISAGREEMENT`：
  実際の原本で見られる時刻別・件数の不一致。イベントの自動補完は行わない。
- `POINT_IN_TIME_CONSENSUS_EVIDENCE_MISSING`：
  発表前に保存した市場予想の証拠が渡されていない。予定表があっても予想値は推測しない。
- `FULL_FX_MACRO_CALENDAR_NOT_ATTESTED`：
  BLSはFX主要イベントの一部であり、世界の全市場・経済指標や日銀・ECB・FRBを網羅していない。
- `BLS_SOURCE_PUBLICATION_AND_LOCAL_CLOCK_UNATTESTED`：
  元情報の公開日時やWindowsローカル時計は独立に認証していない。
- 保存HTML観測時点から24時間以上経過したら`BLS_SAVED_SNAPSHOT_OLDER_THAN_24H`も出す。
- `--forecast-archive` は任意。渡された場合、保存済み予想値レコードの完全性、日付整合、
  同一ICS SHAとタイトル/日時を厳格に照合。照合できても予想原本の真正性は認めない。
- 観測時刻が未来にある場合、スナップショット改ざん・未対応構造・不正な予想値がある場合は
  **FAIL_CLOSED**し、無理に推測・継続しない。
- `asof_utc` はUTCの厳格なISO秒・末尾Z必須で、利用者が明示。過去日時の指定もシステム時計で
  独立認証したことにはならない。

## ユーザーWindowsでの最初の実行

現在 `Fx-FWD-361-376-20261113_112822` worktreeで作業中。すでに
`$originalBundle` は絶対パスとして定義済み。この原本を再利用してよい。

```powershell
$repo = "C:\Users\Suzuki\Documents\ChatGPT\Fx"
if (-not $originalBundle -or -not (Test-Path -LiteralPath $originalBundle)) {
    throw "保存済みBLS原本が見つかりません"
}
git -C $repo fetch origin
if ($LASTEXITCODE -ne 0) { throw "fetch failed" }
$wt = Join-Path (Split-Path $repo -Parent) ("Fx-FWD-377-392-" + (Get-Date -Format yyyyMMdd_HHmmss))
git -C $repo worktree add --detach $wt origin/feat/fwd-377-392-macro-source-consensus-gate
if ($LASTEXITCODE -ne 0) { throw "worktree add failed" }
Set-Location $wt
$asof = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
python -m research.forward_bls_macro_source_gate `
    --snapshot-dir $originalBundle `
    --asof-utc $asof
```

このコマンドは原本を**一切更新せず**、ネットワーク取得も有料APIコールもしない。
バイト数/時刻/イベント別保留の研究結果を標準出力するだけ。
新規worktreeは保存済み原本や元の `Fx` の未コミット変更を操作しない。

## 安全境界と継続課題

- 本ゲートは独立したマクロ情報の収集や実注文の保護装置として稼働するものではなく、
  **オフライン研究用の観測資料**。発表15分前後停止や自動再開を実装/許可しない。
- 研究を進めるには、BLS以外の主要国・中央銀行の経済指標と、**発表前**の市場予想値の原本、
  出典・公開/取得日時・定量値・単位の証拠を揃える。
- ライブ/デモの自動注文は未承認、MT4/EAにも接続しない。
- `NO_GO`、`safety_hold_latched=true`、
  `demo_orders_permitted=false`、`real_orders_permitted=false`固定。
  取引ごとの0.5%、合算1%、日次1.5%、DD4/5%等、既存安全要件は変更しない。
