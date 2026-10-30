# P0-01 D5-24：合成基準点（Trust Anchor候補）と保存・復元失敗時のNO_GO判定

作成日：2026-10-30。基礎：D5-23、D5-22、D5-21の拒否専用ゲート。新規実装：`scripts/p0_01_d5_24_reference_fault_gate.py`、`tests/test_p0_01_d5_24_reference_fault_gate.py`。

**本工程は設計と純粋な合成テストのみ。実際の信頼済みTrust Anchor、署名、本人認証、ファイル書込み、外部参照・OS時計・MT4・楽天口座・注文操作は一切存在しない。 `PHASE-1 BLOCKED / runtime NO_GO` を変更しない。**

## 目的と信頼境界

D5-23では、履歴＋チェックポイントを同時に改ざんすると、双方の内部整合だけでは異常を検出できない。D5-24では3番目の参照値として`reference`を比較する設計を用意する。しかしこの参照値も**呼出元が提供する未信頼の仮想データ**であり、書込み隔離や外部独立性が保証されたTrust Anchorではない。

`build_synthetic_reference_fixture(history_bundle,generation=1)`で合成参照値を生成できることは、**誰でも偽造可能**であることの実演でもある。参照値を生成しても認証・発注権限は付与されない。

## 判定入力

`audit_synthetic_reference_and_failures(payload)` の必須6フィールド：
- `origin="SYNTHETIC_ONLY"`、`schema_version=1`
- `history_bundle`：D5-23の合成ライフサイクル、ハッシュ列、チェックポイント、停止・証拠判定
- `reference`：`reference_id`（`SYNTHETIC_REFERENCE_...`）、`record_id`（`SYNTH_APPROVAL_...`）、`sequence`、`head_hash`、`revocation_tombstone`（bool）、`generation`（1〜1000000）
- `minimum_generation`（1〜1000000）：比較に使う**呼出元供給の下限値**。単調増加を実機で証明する外部台帳ではない。
- `simulated_storage`：`write_state`、`restore_state`、`reference_read_state`、`clock_state`、`concurrent_writer_detected`。先頭3フィールドは`SYNTHETIC_CONFIRMED/FAILED/UNKNOWN`、時計は`SYNTHETIC_CLOCK_STABLE/CLOCK_ANOMALY/UNKNOWN`、競合はbool。

**重要：** 「SYNTHETIC_CONFIRMED」はシミュレーションに含まれる申告であり、本当にディスクへ書込めたことや、Windows時計が正常であることの確認ではない。

## 判定優先順位

| 優先順位 | 条件 | status |
|---|---|---|
| 1 | 型・必須フィールド・参照ID・ハッシュ・下限世代・合成状態が不正 | `ANCHOR_INPUT_REJECTED_FAIL_CLOSED` |
| 2 | 書込み／復元／基準点読出しの合成結果が失敗または不明 | `ANCHOR_STORAGE_UNCERTAIN_NO_GO` |
| 3 | 時計異常／時計不明／二重書込み検出 | `ANCHOR_CONTINUITY_UNTRUSTED_NO_GO` |
| 4 | 参照の世代が合成下限世代より小さい | `ANCHOR_REFERENCE_GENERATION_ROLLBACK_NO_GO` |
| 5 | D5-23履歴・D5-22承認・D5-21権限拒否の不一致・破損 | `ANCHOR_HISTORY_BLOCKED_NO_GO` |
| 6 | 基準点と履歴のレコードIDが違う | `ANCHOR_RECORD_MISMATCH_NO_GO` |
| 7 | 参照連番が提出された履歴より新しい | `ANCHOR_HISTORY_ROLLBACK_NO_GO` |
| 8 | 参照連番が提出された履歴より古い | `ANCHOR_REFERENCE_STALE_NO_GO` |
| 9 | 取消し墓標と履歴内の取消しイベントの有無が不一致 | `ANCHOR_REVOCATION_MISMATCH_NO_GO` |
| 10 | 参照ハッシュとD5-23チェックポイントのハッシュが違う | `ANCHOR_HEAD_MISMATCH_NO_GO` |
| 11 | 仮想履歴、チェックポイント、参照値の内部整合 | `ANCHOR_SYNTHETIC_REFERENCE_MATCH_NO_GO` |

**11はGOではない。** `revocation_tombstone=true`は、過去の取消しが外部に耐久保存されていることの証拠ではない。事後的に同じデータを書き換えても、3者が整合してしまう限界は残る。

すべての返却で`reference_authentic=false`、`revocation_persisted=false`、`trusted_clock_verified=false`、`actual_replay_protection=false`、`approval_verified=false`、`action_authorized=false`、`ea_execution_authorized=false`、`order_authorized=false`、`stop_release_authorized=false`、`effective_approved_actions=[]`、`safety_hold_latched=true`、`runtime_go_no_go=NO_GO`、`verified_values=null`、`broker_verified=false`、`production_usable=false`、`read_only_ex4_execution_approved=false`、`terminal_execution_approved=false`、`orders_generated=false`、`forward_trading_enabled=false`、`phase_1=BLOCKED`を保証する設計。

## 合成テスト51件（期待合計856件）

- 有効形式の合成提案・申告・取消し・期限切れ・DD5停止解除申告・日次停止・証拠矛盾でも全てNO_GO。
- 提示履歴＋チェックポイントの同時改変、取消し削除、同じ長さの別口座・別端末・別操作への変更、古い/新しい参照、世代巻き戻し、墓標不一致を検出。
- 保存失敗・復元失敗・参照値読出し失敗・不明、時計異常・不明、二重書込み検出、複数障害の拒否優先を検証。
- 破損したD5-23履歴や、下位ゲートの偽GO/偽broker_verifiedを拒否。
- **3者のすべてを一貫して再作成された場合は検出できない**ことを明示。古いデータと古い下限世代値を同時に供給された場合も真の鮮度は判断できない。
- 不正なスキーマ・真偽値型・余分な実行許可フィールドの拒否、入力不変性を検証。

## Trust Anchor実装の未解決要件（G6/G7/G8）

1. **独立した信頼の根**：本人が管理する保存先や署名/検証方法の威嚇モデル、鍵保全、ロールバックに対する外部の単調基準、取消し墓標、書込み確定の厳格な定義。
2. **安全な実装**：原子的保存、クラッシュ整合性、プロセス二重起動排除、長期保持・監査、バックアップと復元の整合性。故障注入を通したOSレベルの検証。
3. **安全な時計**：Windows単調時計、UTC、DST、再起動による連続性喪失時の自動解除禁止。
4. **実際の承認権限**：本人確認の独立性、操作/口座/端末/期限/停止原因への厳密な権限制限、失効/取り消しの永続的反映、実注文経路での強制検証。
5. **段階的な本人承認**：実環境へアクセスするかどうかは後日別途明示承認が必要。本PRマージはその承認を意味しない。

G1〜G9はすべて未解決であり、単一MT4環境方針を維持。楽天への問い合わせ、別デモB、MT4起動・口座照会・EA/EX4実行・注文・決済は行わない。

## 本PR受入チェック

- [ ] 新規51件＋従来805件の**計856件**を本人Windowsで検証
- [ ] Repository checksとWindows Python 3.13 / IANA time zones CI成功
- [ ] 参照値・失敗状態が実測や本人認証だと誤読されない
- [ ] D5-23以前のコードを変更せず、安全条件を維持
- [ ] 差分を本人が確認し、本人操作で手動マージ

**D5-24完了の意味は合成基準点の設計・検証のみ。実Trust Anchorの完成、真正性、リアルな停止・注文禁止、運用許可ではない。**
