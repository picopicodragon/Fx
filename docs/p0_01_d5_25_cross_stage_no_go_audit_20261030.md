# P0-01 D5-25：D5-17〜24オフライン総合監査とG1〜G9移行ブロッカー

作成日：2026-10-30。前段D5-24：PR #139、本人Windows 856件OK、GitHub CI成功、マージ済み。

**本工程は合成入力での診断・オフライン監査だけを実装する。本人認証、端末/口座確認、EA/EX4、MT4起動、楽天証券照会、注文、停止解除、実Trading GOを一切実行・認可しない。**

## 1. 目的

D5-17〜D5-24の機能を別々に正常・異常判定できても、複数のゲートが相互に矛盾している可能性がある。D5-25ではそれぞれを**独立に再計算**し、①拒否専用契約、②判定コードの一致、③合成口座スコープの一致を検査する。通過条件は**合成データの内部整合**を意味するのみで、実口座の同一性・真正性や発注可能性を保証しない。

対象：`scripts/p0_01_d5_25_cross_stage_audit.py`。
新規テスト：`tests/test_p0_01_d5_25_cross_stage_audit.py`（50件）。

## 2. 横断ゲートと扱い

`audit_synthetic_cross_stage_no_go(payload)`は`origin=SYNTHETIC_ONLY`、`schema_version=1`、`anchor_fixture`の3フィールドのみ許容。`anchor_fixture`はD5-24と同形式で、D5-23の履歴とD5-19の統合フィクスチャを内包する。

| 評価工程 | オフラインで行うこと | 実世界で保証できないこと |
|---|---|---|
| D5-17/18 → D5-19/20 | 未照合の履歴と合成証拠、合成停止ラッチ・時刻整合 | デモAと休眠口座の同一性、建玉・未約定注文・EAの現在状態 |
| D5-21 | 本人承認の自己申告を拒否専用のゲートで再計算 | 認証された本人承認・実注文への強制力 |
| D5-22 | 未認証の承認申告の取消し・期限切れを再計算 | 信頼できる時刻、本人ID、取消し済みデータの永続性 |
| D5-23 | 提示された履歴・チェックポイントを再比較 | 独立した真正な署名・リプレイ防止 |
| D5-24 | 仮想基準点、保存/復元/時計異常の模擬判定 | 実Trust Anchor、原子的な保存・リアルな障害の検出 |

**クロスチェック：** D5-21が返した統合判定、D5-23が返したD5-22状態、D5-24が返したD5-23状態が、各段階を別計算した結果と違う場合は`CROSS_STAGE_STATUS_DISAGREEMENT_NO_GO`。下位ゲートが未知の状態、`GO`、ブローカー確認済み、停止解除済みなどと主張した場合は`CROSS_STAGE_CHILD_CONTRACT_REJECTED_FAIL_CLOSED`。

**合成口座スコープの追加検査：** D5-22承認レコード内`account_scope`とD5-18合成証拠内`account_scope`が一致しなければ`CROSS_STAGE_SCOPE_MISMATCH_NO_GO`。証拠が未照合のD5-17 ledgerやスコープ欠落なら`CROSS_STAGE_SCOPE_UNVERIFIED_NO_GO`。**一致しても実口座の同一性を証明しない**。D5-19の停止スナップショットには実口座IDの紐付けがないため、D5-25でも別の実データと誤って結び付けない。

## 3. 結果コード

| 条件 | status |
|---|---|
| 入力構造不正・例外 | `CROSS_STAGE_INPUT_REJECTED_FAIL_CLOSED` |
| 子ゲートの拒否専用契約に違反 | `CROSS_STAGE_CHILD_CONTRACT_REJECTED_FAIL_CLOSED` |
| 子ゲートの報告が相互に異なる | `CROSS_STAGE_STATUS_DISAGREEMENT_NO_GO` |
| 証拠のスコープが確認できない | `CROSS_STAGE_SCOPE_UNVERIFIED_NO_GO` |
| 合成口座ラベルが異なる | `CROSS_STAGE_SCOPE_MISMATCH_NO_GO` |
| 子ゲートの障害・拒否・不整合 | `CROSS_STAGE_BLOCKED_NO_GO` |
| すべて合成入力の範囲内で整合 | `CROSS_STAGE_SYNTHETIC_COHERENT_NEVER_AUTHORIZED` |

