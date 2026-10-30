# P0-01 D5-28：G2証拠記録形式とG6受入基準の詳細化

作成日：2026-10-30。直前D5-27（PR #142）はマージ済み、本人Windowsで1,018件OK。本工程は **OFFLINE_DESIGN_ONLY / SYNTHETIC_ONLY**。既存G1〜G9全件未解決、単一MT4環境方針、楽天問い合わせ中止、独立デモB不採用を維持。実MT4、口座、注文、EA/EX4、Windows時計、ファイル保存を操作・実測しない。

## 1. G2：出典と時刻を分けた証拠記録形式

`specs/p0_01_d5_28_acceptance_contract.json` は次の10項目を要求する。いずれも**合成フィクスチャ**であり、ユーザーの実際の口座情報を記録したものではない。

| 項目 | 記録・検査の意味 |
|---|---|
| `report_id` | `EV-OLD` または `EV-NEW`。D5-17の過去申告との概念上の照合 |
| `provenance_class` | `UNVERIFIED_SYNTHETIC_REPORT`のみ受入。ブローカー検証済みと偽装しない |
| `account_token` | `SYNTHETIC_...`形式の架空ラベルのみ。実口座番号をGitHubに記録しない |
| `terminal_token` | `SYNTHETIC_...`形式の架空ラベルのみ。実端末を識別していない |
| `observed_at_utc` | 合成上の観測日時。厳格なUTC秒形式と実在する暦日を検査 |
| `recorded_at_utc` | 合成上の記録日時。観測日時より前なら拒否 |
| `positions` | 合成建玉状態。未約定注文とは別に記録 |
| `pending_orders` | 合成未約定注文状態。建玉とは別に記録 |
| `ea_attachment` | 合成EA装着状態 |
| `autotrading` | 合成AutoTrading状態。EA装着とは別に記録 |

状態は`ABSENT/PRESENT/UNKNOWN`の3値のみ。D5-17の実過去申告に観測UTC時刻がないため、**過去2件をこの新形式の時刻に書き換えたり、合成時刻を実観測時刻だと解釈しない**。将来の実証用記録には、機密情報を公開リポジトリに残さないこと、出典の真正性・観測対象の同一性・記録経路・確認行為の個別承認が別途必要。

**G2の将来の受入基準案**：対象が同一の単一MT4口座か、観測対象と期間に矛盾がないか、建玉と未約定注文を分けた状態、EA装着とAutoTrading表示、証拠の出典と観測・記録時刻が揃っているかを本人が確認。いずれか欠落・矛盾なら`NOT_RECONCILED`のまま停止。これらが全て揃っても、独立の実口座検証や安全確認なしに取引を有効化しない。

合成関数は構造・順序・時刻・架空口座/端末ラベルの不一致を分類する。日付/ラベルが一致した場合の`D528_SYNTHETIC_ACCEPTANCE_FORMAT_COHERENT_NO_GO`は**実口座の本人認証や現在状態確認ではない**。両者を一貫して偽造すれば単純な入力比較では検知できない。

## 2. G6：10個の停止履歴受入基準

D5-27の`P27-G6-01〜10`を受け、`G6-AC-01〜10`を登録した。対象は将来の実ストレージ・独立Trust Anchorの受入試験候補であり、**すべて未実施**。

| ID | シナリオ | 将来の合否基準の要旨 |
|---|---|---|
| G6-AC-01 | 原子的コミット破損 | 不完全な状態に復元されず、安全停止継続 |
| G6-AC-02 | 書込み途中の電源断 | ジャーナル・停止ラッチが未確定なら復帰不可 |
| G6-AC-03 | 参照値の巻戻し | 独立した単調な基準点との比較で拒否 |
| G6-AC-04 | 全参照の同時改ざん | **未信頼の履歴＋基準値だけでは検出不能**。独立した信頼の根が必要 |
| G6-AC-05 | 取消し記録の欠落 | 耐久した取消し墓標との照合で拒否 |
| G6-AC-06 | 同時書込み | 単一書込み主体の排他とクラッシュ後の不一致拒否 |
| G6-AC-07 | 再起動・時計異常 | 単調時計の継続性喪失時は自動解除禁止 |
| G6-AC-08 | 署名鍵改ざん | 鍵保護・失効・独立した検証主体の必要性 |
| G6-AC-09 | ストレージ停止 | 容量不足・アクセス不可・媒体故障でも拒否 |
| G6-AC-10 | 旧バックアップ復元 | 独立した世代/停止履歴による巻戻し検出 |

