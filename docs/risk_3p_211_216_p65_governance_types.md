# RISK-3P-211〜216 | P65統合監査の厳密型境界

P65の6件の**純合成ガバナンス監査結果**について、未確認の入力辞書・キー・値がPythonの暗黙比較や外部定義フックに到達することを回避する。外部の楽天MT4、EA、実建玉、秘密ログ、注文、原議資料にはアクセスしない。

- **211**：rootは組込みdict、組込みstrキーだけ受理。未知キーやroot派生型はFail Closed。
- **212**：rootの独自hash／等値比較キーとstrサブクラスを先行拒否。
- **213**：6子レポートの辞書型・キー型を集合比較・dict.get前に検査。
- **214**：status、runtime、errorsの値型を比較前に確認し、独自`__eq__`やlistサブクラスを拒否。
- **215**：0とFalseのカウント混同、偽の実MT4権限フラグを拒否。
- **216**：16件の負試験・正常系回帰、固定非反射エラー、NO_GOと安全停止ラッチの維持。

変更するのはP65の合成監査器、追加テスト、本文書だけ。既存Q109の45登録ソース・テスト、その他の安全実装・承認台帳を変更しない。

**固定の安全状態**：P05 0/8 BLOCKED、G1実証0/15、FX-SAF原議0/15、FORM承認0/43、PHASE-1 BLOCKED、runtime NO_GO、安全停止ラッチtrue、verified_values=null、production_authorized=false。1取引0.5%／同時1.0%／日次1.5%、DD4%新規停止、DD5%全決済・人間承認、NY17:00取引日の区切りを維持する。

## 実行

```powershell
python -m unittest tests.test_risk_3p_65_adversarial_types -v
python -m unittest discover -s tests -p "test*.py"
```

PRの最新headに対応するWindows Python 3.13/IANA time zonesとRepository checksのCI結果を確認する。#210（P61）・#211（P60）と別ファイルの独立変更。最終的にmainへマージされた際は、その時点のmainで全テストを再実行する。合成PASSは実口座の安全性、停止解除、本人承認や自動売買許可を意味しない。
