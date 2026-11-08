# RISK-3P-259〜264 | P69合成ソース静的AST監査の想定外例外を安全拒否

P69の6固定純合成Pythonソースについて、モジュールのインポート・実行ではなく、**公開リポジトリのテキストを静的AST解析する範囲**で例外境界を強化する。

- **259**: 既存6本の合成静的検査のPASS・常時NO_GOを維持。
- **260**: `ast.parse`の未想定Python例外を固定 `P69_BAD_PYTHON_SYNTAX` で拒否。
- **261**: AST走査などパース後の未想定例外を同じ固定コードで拒否。
- **262**: 公開ソースの読み込み・スキャナー呼び出し中の未想定例外を `P69_SOURCE_UNAVAILABLE` へ固定し、例外文を非反射。
- **263**: 機密を想定したテスト用文字列が診断結果へ含まれないことを検証。
- **264**: 異常終了後の独立した純合成静的検査の正常復帰を確認。

`tests/test_risk_3p_259_264_p69_ast_exceptions.py` に7テストメソッド、複数例外のsubTestを追加する。

```powershell
python -m unittest tests.test_risk_3p_259_264_p69_ast_exceptions -v
python -m unittest discover -s tests -p "test*.py"
```

## 安全境界

Q109固定45ソースとproduction_authorized=false、P05 0/8 BLOCKED、G1実証0/15、FX-SAF原議0/15、FORM承認0/43、PHASE-1 BLOCKED、runtime NO_GO、停止ラッチtrue、verified_values=nullを維持。0.5%/同時1%/日次1.5%、DD4%/5%、NY17:00、人間承認条件は不変更。MT4、EA、注文、建玉、未約定、証券会社接続、秘密ログアクセスなし。

`Exception`派生の想定外Python例外を拒否するが、`BaseException`派生のSystemExit/KeyboardInterrupt、OS強制終了、複雑な動的インポート・ネイティブモジュール、実運用の副作用安全性までは証明しない。GitHub ActionsのWindows Python 3.13/IANA time zonesとRepository checksを最新headで確認する。
