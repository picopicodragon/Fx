# RISK-3P-241〜246: P62 Q109トレーサビリティ監査の型境界

`scripts/audit_risk_3p_62_offline_traceability_graph.py` の純オフライン・リポジトリ公開仕様監査を強化する。実MT4、EA、ブローカー、注文、秘密ログには接続しない。

- **241**: 既存のQ109追跡台帳を正常時は合成専用PASS、運用NO_GOで保持。
- **242**: root manifestの組込みdict・組込みstrキーを辞書参照前に検証。不審な`__hash__`/`__eq__`、str/dictサブクラスを拒否。
- **243**: 各対応レコードの組込みdict・組込みstrキーを集合比較前に検証。
- **244**: `production_authorized=false`のbool/int混同や不正な対応形式を拒否。
- **245**: 公開ソース台帳下流チェックの想定外例外を例外文非反射の固定`P62_CANNOT_READ_PUBLIC_TRACEABILITY`へ。
- **246**: 12件のテストメソッド（正常系と負試験）で異常後の独立実行も回帰確認。

```powershell
python -m unittest tests.test_risk_3p_241_246_p62_type_boundary -v
python -m unittest discover -s tests -p "test*.py"
```

Q109の固定45ソース・テスト対応・承認台帳・production_authorized=falseは不変更。P05 0/8 BLOCKED、G1実証0/15、FX-SAF原議0/15、FORM承認0/43、PHASE-1 BLOCKED、runtime NO_GO、停止ラッチtrue、verified_values=null、1取引0.5%、同時1.0%、日次1.5%、DD4%・5%、NY17:00の安全条件を維持。mainへのマージは本人のみ。

合成・公開仕様の検査PASSは実ブローカーの安全性、本人承認、稼働許可を意味しない。GitHub ActionsのWindows Python 3.13/IANA time zonesとRepository checksで最新headを確認する。