**全結果で** `account_scope_verified=false`、`history_authentic=false`、`trust_anchor_verified=false`、`actual_replay_protection=false`、`approval_verified=false`、`action_authorized=false`、`ea_execution_authorized=false`、`order_authorized=false`、`stop_release_authorized=false`、`effective_approved_actions=[]`、`safety_hold_latched=true`、`phase_1=BLOCKED`、`runtime_go_no_go=NO_GO`、`verified_values=null`、`broker_verified=false`、`production_usable=false`、`orders_generated=false`、`read_only_ex4_execution_approved=false`、`terminal_execution_approved=false`、`forward_trading_enabled=false`。

## 4. G1〜G9を二分した監査台帳

`specs/p0_01_d5_25_gap_verification_matrix.json`に9件すべての`offline_synthetic_coverage`（オフラインテスト対象）と`external_or_real_evidence_required`（別途検証が必要な条件）を明示。全て`implementation_status=UNRESOLVED`、`release_blocker=true`、`real_world_verified=false`。既存の「独立デモB」案は廃案。単一MT4環境のみを将来の対象とする。

| ID | オフラインで対象としたもの | 解決に必要な外部条件 |
|---|---|---|
| G1 CRITICAL | リスク式・境界値の合成検査 | 4通貨ペア×5契約項目を出典付きで確認 |
| G2 CRITICAL | 証拠不足・口座ラベル矛盾の判定 | デモA／休眠口座の同一性、建玉・予約注文・EAを未干渉の個別承認の下で照合 |
| G3 CRITICAL | STOP・復元・注文拒否状態の合成判定 | 実MT4/EA/Python注文経路の停止強制力 |
| G4 CRITICAL | 障害時の拒否原則 | 実回線の遅延・拒否・再送・切断・照合 |
| G5 HIGH | 合成損益・NY17区切り | 実約定・費用・スワップ・損益確定方法 |
| G6 HIGH | ハッシュ履歴・未信頼基準点・保存失敗申告 | 独立Trust Anchor・原子的保存・停止履歴の真正性 |
| G7 HIGH | DST・UTC、合成期限・時計異常 | Windows単調時計、再起動・同期異常時の連続性 |
| G8 HIGH | 未認証申告の拒否、期限・取消しの合成遷移 | 本人認証、厳密な権限失効・実際のLINE＋メール通知 |
| G9 HIGH | NY17区切りとDSTの合成テスト | 楽天MT4の市場時間・休日・例外日の検証 |

**テスト件数の増加をG1〜G9の実運用リスク低下・実行承認と同一視しない。**

## 5. 合成回帰と受入基準

- 新規50件、D5-24までの856件と合わせて**想定906件**。
- 停止中の申告、履歴・スナップショットの破損、時刻不一致、口座ラベル違い、取消し・期限切れ、世代巻き戻し、模擬保存・時計障害、下位偽GO、未知のステータス、結果型の偽装、入力非改変を横断検査。
- `specs/p0_01_d5_25_audit_status.json`に現在の未検証情報・失効していない安全ホールドと想定テスト数を記載。
- 追加コードは**発注・MT4・ファイルI/O・外部時計呼出しを行わない**。D5-24以前の実装には変更を加えない。
- [ ] GitHub Repository checksとWindows Python 3.13 / IANA time zones CI成功。
- [ ] 本人Windows環境で全906件成功。
- [ ] 本人が差分を目視してPRを手動マージ。マージは実環境操作への承認ではない。

## 6. 次に進む場合の原則

オフラインで可能な静的・合成安全テストと、Windows実環境／MT4実口座／実本人確認／外部保存を要する検証を分離し続ける。後者は**工程ごとに個別の明示承認が必要**。本D5-25はその承認を要求・取得・推定しない。適用口座も依然`NOT_RECONCILED`である。

**D5-25の完了はNO_GO総合監査の完成のみ。実機適合性、本番売買許可、安全保証の認定ではない。**
