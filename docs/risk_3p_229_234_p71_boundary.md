# RISK-3P-229〜234 | P71最上位合成整合性ゲートのFail Closed強化

`scripts/risk_3p_71_offline_integrity_gate.py`が統合する7つの合成レポートについて、**入力キーの組込み型検査を集合比較・辞書参照より前に実施する**。既存の誤認拒否、合成成功時も本番NO_GO、安全停止ラッチを維持する。

## 工程

- **229**：rootは組込みdictかつ組込みstrキーと確認。未知項目は固定拒否。
- **230**：rootの不正`__hash__`・`__eq__`、str派生型、不明な機密値を比較前に拒否。
- **231**：7つの子レポートも組込みdict/strキーを先行確認。
- **232**：status・errors・runtimeは厳密な組込みstr/空listと確認してから値比較。独自比較オブジェクト拒否。
- **233**：全項目型一致、偽注文権限、bool/intの証拠カウント混同拒否を保持。
- **234**：予期しない子例外と不完全な7件の統合結果を機密非反射の固定エラーで拒否。正常な純合成は従来のPASS書式だけを維持。

## テスト

`tests/test_risk_3p_229_234_p71_boundary.py`へ17件のテストメソッドを追加。既存P71テストと、main最新状態の全unittestをGitHub ActionsのWindows Python 3.13/IANA time zones、Repository checksで検証する。

```powershell
python -m unittest tests.test_risk_3p_229_234_p71_boundary -v
python -m unittest discover -s tests -p "test*.py"
```

## 安全条件

Q109固定45オフラインソースとproduction_authorized=false、P05 0/8 BLOCKED、G1実証0/15、FX-SAF原議0/15、FORM承認0/43、PHASE-1 BLOCKED、runtime NO_GO、停止ラッチtrue、verified_values=nullは不変。1取引0.5%、同時1.0%、日次1.5%、DD4%新規停止、DD5%全決済と人間承認、NY17:00日次境界にも変更なし。

この検証は合成データ/既存公開仕様の範囲のみ。MT4・EA・楽天証券・注文・建玉・未約定・ローカルの私有ログ・原議資料は読まず、本番権限や停止解除を与えない。#213/#214とは異なる変更ファイルを使用し、mainへのマージは人間のみが判断する。
