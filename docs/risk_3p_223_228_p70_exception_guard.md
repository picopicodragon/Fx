# RISK-3P-223〜228 | P70合成障害試験の例外Fail Closed

対象：`scripts/risk_3p_70_fail_closed_campaign.py`。P70は固定29件の合成異常検査であり、実取引の安全性や障害復旧の保証ではない。

## 作業範囲

- **223**：従来どおり29件の合成試験が形式上PASSしても本番NO_GO・安全停止ラッチ維持。
- **224**：静的AST境界監査で予期しない例外が起きても、固定コードのみを返す。
- **225**：インポート監査とソース台帳読み込みでの例外を安全拒否。
- **226**：Q109台帳検査の例外を安全拒否。
- **227**：上流P65の合成検査出力/監査エラーを機密非反射で拒否。
- **228**：異常終了後の別合成呼び出しは正常に実行可能。例外時の途中実行数はPASSカウントではない。

`tests/test_risk_3p_223_228_p70_exception_guard.py`に8件のテストメソッド。RuntimeError、AssertionError、ZeroDivisionError、UnicodeError、LookupError、NotImplementedErrorを合成AST監査に注入。実行側は`except Exception`を追加して固定`P70_SYNTHETIC_CAMPAIGN_INPUT_INVALID`に変換する。BaseExceptionやプロセス強制終了は捕捉しない。

## 安全状態

P05 0/8 BLOCKED、G1実証0/15、FX-SAF原議0/15、FORM承認0/43、PHASE-1 BLOCKED、runtime NO_GO、停止ラッチtrue、verified_values=null。Q109の45登録ソース、production_authorized=false、0.5%/1%/日次1.5%、DD4/5%、NY17:00の制約および本人承認条件は変更しない。楽天MT4・EA・ブローカー・注文・建玉・未約定注文・機密ログ・本人原議にアクセスしない。

## CI検査

```powershell
python -m unittest tests.test_risk_3p_223_228_p70_exception_guard -v
python -m unittest discover -s tests -p "test*.py"
```

Windows Python 3.13 / IANA time zonesとRepository checksの両ジョブで、本PRの最新headに対する成功を確認する。#213のP60/P65修正とは別のソース・テストファイルである。mainへの統合は本人判断のみ。
