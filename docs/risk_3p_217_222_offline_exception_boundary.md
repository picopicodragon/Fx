# RISK-3P-217〜222 | 合成監査の予期しない例外をFail Closed

対象：`scripts/risk_3p_60_offline_ingress_quality_gate.py`と`scripts/risk_3p_65_integrated_offline_audit.py`。

## 工程
- **217**：既存P60の合成7検査は正常時のPASS（形式検証のみ）と常時NO_GOを保持。
- **218**：既存P65の合成6検査も正常時のPASS（設計検証のみ）と常時NO_GOを保持。
- **219**：P60子検査が予期しないPython例外を起こした場合、秘密や例外文を反射せず固定コード`P60_MISSING_OR_INVALID_OFFLINE_INPUT`で拒否。
- **220**：P65にも同様に固定コード`P65_OFFLINE_QUALITY_INPUT_INVALID`で拒否する境界を追加。
- **221**：例外発生でも本番/実MT4/EA権限の全否定、P05/G1実証カウントゼロ、NO_GO、停止ラッチtrueを保持。
- **222**：例外が解消された独立合成呼び出しは正常に動作するが、停止解除、本番移行、本人安全承認にはならない。

## 検証
`tests/test_risk_3p_217_222_unexpected_offline_exceptions.py`に8つのテストメソッドを追加。RuntimeError・AssertionError・ZeroDivisionError・UnicodeError・LookupError・NotImplementedErrorを各検証器に投入し、例外文が結果に含まれないことを検査。

```powershell
python -m unittest tests.test_risk_3p_217_222_unexpected_offline_exceptions -v
python -m unittest discover -s tests -p "test*.py"
```

これはPython内部の合成検証のFail Closed化に限定される。プログラムの強制終了、OS障害、ハードウェア障害、任意のPythonコード実行や資源枯渇を完全に防ぐことはできない。将来本番コードへ転用する許可も与えない。

## 安全境界

P05 0/8 BLOCKED、G1実証0/15、FX-SAF原議0/15、FORM承認0/43、PHASE-1 BLOCKED、runtime NO_GO、safety_hold_latched=true、verified_values=null、production_authorized=false。Q109固定45ソース・既存の本人承認台帳、リスク0.5%/1.0%/日次1.5%、DD4%/5%、NY17:00境界、注文/停止復旧条件は不変。楽天MT4、EA、注文、建玉、未約定、ブローカー、機密ログへのアクセスなし。mainへのマージは本人判断のみ。

CI：このブランチの最新headに対するWindows Python 3.13 / IANA time zonesとRepository checksの両方が成功した場合のみ「テスト完了」とする。
