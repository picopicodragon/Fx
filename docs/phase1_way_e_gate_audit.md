# E-GATE-01：Phase 1 残存ゲートと依存関係の監査

2026-11-02。基準は PR #161 マージ後の `main` (`44433ecda3201745d673984c283bb6f330db914c`)。本書と `specs/phase1_way_e_gate_register.json` は既存台帳の照合結果であり、新規の安全仕様・実証拠・受入承認ではない。

## 現行定義の選択

G1〜G9の名称と実証要件は `specs/p0_01_d5_25_gap_verification_matrix.json`、依存順は `specs/p0_01_d5_26_transition_priority_plan.json` を根拠とする。`specs/p0_01_d5_preexecution_review.json` は2026-10-28時点でG1〜G5を別の意味に使う**過去の実行前レビュー**であり、現行9ゲートの名称・解除基準として引用しない。D5-26の遷移順は実証済みや実行許可を意味しない。全9件 `UNRESOLVED`、`release_blocker=true`、`real_world_verified=false`。

| 順位 | ゲートと現行の対象 | 依存 | 必要な独立・実環境証拠の要旨 | 現在 |
| --- | --- | --- | --- | --- |
| 1 | G2 単一MT4口座、EA、建玉・予約注文の同一性 | なし | 旧デモA/休眠口座の同一性、時点、EA、建玉、予約注文 | BLOCKED |
| 2 | G6 原子的永続化、改ざん・巻戻し・同時書込み | なし | 独立Anchor、鍵/署名、単調基準、原子的保存、実ストレージ障害 | BLOCKED |
| 3 | G8 本人認証、操作承認・取消し・通知 | G6 | 本人確認、署名付き権限、失効/リプレイ対策、通知実証 | BLOCKED |
| 4 | G7 単調時計、UTC同期、再起動連続性、DST | G6 | Windows時計・同期誤差・再起動連続性の実証 | BLOCKED |
| 5 | G3 実MT4/EA/Pythonの緊急停止・発注遮断 | G2/G6/G8/G7 | 停止が実注文経路で強制されること | BLOCKED |
| 6 | G1 4通貨ペア×5契約属性 | G2 | 20項目の実口座値、出典、観測時刻 | BLOCKED |
| 7 | G5 損益・費用・スワップとNY17日次損失 | G1/G7 | 実約定、損益、費用、ロールオーバーの定義・出典 | BLOCKED |
| 8 | G9 ブローカー営業日・セッション・NY17境界 | G1/G7 | 楽天MT4の取引時間、祝日、休場、日跨ぎ例外 | BLOCKED |
| 9 | G4 実注文の遅延・拒否・再送・切断・不整合 | G3/G5/G9 | 別途承認された隔離条件下の実接続障害・照合・冪等性 | BLOCKED |

表の依存はD5-26の**計画上の順序**。個々の実受入を満たすには、上記の実証拠と本人承認が別に必要。現時点でG2口座同一性は `NOT_RECONCILED`、建玉・未約定注文・EAは `UNKNOWN`。

GitHubの2026-11-02時点の照合ではPR #159、#160、#161はマージ済み。公開されている未完了のPRは #63（Phase 1のオフライン基盤着手）と #5（保存先の文書変更）。これらのPR状態からG1〜G9の実証やMODULE/PHASEの本人承認は得られない。

## D537-WP-01〜15の残作業

正式な作業ID・依存・将来証拠は `specs/p0_01_d5_37_workplan_contract.json`、実受入0/15は `specs/p0_01_d5_36_readiness_register.json` と `specs/p0_01_d5_37_synthetic_tracking.json`。合成設計が存在するG2-06/07、G6-01〜06も、実装/証拠/本人承認/受入の4状態はすべて未了。

| 作業ID | 対象 | 先行条件 | 将来必要な試験・証拠 |
| --- | --- | --- | --- |
| WP-01/02 | G2-06/07 機密保管・公開境界 | G2-06、G8 | 保管権限・保持/削除、実Git/CI漏えい負試験 |
| WP-03/04 | G6-01/02 信頼境界・独立Anchor | G6-01 | 独立主体の脅威審査、単調性・所有権の証明 |
| WP-05/06 | G6-04/05 Journal・単一writer | G6-01、G6-04 | 実Journal・墓標、フェンストークン競合・復旧 |
| WP-07〜11 | G2-01〜05 口座・EA・建玉・時刻 | G2-01/02、G7 | 単一環境の同一性、現状態と時刻/出典の照合 |
| WP-12 | G6-03 鍵・発行者 | G6-01/02、G8 | 実鍵・失効・発行主体の認証 |
| WP-13 | G6-06 原子的保存 | G6-02/04/05 | 原子的コミット、途中電源断・曖昧結果・復旧拒否 |
| WP-14/15 | G6-07/08 時計・承認復旧 | G6-06/G7、G6-03/06/07/G8 | 時計連続性、承認失効・STOP保持の独立実証 |

表中の「実」は今回**未実施**。各WPの正確な `future_acceptance_evidence` と個別依存は機械照合台帳を参照。`implementation_allowed=false`、`real_evidence_collected=false`、`review_approved=false`、`acceptance_allowed=false`、`execution_allowed=false`、`separate_human_approval_required=true` を維持する。

## 試験の棚卸しと残リスク

- P1-04のSQLite障害注入計画26件、P1-05の模擬ブローカー計画27件は両台帳上で全件 `NOT_EXECUTED`。今回の新規単体/合成試験は計画IDごとの実行証跡ではない。
- D5-44の合成Journal、前PRの世代フェンス/隔離SQLite試験、本PRのゲート監査と模擬応答拒否試験は実環境のAnchor、writer、broker、秘密情報走査の代用にならない。
- `specs/acceptance_registry.json` では `M-P1-FOUNDATION-DESIGN` と `PHASE-1` が共に `BLOCKED`、approvalはnull。G1〜G9や15WPを解決したとする変更はしない。
- 安全上の後続順は、原議/本人承認、独立Anchor方式・実証計画の審査、別途承認された実証拠取得、MODULE/PHASE受入の順。実機操作、MT4/EA実行、注文、STOP解除は本PRの範囲外。
