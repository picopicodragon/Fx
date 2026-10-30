# P0-01 D5-22：本人承認の状態遷移・失効条件（合成／拒否専用）

作成日：2026-10-30。根拠：D5-21権限分離監査（PR #136）、D5-20統合NO_GO判定、D5-15単一MT4環境方針。対象は `scripts/p0_01_d5_22_approval_lifecycle.py` と `tests/test_p0_01_d5_22_approval_lifecycle.py`。

**結論：OFFLINE_SYNTHETIC_ONLY / PHASE-1 BLOCKED / runtime NO_GO。** 本仕様は将来の承認失効ルールを検討するための**仮想モデル**であり、実際の本人認証・承認発行・EA起動・停止解除・注文許可を一切実装しない。

## 1. 本人の承認を「自己申告」から作らない

- D5-21と同様、合成データの`APPROVAL_CLAIMED`は未認証の**申告**にすぎない。真の本人同意、有効な署名、監査証跡、端末の実測値ではない。
- 単にPRをマージした、CIが成功した、`claimed_human_approval=true`を入力した、証拠判定が内部整合したことでは**一切の実行権限を生まない**。
- V1目視、MT4起動、口座ログイン、V2読取り、EA/EX4、注文、停止解除、本番売買はそれぞれ独立した個別承認が必要だが、**今回どの承認も取得しない**。
- 口座番号、認証情報、実在の注文ID、未加工ログ、実承認番号はGitHubに保存しない。

## 2. 合成モデルの状態と遷移

| 入力イベント／条件 | 内部状態（合成） | 結果／制限 |
|---|---|---|
| `PROPOSED`（必須初期イベント） | `PROPOSED` | `LIFECYCLE_PROPOSED_NO_GO` |
| `APPROVAL_CLAIMED`（1回まで） | `CLAIMED_NOT_VERIFIED` | `LIFECYCLE_CLAIMED_UNTRUSTED_NO_GO`。**実承認ではない** |
| `REVOKED`（提案／申告後、1回まで） | `REVOKED` | `LIFECYCLE_REVOKED_NO_GO`。失効より優先 |
| `as_of_utc >= expires_at_utc` | `EXPIRED` | `LIFECYCLE_EXPIRED_NO_GO`。期限ちょうどで失効 |
| 操作・口座・端末・停止原因が違う | `SCOPE_MISMATCH` | `LIFECYCLE_SCOPE_MISMATCH_NO_GO` |
| 遷移順序・連番・時刻・構造が不正 | `INVALID` | `LIFECYCLE_INPUT_REJECTED_FAIL_CLOSED` |

**拒否優先順位：** 不正入力 → 取消し → 期限切れ → 対象不一致 → 未認証申告／提案。

複数のイベントは `sequence=0,1,2` の連番、同じ合成レコードID、前後で逆転しない観測日時、未来イベントなしを必須とする。初期イベントの時刻は発行日時と一致。取消し後の再申告、二重取消し、二重申告、期限後に行われた申告は不正として拒否する。

## 3. 対象範囲と時刻境界

- 必須レコード要素：`record_id`、`action`、`account_scope`、`terminal_scope`、`stop_cause`、`issued_at_utc`、`expires_at_utc`。
- 要求要素：`action`、`account_scope`、`terminal_scope`、`stop_cause`。レコードと要求が**全て完全一致**しなければ認めない。異なる操作への流用は禁止。
- 操作：`VISUAL_REVIEW`、`MT4_LAUNCH`、`ACCOUNT_LOGIN`、`READ_ONLY_QUERY`、`EA_EXECUTION`、`ORDER_ACTION`、`STOP_RELEASE`、`LIVE_TRADING`。
- `STOP_RELEASE`は停止原因（`DD4`、`DD5`、`DAILY_LIMIT`、`COMMUNICATION`、`CLOCK_FAULT`、`MANUAL_HALT`）を必須として区別する。**原因の合成一致は停止解除の許可ではない**。
- その他の操作の停止原因は`NONE`とし、未知の原因は拒否。
- `record_id=SYNTH_APPROVAL_...`、口座ラベル`SYNTHETIC_ACCOUNT_...`、端末ラベル`SYNTHETIC_TERMINAL_...`の固定接頭辞を要求する。実口座識別子は受け付けない。
- 日時は厳格なUTC秒精度 `YYYY-MM-DDTHH:MM:SSZ` のみ。経過時間は**入力日時同士**で判定し、OS時計を読み取らない。
- 合成レコードの存続長は**0秒超～3600秒以下**とする。これはオフライン回帰試験用の保守的な仮定であり、**本番の承認有効時間を正式決定したものではない**。今後の実機用ポリシーは別の設計・人間判断が必要。