**注意**：G6-AC-04の`expected_status=SAFETY_HOLD_LATCHED_NO_GO`は、合成ケースで「改ざん」を明示されたとき停止を継続する設計であることのみを意味する。**改ざんを実際に検出した証拠ではない**。そのイベントを隠して履歴・チェックポイント・参照値をすべて偽造された場合、現行構成では検知を保証できない。

将来の実OS障害注入・保存試験は、専用のMT4非連携環境、独立した保存先・署名/鍵・原子的なコミット、復元と旧世代拒否の検証方法を明文化し、**操作別の明示承認**後に実施すること。今回のファイルは受入基準の定義であり、ホストI/O機能の実装ではない。

## 3. D5-28純粋関数・拒否優先順位

`audit_d528_acceptance_design(design,case)` は合成仕様と合成ケースのみを検査する。評価対象の両方が外部由来の**未信頼入力**であり、第三者認証や永続的な証明ではない。

| 条件 | 判定 |
|---|---|
| 受入基準JSONの不足、実認証/実操作許可への変更 | `D528_DESIGN_REJECTED_FAIL_CLOSED` |
| 合成証拠・時刻・G6ケースの形式不備 | `D528_CASE_REJECTED_FAIL_CLOSED` |
| 偽の停止解除申告 | `D528_RELEASE_CLAIM_DENIED_NO_GO` |
| G6の障害入力、保存・基準点・取消し・時計の異常 | `D528_G6_UNTRUSTED_OR_FAULT_NO_GO` |
| G2の合成口座・端末ラベルの不一致 | `D528_G2_SYNTHETIC_SCOPE_MISMATCH_NO_GO` |
| G2の合成観測日時の不一致 | `D528_G2_SYNTHETIC_TIME_MISMATCH_NO_GO` |
| G2の建玉・注文・EA・AutoTrading状態の差 | `D528_G2_SYNTHETIC_REPORT_CONFLICT_NO_GO` |
| G2の合成状態が不明 | `D528_G2_SYNTHETIC_UNKNOWN_NO_GO` |
| 形式上の合成データが一致 | `D528_SYNTHETIC_ACCEPTANCE_FORMAT_COHERENT_NO_GO` |
| 不測の例外 | `D528_INPUT_EXCEPTION_FAIL_CLOSED` |

**すべての返値**で`g2_real_world_resolved=false`、`g6_real_world_resolved=false`、`evidence_provenance_authenticated=false`、`account_identity_verified=false`、`positions_verified=false`、`pending_orders_verified=false`、`ea_state_verified=false`、`trusted_clock_verified=false`、`trusted_anchor_verified=false`、`atomic_persistence_verified=false`、`revocation_durable_verified=false`、`real_transition_authorized=false`、`visual_review_approved=false`、`mt4_launch_approved=false`、`mt4_read_only_approved=false`、`host_io_approved=false`、`approval_verified=false`、`action_authorized=false`、`ea_execution_authorized=false`、`order_authorized=false`、`stop_release_authorized=false`、`effective_approved_actions=[]`、`safety_hold_latched=true`、`phase_1=BLOCKED`、`runtime_go_no_go=NO_GO`、`verified_values=null`、`broker_verified=false`、`production_usable=false`、`read_only_ex4_execution_approved=false`、`terminal_execution_approved=false`、`orders_generated=false`、`forward_trading_enabled=false`。

## 4. 受入と残条件

- D5-27まで1,018件。新規65件、合計**想定1,083件**。
- 既存D5-17・D5-25・D5-27の未確認記録を変更せず、現行口座・端末・建玉・EA状態`UNKNOWN`、G1〜G9`UNRESOLVED`を維持。
- 楽天MT4を起動/照会しない。EA、EX4、注文、決済、実WindowsファイルI/O、通知送信なし。
- [ ] GitHub Repository checks / Windows Python 3.13 CI成功。
- [ ] 本人Windowsの全1,083件実行でOK。
- [ ] 本人が差分を目視し、PRを手動マージ。マージは口座アクセス・停止解除・本番運用の承認ではない。

**D5-28の完了範囲：証拠形式と将来の障害試験受入基準のオフライン設計・合成検証のみ。**
