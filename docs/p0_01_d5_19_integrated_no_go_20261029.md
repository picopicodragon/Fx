# P0-01 D5-19：証拠判定 × 日次停止 × 復元履歴のオフライン結合ゲート

作成日：2026-10-29。対象：`scripts/p0_01_d5_19_integrated_no_go.py`、`tests/test_p0_01_d5_19_integrated_no_go.py`。依存はD5-18（口座証拠判定）、D5-7（日次停止）、D5-10（D5-8/9の合成履歴復元）。

**評価はインメモリ・合成入力に限定。MT4・楽天証券・外部時計・実注文・実測値にはアクセスしない。全分岐でPHASE-1 BLOCKED、runtime NO_GO。**

## 目的

1. 口座同一性と証拠整合性の未確認・矛盾を、停止状態と別軸で保持する。
2. 日次停止ラッチと復元済み停止ラッチのいずれかに停止があるとき、**整合した合成証拠があっても新規取引禁止状態**を維持する。
3. 2種類の停止フラグが食い違えば、正常復帰を推測せず`INTEGRATED_STOP_DISAGREEMENT_FAIL_CLOSED`と判定する。
4. D5-7単体に残る`previous_day_label`の文字列比較の弱さを、結合入力の**暦日実在性・正規ISO形式の検査**で補う。D5-7単体コードはこのPRで変更しない。
5. D5-18の合成記録が整合し、日次リスク・復元履歴が正常でも、取引許可に昇格させない。

## 入力契約

`evaluate_offline_integrated_no_go(payload)` は以下の全フィールドを持つdict以外を拒否：

- `origin="SYNTHETIC_ONLY"`、`schema_version=1`（boolは不可）
- `evidence_mode="D517_LEDGER"` または `"SYNTHETIC_RECORDS"`
- `evidence`：D5-17未確認証拠台帳、またはD5-18の仮想証拠バンドル（ログインID・注文/口座番号は使わない）
- `daily_fixture`：D5-7合成日次リスク入力
- `snapshots` / `restored_snapshot`：D5-10インメモリ合成停止履歴/復元値
- `expected_day`：存在する日付`YYYY-MM-DD`、`minimum_sequence`：合成履歴下限

`daily_fixture.previous_day_label`も実在する`YYYY-MM-DD`とし、`expected_day`より未来なら拒否。日次計算から返る`trading_day_start_ny_date`と`expected_day`の一致が必要。

**結合上の限界：** D5-8/9の停止スナップショットには口座識別子がない。そのため、合成証拠と停止履歴が「同一の実口座」に属する真正な証明にはならない。実口座との紐付けや永続性は本工程の対象外。

## 判定結果と優先順位

| 条件 | ステータス | 注文許可 |
|---|---|---|
| 入力構造・日付不正、日次日付不一致 | `INTEGRATED_INPUT_REJECTED_FAIL_CLOSED` | なし |
| 子判定のスキーマ拒否、日次レビュー異常、復元履歴異常 | `INTEGRATED_COMPONENT_REJECTED_FAIL_CLOSED` | なし |
| 日次ラッチと復元ラッチの食い違い | `INTEGRATED_STOP_DISAGREEMENT_FAIL_CLOSED` | なし |
| 日次/復元に停止がある、または追加のリスクレビューが必要 | `INTEGRATED_STOP_OR_REVIEW_BLOCKED_NO_GO` | なし |
| 証拠の不一致・不足・D5-17未照合台帳 | `INTEGRATED_EVIDENCE_BLOCKED_NO_GO` | なし |
| 合成証拠・合成日次・合成履歴がすべて内部整合 | `INTEGRATED_SYNTHETIC_COHERENT_NEVER_AUTHORIZED` | なし |

全出力で`safety_hold_latched=true`（**合成検証では政策上の安全ホールドを解除しない**）。`daily_stop_latched`は日次/復元ゲートが検出した合成停止状態を示すが、実注文経路を停止した証明ではない。矛盾・無効時は`daily_stop_latched=true`を安全側の既定値とする。

さらに全出力で`verified_values=null`、`broker_verified=false`、`production_usable=false`、`orders_generated=false`、`read_only_ex4_execution_approved=false`、`terminal_execution_approved=false`、`forward_trading_enabled=false`、`phase_1=BLOCKED`、`runtime_go_no_go=NO_GO`。

## 合成テスト（新規32件）

- 内部整合した仮想証拠でも安全ホールド維持
- D5-17の旧/新報告が未照合のまま残る
- 日次停止、日次損失1.5%、DD5%、NY17翌日レビューで停止保持
- 日次/復元の停止フラグ不一致を拒否
- 建玉・予約注文・EAの矛盾、口座スコープ不一致、時点違い、証拠不足
- JSON台帳での疑似ブローカー確認、損失評価の無効値、履歴破損・連番欠落、ロールバック防止
- 不正な暦日、未来日、日次日付不一致、無効なUTC、スキーマ・型の不整合
- 入力が一切書き換わらないこと、全結果で実行権限なし

今回のテストは合成ケースであり、実際のEA停止、注文取消・決済、ブローカー注文履歴、原子的永続化、実口座の同一性は確認できない。

## 変更しない条件

- 楽天証券への問い合わせなし、別デモBや複数MT4環境の構築なし。
- 既存MT4の起動、口座ログイン/照会、EA/EX4、注文/決済を一切行わない。
- 最新の「楽天口座は休眠・建玉なし」と、以前の「MT4デモAのEA・注文あり」は未実測で、口座同一性は未確認。
- 1取引リスク0.5%、総リスク1.0%、日次損失1.5%、DD5%停止、DD4%の人間承認など既存リスク制限を緩めない。

## 本PRの受入条件

- [ ] 新規32件＋従来600件の計632件を本人Windowsで確認
- [ ] Repository checks、Windows Python 3.13のCI成功
- [ ] D5-7/8/9/10/18の既存コードは変更なし
- [ ] 合成整合であっても安全ホールド・NO_GOは継続
- [ ] 口座・MT4・EA・注文へのアクセスは一切未承認
- [ ] 本人が差分を目視確認した上で手動マージ

**D5-19完了＝オフライン結合試験の成功。実運用の安全認定や注文権限の発行ではない。**
