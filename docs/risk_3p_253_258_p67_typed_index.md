# RISK-3P-253〜258：Q109固定45ソース台帳P67の型偽装拒否

公開リポジトリ内の `scripts/audit_risk_3p_67_source_index.py` は、固定45本の合成ソースとトレーサビリティを比較するオフライン監査器であり、実ブローカーのソースの真正性は証明しない。

- **253**: 正常な固定45ソースの合成PASSと常時NO_GOを維持。
- **254**: root、index、traceの組込みdict・組込みstrキーを辞書参照・set比較に先行して検査。
- **255**: 45行のsource mappingで不正なdict派生・不正ハッシュ／比較キーを拒否。
- **256**: ネストしたsafetyの厳密な5項目、bool/int一致混同、独自比較オブジェクトを拒否。
- **257**: scope/classificationの組込みstr型確認、45ファイル名の組込みstr型確認後にソート／比較する。
- **258**: 予期しない公開仕様読み込み例外を固定コード `P67_PUBLIC_INDEX_READ_OR_SCHEMA_FAILURE` で非反射拒否。14件の回帰テストメソッドを追加。

```powershell
python -m unittest tests.test_risk_3p_253_258_p67_typed_index -v
python -m unittest discover -s tests -p "test*.py"
```

## 安全境界

Q109の固定45ソースとproduction_authorized=false、P05 0/8 BLOCKED、G1実証0/15、FX-SAF原議0/15、FORM承認0/43、PHASE-1 BLOCKED、runtime NO_GO、停止ラッチtrue、verified_values=nullは不変。1取引0.5%、同時1.0%、日次1.5%、DD4%新規停止、DD5%全決済・本人承認、NY17:00の日次境界も不変更。

実MT4/EA・建玉・未約定・注文・ブローカー・元資料・秘密ログは使用しない。GitHub ActionsのWindows Python 3.13 / IANA time zonesとRepository checksをPR最新headで確認し、mainへのマージは本人が判断する。
