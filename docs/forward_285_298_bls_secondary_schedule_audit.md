# FWD-285〜298：BLS ICSと公式HTML予定一覧の読み取り専用照合

## 背景

2026-11-13 ユーザーWindowsでBLS ICSの研究用取り込みが成功。
`status=BLS_CALENDAR_RESEARCH_ONLY_NO_GO`、`event_count=4`、
`imminent_event_count=0`、`calendar_timezone_alias_us_eastern_assumed=true`。
2026-11-12の元ICS（80,672 bytes、TZID=US-Eastern 313件）に基づく障害は修正済み。
この成功は発表予定の網羅性や時刻の独立認証を示さない。

## 第2形式の参照

BLS公開の[2026年11月「Schedule of Selected Releases」リスト](https://www.bls.gov/schedule/2026/11_sched_list.htm)に掲載された日時・表題を、限定的なJSON参照へ手動転記：
`research/references/bls_2026_11_selected_html_schedule.json`。

- 発表予定表の表示は **Eastern Time**、公開ページの最終更新日は2026年11月3日。
- 参照は、現時点で参照できたHTMLリストの**静的転記**であり、改訂・遅延を追跡しない。
- 同一のBLSを原本とするICSとHTMLなので、これら2形式の一致は**発行元の独立検証**ではない。
- 原文HTMLそのものの保全・署名・取得時刻の認証はしていない。参照自体は改訂され得る。
- BLSの「Selected Releases」は全世界のFX重要イベントを網羅しない。

この参照には11月3〜20日の発表10件があり、11月13〜20日には5件が掲載されている。
ただしユーザーのICS JSONの `asof_utc` とイベント日時・表題そのものはこの会話には共有されていないため、現時点で**具体的な欠落を断定しない**。

## 実装

`research.forward_bls_calendar_crosscheck` はネットワーク接続やファイル書き込みを行わず、保存済みICS研究用JSONと参照JSONを読み込む。

- 両JSONにサイズ制限と厳格なスキーマ・NO_GO・出典・件数の検査を行う。
- 11月の参照が対象区間の開始・終了を包含しなければ `FAIL_CLOSED`。他月への跨ぎを「一致」と判定しない。
- `America/New_York` のDSTを使いHTMLのEastern TimeをUTCへ変換。DSTの不在・重複時刻は拒否。
- ICSとHTMLのイベント**時刻の多重集合（件数つき）**を比較。同時刻2件のうち1件が欠けた場合も検出。
- 件数が揃ってもタイトル・統計系列・発表元・発表前市場予想・発表結果は照合していないことを明示。
- 結果は `SELECTED_HTML_SLOT_COUNTS_MATCH_UNVERIFIED` または `SELECTED_HTML_SLOT_COUNTS_DISAGREE`。どちらも研究用 `HOLD_NO_GO`。
- 入力の `calendar_sha256` は元ICSレポートの**自己申告値**。元ICSデータへの独立チェーンオブカストディを保証しない。

## Windows PowerShellでの実施

前回の別worktreeで生成したカレンダーJSONの絶対パスを記録する。PowerShellが前のworktreeにいる場合：

```powershell
$calendarReport = (Resolve-Path $cal).Path
```

新たなコードを元の未コミット変更を保持したまま使う場合：

```powershell
$repo = "C:\Users\Suzuki\Documents\ChatGPT\Fx"
git -C $repo fetch origin
if ($LASTEXITCODE -ne 0) { throw "git fetch failed" }
$wt = Join-Path (Split-Path $repo -Parent) ("Fx-FWD-285-298-" + (Get-Date -Format yyyyMMdd_HHmmss))
git -C $repo worktree add --detach $wt origin/feat/fwd-285-298-bls-secondary-schedule-audit
if ($LASTEXITCODE -ne 0) { throw "worktree failed" }
Set-Location $wt
python -m research.forward_bls_calendar_crosscheck `
  --calendar-report $calendarReport `
  --reference-file research/references/bls_2026_11_selected_html_schedule.json
```

もし `$cal` が失われていれば、以前の別worktree `Fx-FWD-273-284-*` の `out/bls_calendar_*.json` を見つけ、その**既存のファイル**を明示指定する。新しいICSのネットワーク取得は不要。

## 安全条件と次の工程

`NO_GO`、`safety_hold_latched=true`、`demo_orders_permitted=false`、`real_orders_permitted=false`。
楽天MT4・EA・AI API・取引注文・114価格CSV・研究ジャーナルに触れない。

この静的照合の次は、実フィードの欠落や同時刻衝突を調べ、改訂日付きHTML原本を安全に保存して将来の点時点差分を評価する。その後、発表前コンセンサスの時点証拠と突合する。いずれも人間の運用許可ではない。
