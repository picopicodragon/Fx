# RISK-3P-235〜240: P64合成キャンペーンの想定外例外を安全拒否

**対象**: `scripts/risk_3p_64_adversarial_consistency_campaign.py`。7種の純合成レポート×10種の模擬破損、計70試行を行う検査器。これは実運用の安全認証ではない。

- **235**: 通常の70件模擬破損PASSを維持しつつ `runtime_go_no_go=NO_GO` を維持。
- **236**: 子レポート生成における予期しない例外を固定拒否。
- **237**: 模擬破損の生成段階での想定外例外を固定拒否。
- **238**: P61厳密契約確認中の想定外例外を固定拒否。
- **239**: P60統合QAの想定外例外を固定拒否。
- **240**: 異常後の独立した正常呼び出しが合成PASSへ戻ることと、例外文非反射を回帰確認。

Pythonの `Exception` 派生例外のみ捕捉し、入力値・例外のメッセージ・部分の模擬証拠を返さず `P64_OFFLINE_ADVERSARIAL_HARNESS_FAILURE` を使用する。`SystemExit`・`KeyboardInterrupt`・プロセス停止を捕捉できるとの主張はしない。

## テスト

`tests/test_risk_3p_235_240_p64_unexpected_exceptions.py`に6テストメソッド（6種類の例外subTestあり）を追加。

```powershell
python -m unittest tests.test_risk_3p_235_240_p64_unexpected_exceptions -v
python -m unittest discover -s tests -p "test*.py"
```

## 絶対安全境界

P05 0/8 BLOCKED、G1実証0/15、FX-SAF原議0/15、FORM承認0/43、PHASE-1 BLOCKED、runtime NO_GO、停止ラッチtrue、verified_values=null、production_authorized=false。Q109固定45オフラインソース、0.5%/1%/日次1.5%損失制約、DD4%/5%の制御、NY17:00境界は不変。楽天MT4、EA、ブローカー、注文、建玉、未約定、ローカル秘密ログを使用しない。mainマージは本人のみが判断する。

最新headに対するWindows Python 3.13 / IANA time zonesとRepository checksの両ジョブをCIで検証する。
