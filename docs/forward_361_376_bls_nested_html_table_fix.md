# FWD-361〜376: BLSの入れ子HTMLテーブルを安全側で解析

## 2026-11-13 Windowsの実診断

保存済みBLSスナップショットの `integrity.verify` は `PASS`。
元の `research.forward_bls_saved_html_audit` は
`BLS dated release table absent or ambiguous` で停止。

読み取り専用診断では `html_table_count=1`、
唯一の表が `row_count=1` / 2列であることを確認。
その2列は「BY MONTH ...」ナビゲーションと
「November 2026 Month View | List View ... NOTE: ...」のページ本文。
この構造により、少なくとも**外側のレイアウトテーブルのみ取得された**ことが分かる。

現実のHTMLにはネストした表がある可能性があるが、元HTMLファイル全体のタグ構造を
本会話からは直接確認できず、単なる推測で日時や名称を作らない。

## 原因候補と修正

旧 `_TableRows` は `depth == 1` の表のみを読み、入れ子の表（`depth >= 2`）をすべて無視していた。
今回、すべてのテーブル階層で `tr`/ `th`/`td` を別々に追跡する**スタック式HTMLParser**に変更。
外側のセルの文章と内側の表のイベント名を誤連結しない。

- 深さ20まで、閉じられない表・二重開始セル/行など構造矛盾は `InputError`。
- 取得した各表の中で唯一の `Date`/`Time`/`Release` 3列ヘッダーにのみ発表イベントの抽出を認める。
- ヘッダーが複数あればあいまいとして拒否。別月・不正曜日・DST曖昧・異常な時刻も拒否。
- ソースSHA256・マニフェスト・二重フォーマット取得時刻の検証を事前に実施する。
- 未認証のタイトルの曖昧一致と自動イベント補完はしない。
- **実HTMLに入れ子3列表がなければ依然Fail Closed**とし、構造を確認してから次の適合実装へ進む。

合成テストは2列の外側レイアウト表＋内側のBLS3列発表表、
2段階の入れ子、同名候補表2つ、壊れた閉じタグ、月不一致、
保全原本の改ざん拒否、研究NO_GO維持を検証する。

## Windowsでの再実行

保存済みスナップショットは前回のまま。新しいネットワーク取得をしない。
現在のPowerShellセッションで `$originalBundle` は既存の
`Fx-FWD-325-344-20261113_104843\out\bls_dual_...` の絶対パス。

```powershell
$repo = "C:\Users\Suzuki\Documents\ChatGPT\Fx"
if (-not $originalBundle -or
    -not (Test-Path -LiteralPath $originalBundle)) {
    throw "保存済みBLSスナップショットの絶対パスが見つかりません"
}
git -C $repo fetch origin
if ($LASTEXITCODE -ne 0) { throw "git fetch failed" }
$wt = Join-Path (Split-Path $repo -Parent) ("Fx-FWD-361-376-" + (Get-Date -Format yyyyMMdd_HHmmss))
git -C $repo worktree add --detach $wt origin/fix/fwd-361-376-bls-nested-html-tables
if ($LASTEXITCODE -ne 0) { throw "worktree add failed" }
Set-Location $wt
python -m research.forward_bls_saved_html_audit --snapshot-dir $originalBundle
```

`Fx` 本体は未コミット変更のあるままで保全。前回のworktreeや証拠原本を削除しない。
出力が `BLS_SAVED_HTML_ICS_AUDIT_HOLD_NO_GO` になった場合も、
第三者認証や全FXイベント網羅を認めたことにはならない。


解析できない場合でも、新規取得やパーサー緩和を行わず、同じ保存原本に対して以下の診断が可能：

```powershell
python -m research.forward_bls_html_structure_diagnose --snapshot-dir $originalBundle
```

出力は表の個数、各表の行数/列数、3列ヘッダー数、ソースSHA一致だけ。
**日時・イベント名・元HTML本文は出力しない**。実BLSのHTML構造が
さらに想定と異なった場合の次の最小変更に使う。

## 安全条件

`NO_GO`、`safety_hold_latched=true`、
`demo_orders_permitted=false`、
`real_orders_permitted=false` を保持。
ネットワーク0、API0、MT4/EA/ブローカー0、デモ/実注文0。
既存の資金管理0.5%／1.0%／1.5%、DD停止条件、イベント停止窓、その他安全仕様は一切変更しない。
