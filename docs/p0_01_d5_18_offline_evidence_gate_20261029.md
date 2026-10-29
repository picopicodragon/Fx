# P0-01 D5-18：単一MT4証拠のオフライン判定ゲート

作成日：2026-10-29。対象：D5-17既存証拠台帳と**純粋に合成した**判定用の仮想記録。コード：`scripts/p0_01_d5_18_evidence_gate.py`、テスト：`tests/test_p0_01_d5_18_evidence_gate.py`。

**実環境評価・MT4照会・発注・実測は行わない。出力のどの状態も取引許可を意味しない。**

## 目的とAPI

1. `evaluate_d517_evidence_ledger(ledger)`：D5-17のJSON台帳の**既知の未確認状態**を読み取る。EV-OLDとEV-NEWは別の口座・別の時点を指している可能性があるため**自動で突合/統合しない**。全S17未実施、個別承認なし、建玉/未約定注文UNKNOWN、口座同一性NOT_RECONCILEDという保守的な姿だけを受け入れる。ユーザーの自己申告やJSONフラグをブローカー実測に格上げしない。値が一部でも「確認済み」に書き換われば`LEDGER_REJECTED_FAIL_CLOSED`。
2. `evaluate_synthetic_evidence_records(bundle)`：`origin=SYNTHETIC_ONLY`、`schema_version=1`の仮想データのみを受け入れる。口座スコープは`SYNTHETIC_...`という非機密なラベル、IDは`EVID_...`で表す。実際のログインID・口座番号や認証情報を渡さない。1〜20件まで。ファイル/ネットワーク/時刻へのアクセスや副作用なし。

合成記録の必須フィールド：
`evidence_id`、`source_kind`（`USER_REPORT` / `VISUAL_OBSERVATION` / `SYNTHETIC_SYSTEM_MEASUREMENT`）、`account_scope`、`observed_at_utc`（`YYYY-MM-DDTHH:MM:SSZ`またはnull）、`positions`、`pending_orders`、`ea_running`（各`PRESENT/ABSENT/UNKNOWN`）。

**注意**：`SYNTHETIC_SYSTEM_MEASUREMENT`は合成データ内の分類名にすぎず、実際にシステムからデータを取得したという意味ではない。入力のsource_kind文字列やJSONだけで真正性を保証できない。

## 判定の優先順位

| 優先 | 結果 | 条件と意味 |
|---|---|---|
| 1 | `SYNTHETIC_INPUT_REJECTED_FAIL_CLOSED` / `LEDGER_REJECTED_FAIL_CLOSED` | スキーマ破損、型不一致、未知の出典、無効日時、重複ID、疑似承認フラグ等 |
| 2 | `ACCOUNT_SCOPE_MISMATCH_NO_GO` | 同じ仮想口座に関する照合だと保証できない |
| 3 | `EVIDENCE_CONFLICT_NO_GO` | **同一仮想口座・同一UTC時点**で既知値PRESENT/ABSENTが衝突 |
| 4 | `EVIDENCE_INSUFFICIENT_NO_GO` | 時点違い、出典1種類のみ、時刻未記録、UNKNOWNなど。違う時点で値が異なるだけでは同時矛盾とはしない |
| 5 | `SYNTHETIC_INTERNALLY_CONSISTENT_NO_GO` | 同一仮想口座・同一UTC時点、2件以上・出典2種以上で3項目が既知かつ無矛盾。**合成入力内で整合しただけ** |
| 固定 | `D517_REPORTS_NOT_RECONCILED_NO_GO` | 既存D5-17台帳の2件が区別され、未確認であることを確認 |

いずれも返値の`account_identity_consistency=NOT_RECONCILED`、`positions_status=UNKNOWN`、`pending_orders_status=UNKNOWN`、`ea_running_status=UNKNOWN`を維持。合成結果で実口座の状態を更新しない。

## 永続的な拒否事項

全出力共通：
`runtime_go_no_go=NO_GO`、`verified_values=null`、`broker_verified=false`、`production_usable=false`、`read_only_ex4_execution_approved=false`、`terminal_execution_approved=false`、`orders_generated=false`、`forward_trading_enabled=false`、`phase_1=BLOCKED`。

- 楽天への問い合わせ、追加デモB、複数口座/複数MT4環境、EA/EX4起動、MT4ログイン、口座照会、注文操作はしない。
- 既存の休眠・建玉なしという最新申告と、過去のデモAに関するMACD Sample・注文あり目視報告は異なる証言として保持。
- 口座が同じ・EAが停止している・取引許可があると推定しない。
- DD4%/5%、日次損失1.5%、1取引0.5%、同時リスク1.0%などの既存安全制約を緩めない。

## 受入基準

- [ ] D5-17台帳そのままの評価は`D517_REPORTS_NOT_RECONCILED_NO_GO`
- [ ] D5-17台帳の実証/承認を装った変更は拒否
- [ ] 合成同時矛盾、口座違い、時刻違い、情報不足、正常な合成整合性を区別
- [ ] 入力不変・外部アクセスなし・全分岐NO_GO
- [ ] Windowsローカル全テスト、Repository checks、Windows Python 3.13 CI成功
- [ ] PR差分を本人が目視し、本人が手動マージ

**D5-18完了はオフライン判定コードと合成テストの成立のみ。実機安全性の認定・取引権限の発行は一切しない。**
