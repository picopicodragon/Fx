# P0-01 D5-31：G2公開メタデータ境界とG6合成コミット/復旧プロトコル

作成日：2026-10-30。前段 D5-30 はPR #145マージ済み、本人Windows 1,231件OK、GitHub CI成功。

本工程は **OFFLINE_DESIGN_ONLY / SYNTHETIC_ONLY**。ブローカー、MT4、EA/EX4、注文、OS時計、実ストレージへの書込み/復元、Gitフック/秘密情報スキャン、本人認証、通知送信を一切呼ばない。あくまで仕様と合成データを純粋関数で検査する。**G1〜G9は未解決のまま。**

## 1. G2：非機密メタデータの厳格許可形式

D5-30の未実施8件（端末、口座/サーバー、セッション、EA/AutoTrading、建玉、未約定注文、時刻/出典、ログ）を`D530-G2-01〜08`として引き継ぐ。

将来GitHubに置くことを許す**合成設計用**のレコードは、次の5つの固定フィールドだけとする。

| フィールド | 許される値 |
|---|---|
| `origin` | `SYNTHETIC_ONLY` |
| `schema_version` | 数値の`1`のみ（真偽値は不可） |
| `check_id` | `D530-G2-01〜08`のいずれか |
| `design_state` | `NOT_PERFORMED` |
| `simulation_only` | 真偽値`true`のみ |

許可フィールド以外が1つでも含まれる場合（口座番号、ログ、スクリーンショット、APIキー、実観測時刻、建玉詳細、自由記述、ネストしたメタデータなど）は**出力しない・拒否する**。伏せ字にして公開する仕組みではなく、拒否専用の入力形式検査である。

**注意：** この関数はGitリポジトリの変更や実ファイル全体をスキャンせず、既存コミット履歴に秘密情報がないことを証明しない。アプリが実際にGitHubへ書き込む直前の強制フックにも接続していない。個別承認・限定環境での将来実装が必要。G2実口座同一性は`NOT_RECONCILED`、建玉・未約定注文・EAは`UNKNOWN`、実証拠収集は`NOT_PERFORMED`のまま。

## 2. G6：コミットと復旧の純粋な状態機械

D5-30で設計した7段階を、**この順序の先頭から続くものだけ**有効な合成トレースとして認識する。逆順・重複・欠落・不明な手順名は不正入力として拒否する。

| 段階 | 合成手順 | クラッシュ時の扱い |
|---:|---|---|
| 1 | 停止ラッチを先行保持 | 不明ならSTOP保持 |
| 2 | 履歴・取消し墓標を準備 | 準備途中ならSTOP保持 |
| 3 | 将来の耐久書込み境界 | 書込み済み申告は未信頼、STOP保持 |
| 4 | チェックポイント・書込み主体を検査 | 不一致・競合ならSTOP保持 |
| 5 | 独立世代基準を更新する構想 | 更新済みでも実証ではない |
| 6 | ローカル確定チェックポイント | 外部世代との不一致を許可しない |
| 7 | 復旧後、停止ラッチ維持を再照合 | 全部揃っても自動解除しない |

合成状態には、前後の`record_id`、世代番号、連番、64桁の形式上のハッシュ、取消し墓標、停止ラッチ、完了段階を含める。別の未信頼な申告としてストレージ・独立基準・単一ライター・時計・取消し索引・既存10脅威の故障状態を受け取る。

不正または不確定な申告、部分コミット、停止ラッチ消失、レコードスコープ不一致、世代・連番の巻戻し、取消し消失、外部証明なき前進、ハッシュ不一致、停止解除要求はすべて`NO_GO`。

全7段階が合成データとして一致しても、`D531_SYNTHETIC_PROTOCOL_COHERENT_NEVER_AUTHORIZED`とする。**状態機械の合成トレースが一致しただけであり、実際のfsync、独立Trust Anchorの署名、OS上のクラッシュ整合性、本人承認や運用可能な復旧の保証ではない。**

