# FWD-393〜408：BLS保存原本の不一致と発表前予想を統合研究ボードへ連結

## 根拠：2026-11-13 実Windows検証

新規 `research.forward_bls_macro_source_gate` に対して、保存済みBLS ICS/HTML原本バンドルを読み取り専用検査：
`status=BLS_MACRO_SOURCE_CONSENSUS_READINESS_HOLD_NO_GO`、
`asof_utc=2026-11-13T02:49:10Z`、
`snapshot_html_observed_at_utc_clock_unattested=2026-11-13T01:48:45Z`。
ICS4件／HTML5件、欠落候補は11月20日15:00Zの1件。
データ鮮度は24時間以内だが、発表前コンセンサス原本は無く、
FX主要イベントの網羅性・出典の独立認証・ブローカー側停止は未立証。

## 目的

従来の統合研究ボード `research.forward_macro_integrated_readiness` は
価格CSV/AI研究・任意BLS ICSカレンダー・任意の発表前コンセンサス証拠をまとめた。
今回、そのボードへ**保存済み二形式BLS原本の監査結果と保留理由を同時に含める**。
新しい研究フェーズのGO判定機能でも、MT4/EA稼働許可でもない。

## 互換性を保つCLI拡張

既存引数をそのまま維持し、新たに `--bls-snapshot-dir <absolute-folder>`
を追加する。この引数が指定された場合、同フォルダーの
`bls.ics`、`bls_schedule.html`、`calendar.json`、`snapshot.json` を
SHA256・発表予定表・時刻に関して再検証する。

- `--calendar-report` が省略されていても、検証済み原本バンドルに含まれる
  `calendar.json` を研究用イベント窓に用いる。
- `--calendar-report` と `--bls-snapshot-dir` を共に指定した場合は、
  保存原本の `calendar.json` と**JSON全項目一致**が必要。
  一つでも違えば `FAIL_CLOSED`、出力ファイル未作成（上書き不可）。
- `--forecast-archive` がある場合は既存アーカイブの整合性と
  カレンダーSHA、イベント名、時刻の厳格な一致を要求。
  **ローカル保存のSHAだけで予想公開時刻を認証したとは認めない**。
- `unresolved_holds` にBLSの原本間の不一致、鮮度、
  コンセンサス未取得、全FXイベント網羅性不足などを追加。
  `next_research_actions` は重複排除して結果に残す。
- 追加の表示：`bls_original_source_bundle_verified`、
  `bls_html_ics_schedule_disagreement`、
  `bls_html_only_missing_slot_instances`、
  `bls_snapshot_older_than_24h`、`bls_saved_calendar_ics_sha256`。
- 既存 `schema=fx_fwd_macro_integrated_forward_research_v2` と
  `status=INTEGRATED_MACRO_FORWARD_READINESS_HOLD_NO_GO` はそのまま。
- 保存原本が指定されない従来CLIでは、追加項目を `null` などの
  **未検証**で返し、勝手に二形式一致とはみなさない。

## Windowsでの運用例

`--session` の値は過去に取得したユーザー自身の実フォワード研究セッションを使用する。
**未確認のフォルダーや仮想セッションを作って「114価格CSVあり」と見せかけないこと。**

例（`$sessions` に利用者が既に正しい `--session` 引数を保存している場合のみ）：

```powershell
# 先のFWD-377〜392で使った原本の絶対パス（再ダウンロード不要）
if (-not $originalBundle -or -not (Test-Path -LiteralPath $originalBundle)) {
    throw "BLS保存原本の絶対パスが見つかりません。"
}
# 既存セッションが確認できないときは、この統合コマンドを無理に実行しない。
$asof = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
# python -m research.forward_macro_integrated_readiness `
#   --session "CHECKED_LABEL=CHECKED_SESSION_PATH" `
#   --bls-snapshot-dir $originalBundle `
#   --asof-utc $asof `
#   --out "out/integrated_source_evidence_$(Get-Date -Format yyyyMMdd_HHmmss).json"
```

既存研究セッションパスがまだ不明なときの**すぐ実行可能な根拠検査**は
FWD-377〜392の
`python -m research.forward_bls_macro_source_gate --snapshot-dir $originalBundle --asof-utc $asof`
であり、これは実機で既に成功している。

## CIと安全境界

既存の統合ボード入力互換、保存原本と外部ICSの不一致拒否、
欠落したコンセンサス別保留、古いスナップショット、
壊れた原本Fail Closed、出力未書込、価格データ非改変などをテスト。
- ネットワーク0、AI API0、MT4/EA接続0、デモ/実注文0。
- `NO_GO`、`safety_hold_latched=true`、
  `demo_orders_permitted=false`、`real_orders_permitted=false`固定。
- 研究資料の整合性は、未来の売買・投資収益・イベント停止の実動作を保証しない。
- 元Fxフォルダーや既存outフォルダーを自動clean/stash/resetせず、別worktreeでの開発・PRを維持。
