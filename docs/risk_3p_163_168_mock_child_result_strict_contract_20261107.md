# RISK-3P-163〜168：架空証拠受入の子検査結果を全フィールド厳格照合

作成日：2026-11-07 JST。PR #199〜202がすべてmainにマージされたことをGitHubで検証し、統合後のmainから開発。

## 問題の再現と安全上の意味

`risk_3p_55_synthetic_ingress_contract.py`は、各子評価器P49/P50/P51の返却辞書のうち`status`、`runtime_go_no_go`、`safety_hold_latched`だけを確認していた。以下のような偽の子報告は、従来のチェックを通過し得た。

- `status="PASS_TWO_FAKE_WITNESSES_ONLY"`、`runtime_go_no_go="NO_GO"`、`safety_hold_latched=True`は保持。
- 同じ辞書に`real_mt4_read_authorized=True`、`orders_authorized=True`または`order_execution_authorized=True`の未認証情報を混入。
- `fictitious_fields=15`を虚偽の数値に改変、`errors`を欠落／非空に変えても子の3項目検査だけでは検出できない。

これは現実のブローカー接続が許可された事実ではないが、**架空検査の合成PASSという出力が不正な子報告を見逃す**検証上の欠陥である。

## 実装

| 工程 | 内容 |
|---|---|
| RISK-3P-163 | P49/P50/P51の成功時に必要な子報告全項目を、P55内の固定リテラル`EXPECTED_CHILD_REPORTS`で明示 |
| RISK-3P-164 | 組込みdict、全キーexact str、キーの完全一致、値のexact type／valueを比較。余計な「許可」や未知列を拒否 |
| RISK-3P-165 | `False↔0`、`True↔1`、カウンター改変、型偽装、`errors`欠落／非空を拒否 |
| RISK-3P-166 | 不審な辞書キー・値比較オブジェクト・dictサブクラスを比較前に拒否 |
| RISK-3P-167 | 元の3検査器の固定成功出力が契約に合致することを回帰確認。すべて架空データのみ |
| RISK-3P-168 | 既存P55テストへ16件追加し、Windows/Repository CIを統合済みmainに対して検証 |

## 境界と制約

ここで使う固定契約は、子評価器の**戻り値を検査するものであって、その元の架空情報の真正性を保証するものではない**。署名・独立証人・実口座データ・P05署名を取得しない。子結果全項目が一致しても本番トレード承認にはならない。

**P05 0/8 BLOCKED、G1実0/15、FX-SAF原議0/15、FORM 0/43、PHASE-1 BLOCKED、runtime NO_GO、safety_hold_latched=true、verified_values=null**を維持。正式な0.5%／1.0%／日次1.5%、DD4/5%、NY17:00、通信断・時計異常の条件は変えない。楽天MT4、EA、実建玉、未約定注文、秘密ログにアクセスしない。mainへのマージは行わない。
