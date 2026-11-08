# RISK-3P-199〜204：P61合成結果のキー・型境界強化

**範囲**：合成7サブレポートの契約検証器 `scripts/risk_3p_61_strict_offline_result_contract.py`。実口座、MT4、EA、注文送信、実証原議、秘密ログにはアクセスしない。

## 変更

- **199**：rootを組込みdictと確認。既存7サブレポートとの完全一致を維持。
- **200**：rootのキーが厳密な組込みstrであることを、集合演算より先に確認。独自`__hash__`／`__eq__`の比較処理を避ける。
- **201**：各サブレポートの組込みdict／組込みstrキー完全一致。辞書サブクラスを拒否。
- **202**：値は期待される組込みのstr／int／bool／Noneに型一致してから比較。`False == 0`の型混同や不正比較オブジェクトを拒否。
- **203**：`errors`の組込みlist境界。list派生型、未知の注文権限フィールドを拒否。
- **204**：16件の負試験・正常系回帰試験。固定エラーコード、入力秘密文字列非反射、`NO_GO`・安全停止ラッチ維持を確認。

## 互換性・制約

- 出力のキー・status名・固定エラーコードは変更せず、受入境界だけを狭くする。
- Q109の45登録ソースと既存テスト対応はそのまま。補助のテストファイル `tests/test_risk_3p_61_adversarial_types.py`を追加する。
- P05 0/8、G1実証0/15、FX-SAF原議0/15、FORM承認0/43、PHASE-1 BLOCKED、runtime NO_GO、安全停止ラッチtrue、`verified_values=null`を保持。
- 1取引0.5%、同時1.0%、日次1.5%、DD4/5%、NY17:00等のリスク制限と本人承認条件は変更しない。

## 実行と検証

```powershell
python -m unittest tests.test_risk_3p_61_adversarial_types -v
python -m unittest discover -s tests -p "test*.py"
```

GitHub ActionsのWindows Python 3.13/IANA time zonesとRepository checksをPR head SHAに対して確認すること。合成PASSは安全重要MODULE/PHASE承認、本番売買許可、外部データの真正性を証明しない。
