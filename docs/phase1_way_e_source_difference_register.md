# E-GATE-02：安全重要仕様の原議差分・未決事項

2026-11-02。参照元は `specs/reconciliation_registry.json`、`specs/source_review_priority.json`、`specs/source_evidence.json`、`MASTER_SPEC.md`、`specs/safety_foundation.md`。**原議全文を本作業では取得・閲覧していない。** 下表は既存台帳の未決事項の整理であり、新たな一致判定、逐語引用、本人承認ではない。ローカル原本・候補抽出物はGit/GitHubに載せない。

| 安全仕様ID | 原議比較状態 | 本人が原議と照合・決定すべき主な点 |
| --- | --- | --- |
| FX-SAF-001 | SOURCE_UNAVAILABLE | 発注前0.5%の純資産基準、円換算、数量・注文状態・例外 |
| FX-SAF-002 | SOURCE_UNAVAILABLE | 同時1.0%の建玉/未約定/候補の合算、相関・換算・例外 |
| FX-SAF-003 | NEEDS_CLARIFICATION | NY17日次1.5%の入出金補正、損益項目の独立照合、欠落/二重計上/利益相殺 |
| FX-SAF-004 | SOURCE_UNAVAILABLE | 翌取引日再開とDD/重大停止の独立した解除条件 |
| FX-SAF-005 | NEEDS_CLARIFICATION | 単位当たり純資産DDの仮想口数・高水位・入出金/残高ゼロ例外 |
| FX-SAF-006 | SOURCE_UNAVAILABLE | DD2/3/4/5%の状態、鮮度/時計・30分解除と本人承認停止の優先順 |
| FX-SAF-007 | SOURCE_UNAVAILABLE | 重要イベント時刻、対象ペア、発表後の安全確認 |
| FX-SAF-008 | SOURCE_UNAVAILABLE | 独立反証結果、鮮度、修正回数、Python最終棄却条件 |
| FX-SAF-009 | NEEDS_CLARIFICATION | 期限切れ仮説を再評価できない場合の最大待機/決済条件 |
| FX-SAF-010 | SOURCE_UNAVAILABLE | SL後退禁止、サーバー制限、ATR参照時間足 |
| FX-SAF-011 | SOURCE_UNAVAILABLE | 通信異常の起点、L1/L2/L3の遷移・復旧と複数停止理由 |
| FX-SAF-012 | SOURCE_UNAVAILABLE | ウォッチドッグ確認、自動再起動3回の事故単位 |
| FX-SAF-013 | SOURCE_UNAVAILABLE | サーバー側SLが確認できない停止/再起動時の照合 |
| FX-SAF-014 | SOURCE_UNAVAILABLE | デモ/実口座差異、MT4接続と人間承認の境界 |
| FX-SAF-015 | SOURCE_UNAVAILABLE | 実装、PRマージ、安全仕様承認、本番有効化の分離 |

全15件は `source_kind=SUMMARY_ONLY`、`source_review=PENDING_ORIGINAL`、`implementation_approved=false`、`human_safety_approval=false`、`owner_approval=null`。一部Q116〜122の本人報告による抜粋文字列比較は台帳にあるが、元メッセージの完全な文脈・後続修正・要件全体の承認を証明しない。数値や解除条件は既存値を維持し、未決パラメータを推定してコードに固定しない。

## Q109〜Q115の出典レベル

| ID | `specs/source_evidence.json` の状態 | 実装・受入上の意味 |
| --- | --- | --- |
| Q109〜Q112 | 原議抜粋未登録 | 現行方針・検査スクリプトは存在するが、原文確認を捏造しない |
| Q113〜Q115 | `ORIGINAL` / `DIRECT_CHAT`、ローカルアーカイブ参照は `PENDING_LOCAL_ARCHIVE` | 当時の直接回答抜粋を登録済み。ただし全設計対話の原本照合・安全実装承認ではない |

`check_master_spec.py` はQ1〜110の番号、Q112/113/115の検査は台帳の構造を調べる。原議との意味一致、本人の意思、FX計算やMT4安全性は証明しない。本人がローカル原本の文脈・機密を確認し、相違/欠落を解消して決定ログへ明示承認を記録するまで、15件を実装用承認済みに変更しない。

## 原議照合の次の証拠

1. ユーザーがローカルの完全な原議アーカイブを保持し、該当設問と前後文脈・後続訂正を確認する。候補抽出は `docs/local_archive_guide.md` の手順に従う。
2. 出典位置、相違/省略、算式・例外、未決理由を要件ID別に整理する。公開するのは本人が機密審査した必要最小限の抜粋のみ。
3. 安全仕様の最終文面・試験・本人決定を別々にレビューし、承認参照を記録する。PR/CI成功やこの差分表の作成だけでは承認しない。
