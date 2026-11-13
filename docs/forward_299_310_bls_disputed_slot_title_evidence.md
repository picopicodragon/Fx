# FWD-299〜310：同時刻BLSイベントの候補名を安全に表示する読み取り専用監査

## 実際の根拠（2026-11-13）

ユーザーWindowsの保存済みBLS ICS研究JSON（asof `2026-11-13T00:47:40Z`）を、PR #271 の静的HTML予定表と照合。ICSは4件、11月分HTMLから対象区間に入るものは5件。日時多重集合の一致は4件で、`2026-11-20T15:00:00Z`（EST 10:00、日本時間11月21日00:00）に1件不足する。

BLSの [2026年11月月間発表一覧](https://www.bls.gov/schedule/2026/11_sched_list.htm) と [Weekly Update](https://www.bls.gov/opub/update.htm) は共に、同時刻の以下2リリースを掲載している。

- State Employment and Unemployment (Monthly) for October 2026
- Total Factor Productivity for Major Industries for Annual 2025

ただし、ユーザーの実ICS JSONの**イベント名**は、この段階ではまだ確認していない。同一のBLSからの別ページは発行元の独立認証ではない。発表予定は後日改訂され得る。前回の静的HTML転記は2026-11-03時点のラベルを持つに留まる。

## 実装

既存のオフライン `research.forward_bls_calendar_crosscheck` に**不一致の日時だけ**次の候補情報を追加する（後方互換で従来項目は変更しない）。

- `disputed_slot_title_evidence`：日時、ICS/HTMLに収録された候補タイトル、元の件数。
- `literal_identical_titles_unverified`：両者の完全に同じ表記のタイトル（参考のみ）。
- `ics_titles_omitted_count`／`html_titles_omitted_count`：出力が長すぎる場合に省略件数を示す。
- 1つの日時の各ソースにつき先頭12件、全体で12日時までに制限し、残り日時の省略件数を示す。
- `candidate_identity_verified=false`、`auto_resolve_or_backfill_allowed=false`、`title_alias_or_release_identity_inference_allowed=false`、`missing_calendar_event_auto_insert_allowed=false` を固定。
- カレンダーの出典・安全状態・件数の既存検査を通過した後にのみ候補を表示。曖昧なタイトルの同義語推定や相互補完はしない。
- 同時刻のイベント件数が一致していても、**名前や統計系列の一致は証明されない**。

## Windowsでの実行方法（新規ダウンロード不要）

PR #271 の監査を実施したworktreeで保存された `$calendarReport` の絶対パスをそのまま使える。新ブランチを使用するため別worktreeを作る。元の `Fx` は切り替えない。

```powershell
$repo = "C:\Users\Suzuki\Documents\ChatGPT\Fx"
if (-not $calendarReport -or -not (Test-Path -LiteralPath $calendarReport)) {
    throw "保存済みBLSカレンダーJSONの絶対パスが見つかりません。"
}
git -C $repo fetch origin
if ($LASTEXITCODE -ne 0) { throw "Git fetch failed" }
$wt = Join-Path (Split-Path $repo -Parent) ("Fx-FWD-299-310-" + (Get-Date -Format yyyyMMdd_HHmmss))
git -C $repo worktree add --detach $wt origin/feat/fwd-299-310-bls-disputed-slot-titles
if ($LASTEXITCODE -ne 0) { throw "Worktree creation failed" }
Set-Location $wt
python -m research.forward_bls_calendar_crosscheck `
  --calendar-report $calendarReport `
  --reference-file research/references/bls_2026_11_selected_html_schedule.json
```

主に `disputed_slot_title_evidence` を確認し、11/20のICSタイトルが2候補のどちらと同一表記なのか、または別表記なのかを確認する。その結果を手がかりに**人間による出典照合を行う**。どちらかを自動的に「欠落」と決めず、追加入力せず、経済指標発表停止窓・AI判断・注文経路に連結しない。

## 安全境界

- すべて読み取り専用、ネットワーク0、AI API0、MT4/EA0、デモ注文0、本番注文0。
- 原ICS報告、元価格CSV（114ファイル）、研究ジャーナル、発表前予想証拠を変更しない。
- BLSの2ページだけで時刻の独立認証や全FX経済指標網羅性を得たとは判定しない。
- `NO_GO`、`safety_hold_latched=true`、`demo_orders_permitted=false`、`real_orders_permitted=false` 維持。
