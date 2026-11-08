# RISK-3P-193〜198 | マージ後の安全台帳・型偽装回帰検査

状態: **オフライン検証のみ / 実運用NO_GO**。2026-11-08時点のmainをベースに、既存台帳を**変更せず**参照する16件のPython unittestを追加。

- **193**: `specs/acceptance_registry.json`、`specs/source_review_priority.json`、`specs/traceability.json`の安全停止・未承認の共通基準を照合。
- **194**: 安全重要MODULE・全PHASEの承認偽造やACCEPTED誤認を拒否。
- **195**: FX-SAF-001〜015の原議未確認・本人承認なしを検査。偽の元資料URL、`0 == False`の型混同を拒否。
- **196**: Q109の既存45本のオフラインソースを固定し、`production_authorized=false`・テスト対応を検査。bool/int偽装拒否。
- **197**: 安全要件IDの重複・欠落、45ソース台帳の欠落を拒否。
- **198**: dict派生型、不正な台帳要素、承認キー欠損を拒否。

## 変更範囲

追加ファイルは `tests/test_risk_3p_post_merge_safety_ledger.py` のみ（本書を除く）。**既存の安全台帳・元資料・本番コード・CI設定・Q109トレーサビリティの固定45ソースを変更しない**。検査はPython標準ライブラリを使う。テストコードの関数は入力された辞書とリストを検査するだけで、ローカル元資料、シークレット、ネットワーク、MT4、EA、ブローカー、注文を参照しない。

## 検証コマンド

```powershell
python -m unittest tests.test_risk_3p_post_merge_safety_ledger -v
python -m unittest discover -s tests -p "test*.py"
```

テストを追加したPRの **head SHA** について、GitHub ActionsのWindows Python 3.13 / IANA time zones、Repository checksをそれぞれ確認する。緑のCIは合成／台帳レベルのみの根拠であり、実口座安全認証ではない。

## 運用禁止状態

P05 0/8 BLOCKED、G1実証0/15、FX-SAF原議0/15、FORM承認0/43、PHASE-1 BLOCKED、runtime NO_GO、安全停止ラッチtrue、verified_values=null。1取引0.5%、同時1.0%、日次1.5%、DD4%新規停止、DD5%全決済・本人承認、NY17:00境界を変更しない。#203〜#206の未マージ状態は変更しない。人間のmainマージ判断を経ずに統合しない。

このテストは、将来正当に承認された場合には現状の「未承認固定」を更新する必要がある。それまでは承認済みと偽装した変更を検出する停止線として使用する。