特に外部基準の公開とローカル確定の間にクラッシュが起こるケースなど、異なる保護領域間での原子性は未解決。故障後は手動の独立検証が終わるまで停止を維持する設計とする。ハッシュや全ての未信頼入力がまとめて偽造された場合は、その改ざんをこの比較のみでは検出できない。

## 3. 実装・拒否ステータス

- `specs/p0_01_d5_31_protocol_privacy_contract.json`：厳密なG2公開形式とG6の7段階・10脅威の仕様。
- `specs/p0_01_d5_31_synthetic_fixture.json`：実口座情報を一切含まない架空の基準状態。
- `scripts/p0_01_d5_31_protocol_privacy_gate.py`：`review_d531_protocol(plan, original_evidence, gap_matrix, public_metadata, synthetic_recovery)`。
- `tests/test_p0_01_d5_31_protocol_privacy_gate.py`：実証済みフラグの偽装、機密情報欄、途中クラッシュ、順序不一致、時計・基準・取消し等を扱う新規87件の回帰テスト。
- `specs/p0_01_d5_31_status.json`：本番不許可、G1〜G9未解決の状態台帳。

判定コードは`D531_DESIGN_REJECTED_FAIL_CLOSED`、`D531_SOURCE_BASELINE_REJECTED_FAIL_CLOSED`、`D531_GAP_BASELINE_REJECTED_FAIL_CLOSED`、`D531_G2_PUBLIC_METADATA_REJECTED_FAIL_CLOSED`、`D531_G6_PROTOCOL_INPUT_REJECTED_FAIL_CLOSED`、`D531_UNAUTHORIZED_STOP_RELEASE_NO_GO`、`D531_G6_UNTRUSTED_FAULT_NO_GO`、`D531_G6_STOP_LATCH_LOST_NO_GO`、`D531_G6_RECORD_SCOPE_MISMATCH_NO_GO`、`D531_G6_ROLLBACK_NO_GO`、`D531_G6_REVOCATION_ERASURE_NO_GO`、`D531_G6_REVOCATION_CHANGE_NO_GO`、`D531_G6_UNPINNED_ADVANCE_NO_GO`、`D531_G6_HASH_MISMATCH_NO_GO`、`D531_G6_PARTIAL_COMMIT_STOP_HELD_NO_GO`、`D531_SYNTHETIC_PROTOCOL_COHERENT_NEVER_AUTHORIZED`、`D531_INPUT_EXCEPTION_FAIL_CLOSED`。

**全経路共通**：`phase_1=BLOCKED`、`runtime_go_no_go=NO_GO`、`verified_values=null`、`safety_hold_latched=true`。実証拠の本人認証、ファイル保存、Trust Anchor、時計、復旧、停止解除、MT4起動、ブローカー照会、注文、EA/EX4、本番稼働等はすべて未実施・未承認である。

## 4. 本工程で扱わないものと受入

- 旧`EV-OLD`のMT4デモAの申告と後の`EV-NEW`の休眠口座申告は同一の対象・時刻か未照合であり、現在の状態の根拠にはしない。
- 楽天へのメール問い合わせは中止。別デモBの作成・複数MT4同時ログインなし。
- 既存リスク上限（単発0.5%、同時1.0%、日次1.5%、DD4%停止・5%強制停止）・NY17日次境界・承認制限は変更しない。
- 初回CI前の予想数は既存1,231件＋新規87件＝**1,318件**。
- [ ] GitHub Repository checks / Windows Python 3.13 + tzdata CI成功
- [ ] 本人Windows全1,318件成功
- [ ] 人間が差分を目視レビューして手動マージ。マージはMT4操作・実売買・停止解除の許可ではない。

**D5-31の完了は、G2公開レコードの形式監査とG6合成プロトコルの拒否性を確認したことのみ。**
