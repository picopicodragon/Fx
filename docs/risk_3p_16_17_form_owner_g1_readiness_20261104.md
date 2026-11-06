# RISK-3P-16〜17：FORM-01〜10統合レビューとG1 3×5証拠準備ゲート

2026-11-04。追加先：未マージPR #179（RISK-3P-08〜15と同一ブランチ）。この工程は**未承認項目の棚卸しと証拠準備状況の静的照合**に限定する。証拠の収集・生成・実証・口座操作・注文は実施していない。

## 統合の意味

工程ごとのPRを作る代わりに、RISK-3P-08〜17の10工程分を**1つの監査可能な差分とGitHub CI**で確認する。これにより通常の設計・オフライン検証で手動マージの回数を削減する。`AGENTS.md`で求められるmainへの最終手動マージと、安全重要仕様の本人による個別承認は残る。**マージは安全仕様承認ではない。**

## 重要な現状

| 対象 | 対応する現在の台帳 | 今回の結論 |
| --- | --- | --- |
| 今後の3ペア | 本人の2026-11-04後続設計方針 | USD/JPY、EUR/JPY、EUR/USD。旧4ペアQ3は歴史的資料として保持 |
| FORM-01〜10 | `specs/p0_01_risk_formula_open_decisions.json` とRISK-3P-05〜15の各ドラフト | **10件ともUNDECIDED_IMPLEMENTATION_DETAIL**、実装承認なし |
| 本人判断の細分化 | F01 5件、F02 6件、FORM-03〜07 20件、FORM-08〜10 12件 | **合計43件すべて未承認**。1件のPRマージで一括承認しない |
| G1の実証 | `specs/risk_3p_06_form01_evidence_draft_20261104.json` | 新3ペア×5主要属性＝**15項目すべてPENDING_REAL_WORLD_EVIDENCE**、値・出典・時刻・独立確認なし |
| G1正式ゲート | `specs/p0_01_d5_25_gap_verification_matrix.json` | 過去の4ペア×5項目＝20項目という正式未解決ゲートを勝手に3×5へ置換しない |
| 安全原議 | `specs/source_review_priority.json` | FX-SAF-001〜015の15件すべてPENDING_ORIGINAL、本人実装承認なし |
| 受入 | `specs/acceptance_registry.json` | MODULEとPHASE-1がBLOCKED、approval null |
| 実行 | G1〜G9、runtime、停止ラッチ | G1〜G9 UNRESOLVED、PHASE-1 BLOCKED、runtime NO_GO、safety_hold_latched=true |

合成テストが3,000件以上PASSしても、FORM-01〜10の**運用に必要な未決詳細・本人原議の照合・楽天MT4の契約実測・実約定リスク・HWM/時刻の真正性**は満たされない。15件のG1新候補は実証済み0/15であり、今後の新設計候補。旧正式20件もUNRESOLVEDを維持する。

## 次の実証準備で必要な6段階

1. FORM-01〜10を個別の仕様IDで本人が判断・原議照合し、発注前の拒否条件/根拠の版を定める。現時点で原議を推測せず、安全実装承認なし。
2. G1の**正式スコープを3ペア×5属性**へ改版する場合、旧Q3/4ペア20属性の経緯を保持し、別の明示承認記録を必要とする。G1のゲート解除ではない。
3. 楽天MT4の契約観測が本当に必要になった段階で、**本人の別承認**を得て単一セッション・既存EA/建玉との安全な共存可否を独立確認。現段階で接続/ログイン/スクリプト実行/口座追加をしない。
4. 個別15属性について、同一の実口座/シンボル、数値と単位、観測時刻、出典、バージョン、別経路照合を記録する。EUR/USDの表示名、tick値、contract sizeは空欄を保持し、旧GBP/USD・AUD/USDの数値を流用しない。
5. FORM-02〜10（SL、bid/askの円換算、費用、未約定注文、部分約定、ロット境界、NY17、DD、データ鮮度）を原証拠とFX-SAF-001〜015へ紐付け、未確認項目はFail Closed。市場ギャップの有限最大損失を合成値だけで保証しない。
6. Q110のTASK/MODULE/PHASEを独立受入し、G1〜G9すべての安全条件と本人承認が別途整うまで実口座の売買・停止解除に進めない。

## 自動監査の範囲

`scripts/audit_risk_3p_16_17_owner_g1_readiness.py`は、上記の**既存台帳間の一貫性のみ**を読み取り、実証済みの値や承認が誤って記載された場合に失敗する。確認対象はFORM-01〜10、43個の未決項目、15個のG1証拠枠、15個のFX-SAF原議、9個のG1〜G9、Q110受入、3ペアV3テンプレ、Q109の合成コード登録である。

`tests/test_risk_3p_16_17_owner_g1_readiness.py`は、それらの登録に偽の本番許可、承認参照、G1値、緩和した上限、STOP解除、無審査のmain自動マージを故意に挿入し、検査で拒否されることを確認する。監査がPASSしても**証拠充足はBLOCKED**のまま。既存のローカル原議アーカイブの内容やGitHubに存在しない証拠の真正性は評価できない。

実行：`python scripts/audit_risk_3p_16_17_owner_g1_readiness.py`、`python -m unittest tests.test_risk_3p_16_17_owner_g1_readiness -v`、`python -m unittest discover -s tests -p "test*.py"`、既存Repository checksとWindows Python 3.13 CI。

## 管理方針

- 本人の要望に従い、関連する通常の設計/オフライン検証は同一PRへまとめてmainのマージ回数を減らす。
- `AGENTS.md`は変更せず、CIと差分の最終確認後のmain手動マージは1回のみとする。**実運用許可・安全仕様承認の自動処理は行わない。**
- 口座・鍵・秘密情報・原議全文や実MT4スクリーンショットをGitHubへ載せない。
- 1取引0.5%、同時合計1.0%、日次1.5%、DD4%新規停止、DD5%全決済＋本人承認を維持。

全ゲートの状態：FX-SAF-001〜015未承認、G1〜G9 UNRESOLVED、PHASE-1 BLOCKED、runtime NO_GO、safety_hold_latched=true、verified_values=null。