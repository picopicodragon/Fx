# RISK-3P-169〜174：架空G1 3×5検証器の不正型・キー・例外対策

作成日：2026-11-07 JST。PR #199〜202のマージ済みmainから独立したオフラインブランチで実装。PR #203とはソース変更箇所が重複しない。

## 欠陥

架空G1検証器`validate_risk_3p_34_synthetic_provenance.py`は、外側と各行・架空出典の組込み辞書を`set(obj)`によって検査していた。受け取った辞書にカスタムPythonキーが含まれると`__hash__`・`__eq__`を実行する余地がある。また`classification`、`target_pairs`内の項目、`row["pair"]`、`row["unit"]`などの比較を型確認なしに実行していた。

この検証器は架空の2証人比較器P50の**上流依存**でもあるため、上流の不正型が例外発生・意図しない比較を誘発すると下流の安全判断の根拠が不明瞭になる。

## 工程

| 工程 | 変更 |
|---|---|
| RISK-3P-169 | root・15行・架空出典の辞書キーを、組込みdict／exact str型で事前検査してから集合比較 |
| RISK-3P-170 | `classification`、通貨ペア・属性リスト、行`pair`／`field`／`status`／`unit`／架空シンボル／出典kindを型確認してから比較 |
| RISK-3P-171 | 予期しない検証例外は固定コード`P34_SYNTHETIC_VALIDATION_EXCEPTION`でFail Closed。機密らしき値や例外文は結果に反射しない |
| RISK-3P-172 | 根本の悪意あるキー、文字列サブクラス、危険な比較演算、偽許可をテスト |
| RISK-3P-173 | 元の15件G1架空レコード・NO_GO・停止ラッチを保持、P50の既存検証と一致することを全回帰で確認 |
| RISK-3P-174 | P34の既存テストファイルに14件追加、文書化、PRとWindows/Repository CI。新規運用モジュールなし |

## 承認境界

`PASS_SYNTHETIC_CONTRACT_ONLY`は架空の3ペア（USD/JPY、EUR/JPY、EUR/USD）×5属性の形式検査であり、本物のブローカー証拠・適正な契約値・証拠出典を認証しない。検査器は現実のMT4や証券会社に接続せず、口座や実注文、個人ファイルを読み取らない。Python辞書の悪意あるキーを**挿入する瞬間**の処理までは防止できない。

**P05 0/8 BLOCKED、G1実0/15、FX-SAF原議0/15、FORM 0/43、PHASE-1 BLOCKED、runtime NO_GO、安全停止ラッチtrue、verified_values=null**を維持。正式な損失上限0.5%／1.0%／日次1.5%、DD4/5%、NY17:00、通信断等の停止条件は変更しない。mainへのマージは行わない。
