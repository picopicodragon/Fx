# RISK-3P-38〜42：P05のオフライン安全ゲート強化

作成日：2026-11-06 JST。PR #180のmainマージを確認後、新規ブランチで実施。

**対象は合成データと仕様台帳のオフライン検証のみ。** 楽天MT4、既存MACD Sample、証券会社、ログインID、建玉・未約定注文、ローカルの非公開証拠フォルダには接続・アクセス・変更しない。

## 実装工程

| 工程 | 実装・確認対象 | 重要な禁止 |
|---|---|---|
| RISK-3P-38 | P05-01・04：架空の口座エイリアス・DEMO種別・単一セッションの整合性 | 画面の「通信中」を実口座同一性と見なさない。2端末ログインも禁止 |
| RISK-3P-39 | P05-02・05：MACD Sample表示、AutoTrading OFFらしき表示、不機嫌な顔の解釈境界 | EA停止・実行状態・注文不存在の確証にしない。実MT4へ一切操作しない |
| RISK-3P-40 | P05-01〜05：上記2検証器と既存P05-03注文照合の3系統合成連動 | 一致・成功でもP05の合格、MT4読取・売買許可に昇格しない |
| RISK-3P-41 | P05-01〜08全件：本人報告／人間未署名レビュー／G1未検証台帳との8件整合性 | P05-06のローカル保管先受入を全P05受入・ACL独立検査・データ収集許可に変換しない |
| RISK-3P-42 | 異常注入：口座違い・別セッション・LIVE誤認・EA誤操作・サーバー注文・時刻差・欠落・権限偽造等16ケース | 全てFAIL_CLOSED、センシティブ情報を出力しない |

ファイルは `scripts/risk_3p_38_synthetic_session_identity.py`、`scripts/risk_3p_39_synthetic_ea_no_interference.py`、`scripts/risk_3p_40_synthetic_p05_interlock_matrix.py`、`scripts/audit_risk_3p_41_p05_offline_gate_matrix.py`、`scripts/risk_3p_42_synthetic_fault_campaign.py` と、対応テスト・`specs/risk_3p_41_p05_offline_gate_matrix_20261106.json`。新しい5つのコードは `specs/traceability.json` へテスト・仕様IDと一緒に登録し、`production_authorized=false` を明示する。

## 判定の読み方

`PASS_SIMULATED_IDENTIFIERS_ONLY`、`PASS_OFFLINE_NON_INTERFERENCE_PLAN_ONLY`、`PASS_SYNTHETIC_MATRIX_ONLY`、`PASS_OFFLINE_MATRIX_ONLY`、`PASS_SYNTHETIC_FAULT_CAMPAIGN_ONLY` は、**架空入力の構造が期待どおりに評価される**ことを示すだけである。実機の現在状態、EA実行状態、サーバー注文、保管権限、口座同一性の実証ではない。

以下は実データを用いた将来の独立確認と人間の別途審査を要する：対象デモ口座の現在の同一性、EA/AutoTrading/稼働状態、建玉・未約定注文のサーバー照合、単一接続、読み取り無干渉、G1の契約15属性の証拠、P05-08本人署名。

**P05 0/8 BLOCKED、G1 0/15、FX-SAF原議0/15、FORM承認0/43、PHASE-1 BLOCKED、runtime NO_GO、safety_hold_latched=true、verified_values=null** を維持する。1取引0.5%、同時保有1.0%、日次損失1.5%、DD4%停止、DD5%全決済・本人承認という安全条件も変更しない。

本工程では新たな人間の確認やmainへのマージは行わない。PRは自動テストまで進め、mainへの最終統合は別途人間の判断に残す。
