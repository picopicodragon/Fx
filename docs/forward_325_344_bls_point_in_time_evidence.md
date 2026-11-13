# FWD-325〜344：BLSのICSとHTMLを取得時点ごとに原本保存し、改訂を監査する（NO_GO）

## 根拠

2026-11-13ユーザーWindowsのBLS研究用ICS JSON（`calendar_sha256=92a350111ace106deaab5584e4084366bd367b594a0d0bad116008d82d63e501`、`asof_utc=2026-11-13T00:47:40Z`）は4件。
BLS2026年11月HTML予定表は同区間に5件を表示。差異は11月20日15:00 UTCで、ICSには
`State Employment and Unemployment (Monthly)`、HTMLにはそれに加えて
`Total Factor Productivity for Major Industries for Annual 2025` の候補がある。

前段のFWD-311〜324は、名前の語彙的一致を候補として表示するが、ICSからの抜けや改訂の時点を確証できない。
また従来のJSONは元ICS本文ではなく本文のSHAだけを保持していた。

BLS公式参考：
- https://www.bls.gov/schedule/2026/11_sched_list.htm
- https://www.bls.gov/schedule/news_release/bls.ics
- https://www.bls.gov/opub/update.htm

## 新規2コマンド

`research.forward_bls_dual_snapshot`：
- **利用者が明示的に `--allow-network` を渡した一回のみ**、固定HTTPS公式URLへICS/HTMLを各1回GET。
- `research.forward_bls_calendar.download` をそのまま利用する。ICS上限350,000バイト、HTML上限500,000バイト、リダイレクト禁止、12秒タイムアウト、自動再試行なし、利用者権限で403/429なら停止。
- HTMLは月次2026年11月ページに限定。HTMLの体裁・期待月/表題が確認できない場合はFail Closed。任意URL入力や別サイトへの切替なし。
- `--ics-file`＋`--html-file` による明示的なローカル・オフライン取り込みも可能。双方指定必須で、ネットワークモードとは併用禁止。
- 取得した各元本文のSHA256とバイト数、取得直後（オフライン時は**ローカルコピーを読んだ時点**）のUTCローカル時計値を記録。日時はNTP等で独立認証していない。
- 出力先は**まだ存在しないディレクトリ**だけ、`bls.ics`、`bls_schedule.html`、`calendar.json`、最後に`snapshot.json`を作成。途中失敗で最後のマニフェストがなければ無効な不完全バンドルとして保留。既存データを上書きしない。
- 2ソースは連続取得なので同時刻原本ではなく、相互の内容変更もあり得る。
- この保存物には市場予想値、実際の発表、ブローカー時刻認証は含まれない。点時点の完全な公開履歴を証明しない。

`research.forward_bls_snapshot_diff`：
- 2つの保存済みバンドルをオフラインで読み、原本バイト数/SHA、内部JSON、時刻順序、安全フラグを再確認。
- `BOTH_SOURCE_BYTES_UNCHANGED` / `ICS_SOURCE_BYTES_CHANGED` / `HTML_SOURCE_BYTES_CHANGED` / `BOTH_SOURCE_BYTES_CHANGED` を出力。
- **バイトが異なることは発表スケジュールが変化した証明ではなく、バイトが同一でも発表予定を網羅した証明ではない。** タイトル・日時の変更を分析する前の第一層の監査である。
- 変更の有無にかかわらず `NO_GO` と保有なし・発注禁止を維持。

## Windows実行（元のFxフォルダーの未コミット変更を維持）

PRを使う際は、前回の既存worktreeから以下を実行できる。

```powershell
$repo = "C:\Users\Suzuki\Documents\ChatGPT\Fx"
git -C $repo fetch origin
if ($LASTEXITCODE -ne 0) { throw "fetch failed" }
$wt = Join-Path (Split-Path $repo -Parent) ("Fx-FWD-325-344-" + (Get-Date -Format yyyyMMdd_HHmmss))
git -C $repo worktree add --detach $wt origin/feat/fwd-325-344-bls-point-in-time-bundles
if ($LASTEXITCODE -ne 0) { throw "worktree failed" }
Set-Location $wt
New-Item -ItemType Directory -Path "out" -Force | Out-Null
$snap1 = "out/bls_dual_$(Get-Date -Format yyyyMMdd_HHmmss)"
python -m research.forward_bls_dual_snapshot `
    --allow-network `
    --days-forward 14 `
    --out-dir $snap1
```

取得成功した場合だけ、別の明示実行で2回目を保存した後、次のオフライン照合を行う。自動巡回しない。

```powershell
$snap2 = "out/bls_dual_$(Get-Date -Format yyyyMMdd_HHmmss)"
python -m research.forward_bls_dual_snapshot --allow-network --days-forward 14 --out-dir $snap2
python -m research.forward_bls_snapshot_diff --before-dir $snap1 --after-dir $snap2
```

元の未コミット差分・114価格CSV・AI研究ジャーナル・MT4/EA・デモ/本番口座には触れない。
マニフェストのSHAや取得時計を独立認証された出典証明と取り違えない。HTML側とICS側のイベント単位の差異や改訂は次のフェーズで解析する。

## 受け入れ境界

- Linux Python 3.12 / Windows Python 3.13のCI、合成データ・例外・原本改ざん・上書き拒否を検証。
- 実HTMLの体裁が想定と違えば、日時を推定したり検証を緩めたりせずエラー分類を改善する。
- `NO_GO`、`safety_hold_latched=true`、`demo_orders_permitted=false`、`real_orders_permitted=false`を維持。