## 4. D5-21との結合

`audit_synthetic_approval_lifecycle(payload)`は状態だけを合成判定する。`audit_synthetic_lifecycle_with_authority(integrated_fixture,payload)`はD5-21の`audit_offline_authority_separation`を呼び、D5-19/20の証拠・停止状態を再計算した**拒否専用**の戻り値を監査する。

- 元の承認申告が合成上で`CLAIMED_NOT_VERIFIED`でも、D5-21へ渡せるのは未認証`claimed_human_approval`の申告であり、実権限ではない。
- 証拠矛盾、現在の停止記録不足、DD5%、時刻不整合などがあれば、D5-21側の停止／証拠ブロックが優先。
- 下位ゲートが`GO`、ホールド解除、認可フラグtrue、未知の判定コード等を返す場合、`LIFECYCLE_AND_AUTHORITY_REJECTED_FAIL_CLOSED`とする。
- 戻り値に承認番号や原文をエコーせず、ステータスのみ返す。

全結果で `approval_verified=false`、`action_authorized=false`、`ea_execution_authorized=false`、`order_authorized=false`、`stop_release_authorized=false`、`effective_approved_actions=[]`、`safety_hold_latched=true`、`verified_values=null`、`broker_verified=false`、`production_usable=false`、`read_only_ex4_execution_approved=false`、`terminal_execution_approved=false`、`orders_generated=false`、`forward_trading_enabled=false`、`phase_1=BLOCKED`、`runtime_go_no_go=NO_GO`。

## 5. 未解決の真正性・再利用リスク

本工程の連番は**提示されたイベント配列内**の整合検査のみ。外部に信頼された最新連番・永続保存・署名・取消し台帳が存在しないため、改ざん済み履歴や旧状態を再送されても**真の失効・リプレイ防止は保証できない**。合成時刻の一致や、未来時点・期限切れの判定は入力日時の整合性だけを保証するもので、実時計との同期・鮮度を保証しない。

今後G8の真の承認システムを設計する際は、本人認証、行為/口座/環境/停止原因への暗号学的束縛、独立な時刻検証、短期失効、取消しの永続性、nonce・再利用検出、監査、権限を使う側の強制ゲートを別途要件化する。**現段階ではこれらは未実装**であり、実環境への移行可否は変わらない。

## 6. オフライン受入条件

- [ ] 新規52件＋既存703件の**計755件**のWindowsローカルテスト成功
- [ ] GitHub Repository checks、Windows Python 3.13 / IANA time zones CI成功
- [ ] 取消し・期限境界・対象不一致・二重イベント・時刻逆転を拒否
- [ ] 合成申告や再提出で実承認が発生しない
- [ ] D5-21との結合で停止・証拠ブロック、偽GO応答を拒否
- [ ] D5-21以前のコード／G1〜G9の安全条件を変更しない
- [ ] 本人が差分を確認して手動マージ（実機操作の承認とは別）

**D5-22完了の意味：合成データ上の承認状態遷移・失効条件をテストしたことのみ。MT4・楽天口座・実認証・実注文の検証ではない。**
