# RISK-3P-205〜210 | P60架空入力の検査順序と型境界

既存の7つの合成オフライン検査をまとめるP60について、外部から渡された`injected`の危険な辞書キーや値を**比較処理より前に**拒否する。

- **205**: 入力rootは組込みdictのみ、組込みstrキーだけを許可。未知スロットは固定コードで拒否。
- **206**: rootの辞書サブクラス、strサブクラス、不正ハッシュ/等値比較フックを評価しない。
- **207**: 子レポートの組込みdict／組込みstrキー確認を`dict.get`より前に行う。
- **208**: `status`・`runtime_go_no_go`は組込みstr、`errors`は組込みの空listを要求。未知の比較オブジェクトを評価しない。
- **209**: 権限偽装およびbool/intの未確認件数偽装を拒否し、安全停止を維持。
- **210**: 16件のオフライン負試験・正常系回帰を追加し、子の形式エラーが検出された後は下流の厳密結果検証へ不審な辞書を渡さない。

## 安全条件

G1実証0/15、P05 0/8、FX-SAF原議0/15、FORM承認0/43、PHASE-1 BLOCKED、runtime NO_GO、停止ラッチtrue、verified_values=nullの状態を維持。Q109固定45ソース・承認台帳・CI設定を変更しない。1取引0.5%、同時1.0%、日次1.5%、DD4/5%、NY17:00規則も不変更。MT4・EA・ブローカー・本番/デモ注文・機密ログを読み書きしない。

## テスト方法

```powershell
python -m unittest tests.test_risk_3p_60_adversarial_types -v
python -m unittest discover -s tests -p "test*.py"
```

既存P60テストとの互換性、Windows Python 3.13/IANA time zones、Repository checksの両CIをPR headで検証する。合成PASSは本番の安全認証、注文許可、停止解除ではない。#210のP61変更とは別ファイルであり、両PRマージ後は新たなmain SHAで全テストの回帰を実行する。
