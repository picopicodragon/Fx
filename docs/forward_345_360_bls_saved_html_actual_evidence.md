# FWD-345〜360: 同時取得のBLS原本HTMLとICSを直接照合（研究用）

## 実機結果を根拠とした作業

2026-11-13 10:48 JST頃、Windows別worktreeでFWD-325〜344の
`research.forward_bls_dual_snapshot --allow-network --days-forward 14` が成功。
ICS `calendar_event_count=4`、SHA256
`92a350111ace106deaab5584e4084366bd367b594a0d0bad116008d82d63e501`、
保存HTML SHA256
`db4cb05e91e67b434f16f01d37540258e780cad0bffa001607f08fc2ef87e071`。
状態は `BLS_DUAL_FORMAT_SNAPSHOT_RESEARCH_HOLD_NO_GO`。

PR #271〜273 は**静的に転記されたHTML一覧**とICSの日時/候補タイトルを照合していた。
11月20日10:00 ETには、HTML側で
`State Employment and Unemployment (Monthly)` と
`Total Factor Productivity for Major Industries` の2系列が掲載。
ICSで観測したのは前者の短縮名だけ。従来検査が疑う後者の欠落を、
今回保存できた**HTML原本から直接**確認できるようにする。

## 新しい読み取り専用コマンド

```powershell
python -m research.forward_bls_saved_html_audit --snapshot-dir $snap1
```

1. `snapshot.json`、ICS、HTML、calendar.jsonのハッシュと再パース結果を再検証。不完全バンドルや改ざん、自己不一致では直ちにFail Closed。
2. 元HTML本文の表を標準ライブラリHTMLParserで構造解析。唯一の `Date / Time / Release` の3列テーブルと2026年11月の厳格なEastern Time・曜日検証を要求。表の欠落/異常、他月混入、曖昧なDSTではFail Closed。
3. 無時刻の既知祝日だけを除き、11月全体の正式時刻とタイトルを抽出。固定の11月参照ファイルに依存せず、保存HTMLの実データと同じスナップショットのICSを**日時の多重集合**で比較。
4. 不一致の日時だけ、ICS/HTMLそれぞれの元タイトルと、完全一致または `for [期間]` が付くタイトルの暫定候補を表示。欠落指標を自動補完しない。
5. `html_month_selected_release_item_count`、`html_event_count_within_window`、`ics_event_count`、`missing_html_slot_instance_count`、`disputed_slot_title_evidence` を出力。結果が一致してもイベントの本人確認・配信完全性・第三者認証とみなさない。
6. HTML構造の想定が実原本と異なる場合、例外発生・コマンド失敗として判別する。**未検証の日時抽出を強引に継続しない**。

## Windows実行手順

コマンド実行場所は、前回のスナップショット保存先を持つ
`C:\Users\Suzuki\Documents\ChatGPT\Fx-FWD-325-344-20261113_104843` でよい。
前回の `$snap1` は相対パス `out/bls_dual_...` であり、移動前に次のように絶対パスを保存する。

```powershell
Set-Location "C:\Users\Suzuki\Documents\ChatGPT\Fx-FWD-325-344-20261113_104843"
if (-not $snap1 -or -not (Test-Path -LiteralPath $snap1)) {
    throw "保存済みスナップショットが見つかりません"
}
$originalBundle = (Resolve-Path -LiteralPath $snap1).Path
$repo = "C:\Users\Suzuki\Documents\ChatGPT\Fx"
git -C $repo fetch origin
if ($LASTEXITCODE -ne 0) { throw "fetch failed" }
$wt = Join-Path (Split-Path $repo -Parent) ("Fx-FWD-345-360-" + (Get-Date -Format yyyyMMdd_HHmmss))
git -C $repo worktree add --detach $wt origin/feat/fwd-345-360-bls-saved-html-evidence-audit
if ($LASTEXITCODE -ne 0) { throw "worktree add failed" }
Set-Location $wt
python -m research.forward_bls_saved_html_audit --snapshot-dir $originalBundle
```

既存の `Fx`（未コミット変更あり）は切り替えない。スナップショットを**再ダウンロードしない**。新規バンドルを作る必要もなく、元の2026-11-13観測原本のまま解析する。

## 認証と運用境界

- 同一BLS発行元のHTMLとICSの照合は**独立した第三者発行元検証ではない**。保存時刻はローカル時計であり、改訂前後の正当性・原本の公開時刻を認証しない。
- 今回HTMLを正しく抽出できても、世界の主要FX指標、日本・欧州・中央銀行の完全カレンダーは未取得。発表前市場コンセンサスも未取得。
- 本検査は純粋にオフラインで入力を書き換えず、HTTP0回、AI API0回、MT40回、実/デモ注文0回。
- `runtime_go_no_go=NO_GO`、`safety_hold_latched=true`、`demo_orders_permitted=false`、`real_orders_permitted=false` を維持。
- 次工程では点時点コンセンサスの外部原本保存、観測データ真正性と市場時刻の独立照合を優先。デモフォワード運用は別途安全監査が必要。
