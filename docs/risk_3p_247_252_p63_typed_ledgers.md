# RISK-3P-247〜252 | G1の3ペア×5属性・未実証台帳の厳密型境界

対象は `scripts/audit_risk_3p_63_g1_ledger_alignment.py` の純合成・公開仕様間監査のみ。楽天MT4、EA、実ブローカー、注文やローカル秘密ログは利用しない。

- **247**: 3ペア×5属性のG1未実証15行の正常なオフライン照合を維持。未承認・NO_GOは不変。
- **248**: 4文書のroot・ネストした安全状態・15行×2台帳の辞書キーを組込みstr型確認後に比較。不正`__hash__`/`__eq__`を実行しない。
- **249**: pair・field・statusは組込みstr、ペアとフィールドの一覧は組込みlist＋strのみを許可。
- **250**: `False == 0` / `True == 1`の型偽装を、件数の組込みint／許可フラグのbool strict identityで拒否。
- **251**: ネストしたpermission/safety/stateの形式異常を固定コードで安全拒否。
- **252**: 想定外の読み込み・監査例外文を結果に転写せず固定`P63_OFFLINE_SOURCE_READ_FAILURE`へ変換。15件の回帰テストメソッドを追加。

```powershell
python -m unittest tests.test_risk_3p_247_252_p63_typed_ledgers -v
python -m unittest discover -s tests -p "test*.py"
```

Q109固定45ソース、production_authorized=false、P05 0/8 BLOCKED、G1実証0/15、FX-SAF原議0/15、FORM承認0/43、PHASE-1 BLOCKED、runtime NO_GO、安全停止ラッチtrue、verified_values=nullを維持。1取引0.5%、同時1%、日次1.5%、DD4%新規停止、DD5%全決済・本人承認、NY17:00日次境界は変更しない。実運用の承認・停止解除ではない。

GitHub ActionsのWindows Python 3.13 / IANA time zonesとRepository checksを最新PR headで確認し、mainへのマージは本人判断のみとする。
