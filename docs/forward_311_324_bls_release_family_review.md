# FWD-311〜324: BLS同一時刻イベントの名称候補を保守的に対応付ける

## 実測（2026-11-13）

ユーザーの既存worktree内で、11月20日15:00 UTCのICSイベント名が
`State Employment and Unemployment (Monthly)` と判明。

BLS公式[2026年11月発表予定一覧](https://www.bls.gov/schedule/2026/11_sched_list.htm)と
[Weekly Update](https://www.bls.gov/opub/update.htm)には同時刻10:00 ETに以下の2件を掲載：

- State Employment and Unemployment (Monthly) for October 2026
- Total Factor Productivity for Major Industries for Annual 2025

保存済みICSと11月のHTML参照の日時件数は4:5。欠落候補は後者だが、予定の改訂、ICS配信内容の変更、ファイル保存時点の差異の可能性は残る。
BLS自身のページ同士は独立の第三者出典ではない。タイトルの文字列対応だけではイベント同一性を確定できない。

## 新しい非破壊の診断結果

`python -m research.forward_bls_calendar_crosscheck` の既存の
`disputed_slot_title_evidence` の**下位フィールド**に
`release_family_candidate_review`を追加（既存のフィールド・スキーマは保持）。

- `relationship_status=UNIQUE_LEXICAL_CANDIDATES_ONLY` は、名前を完全一致させるか
  HTMLの `"<ICS title> for <period>"` に限り候補として扱う。大文字小文字や別名、表記ゆれの類推はしない。
- 全てのICSタイトルがちょうど1件のHTMLタイトルに対応し、重複や多対一もないときだけ
  `html_only_title_candidates_not_in_ics` にHTML側で追加の候補名を表示。
- 曖昧・不一致・多対一・重複は `NO_UNIQUE_TITLE_RELATIONSHIP` 等の状態とし、
  **HTMLにしかない指標名を推測しない**。各側12件超の候補は推測禁止。
- 候補の組み合わせは `provisional_title_pairs`、対応の種類は
  `EXACT_TITLE` または `ICS_TITLE_PREFIX_BEFORE_FOR` として表示。
- `all_title_relationships_independently_verified=false`、
  `automatic_missing_event_creation_permitted=false`、
  `source_revision_or_omission_resolved=false` を保持。
- 経済指標が出力上「不足候補」でも、ICS元データ・マクロ研究用の予定停止窓・
  発表前予想・MT4/EA・注文経路に**追加しない**。

## Windows側の使用法

前回の作業ディレクトリ：
`C:\Users\Suzuki\Documents\ChatGPT\Fx-FWD-285-298-20261113_100052`。
`$calendarReport` は取得済みICS研究用JSONの絶対パスとして設定済み。
元の `Fx` の未コミット変更には触れない。

PR #273のブランチを**新しいworktree**で検証する：

```powershell
$repo = "C:\Users\Suzuki\Documents\ChatGPT\Fx"
if (-not $calendarReport -or -not (Test-Path -LiteralPath $calendarReport)) {
    throw "前回の研究用カレンダーJSONがありません。"
}
git -C $repo fetch origin
if ($LASTEXITCODE -ne 0) { throw "git fetch failed" }
$wt = Join-Path (Split-Path $repo -Parent) ("Fx-FWD-311-324-" + (Get-Date -Format yyyyMMdd_HHmmss))
git -C $repo worktree add --detach $wt origin/feat/fwd-311-324-bls-release-family-review
if ($LASTEXITCODE -ne 0) { throw "worktree add failed" }
Set-Location $wt
python -m research.forward_bls_calendar_crosscheck `
  --calendar-report $calendarReport `
  --reference-file research/references/bls_2026_11_selected_html_schedule.json
```

出力の `disputed_slot_title_evidence[].release_family_candidate_review` を確認する。
`Total Factor Productivity for Major Industries for Annual 2025` が
`html_only_title_candidates_not_in_ics` に表示された場合も、
**元のICSに存在しない候補を発見したという意味だけ**である。

## 継続課題とNO_GO

- 改訂・追加を追跡するため、ICSとHTMLを時点ごとに取得時刻、本文SHA256、出典URL、
  取得失敗のまま保存できる安全な証拠収集契約を別途設計する（ネットワーク自動化は未承認）。
- 予想値を含む経済指標データは、発表前に公開時刻の検証可能な証拠として別途取得する。
- この限定的なBLS比較だけでは全通貨に関係する重要イベントの網羅を証明しない。
- 研究用 `NO_GO`、`safety_hold_latched=true`、`demo_orders_permitted=false`、
  `real_orders_permitted=false`を維持。新規取引・デモ注文も一切許可しない。
