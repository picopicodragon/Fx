# P0-01 D5-29：G2証拠の受入前チェックとG6停止履歴の復元判定

作成日：2026-10-30。前工程D5-28はPR #143マージ、本人Windows 1,083件OK、GitHub CI成功。D5-29は **OFFLINE_SYNTHETIC_PREACCEPTANCE_ONLY**。このPRはMT4・楽天口座・EA/EX4・発注・建玉・通知・Windows実時計・ファイル保存や復元の実行を行わない。

## 目的と入力の信頼境界

D5-28のG2合成証拠フォーマットとG6受入基準を、過去報告の出典管理および停止履歴の合成復元前後比較へ拡張する。**受入前の形式チェックは実証ではなく、承認・取引開始の判断にも使用しない。**

- 新規関数：`scripts/p0_01_d5_29_evidence_restore_gate.py` の `evaluate_d529_evidence_restore(contract, source_ledger, d528_contract, payload)`。**引数は全て未信頼な呼出元供給のJSON相当値**。
- 新規仕様：`specs/p0_01_d5_29_preacceptance_contract.json`。D5-17の`EV-OLD/EV-NEW`とD5-28の`G6-AC-01〜10`を明示的に登録。
- 新規合成ケース：`specs/p0_01_d5_29_synthetic_fixture.json`。口座・端末・日時・停止履歴は**全て架空**。古い申告に存在しない観測時刻を追加・確定したものではない。
- D5-17の原申告台帳とD5-28の合成子ゲートを再検査する。両者も入力側から改ざんできるため**真の原本照合や本人認証にはならない**。

## G2：証拠の受入前チェック

D5-17で未解消の事実：
`EV-OLD`は過去の「MACD Sample装着」「AutoTrading OFFらしい」「建玉または注文があった」という報告。後の`EV-NEW`は休眠・建玉と注文なしという別の報告。**対象口座と観測日時が一致するか不明であり、現在状態の結論は出せない。**

各合成証拠の「出典エンベロープ」には次を要求する：
`report_id`、`source_kind`、合成`account_token`と`terminal_token`、`observed_at_utc`と`recorded_at_utc`、`provenance_attested=false`、`account_attested=false`、`real_world_verified=false`、`synthetic_only=true`。

受入前検査では、出典IDと種別の組合せ、D5-28合成レコードとのラベル・時刻の一致、追加の機密口座識別欄や実証済みフラグの混入を検査する。D5-28の子ゲートにより、UTC時刻形式、観測時刻≤記録時刻、2つの合成記録の口座/端末/観測日時/建玉/未約定注文/EA/AutoTradingの不一致を個別分類する。

**注意**：出典エンベロープの一致は、実際の証拠の出典や時刻を認証するわけではない。全項目が揃った架空データでも`D529_SYNTHETIC_PREACCEPTANCE_MATCH_NEVER_AUTHORIZED`という**NO_GO**で終わる。

## G6：復元前後の合成スナップショット比較

それぞれの合成停止スナップショットに、`record_id`、`generation`、`sequence`、`head_hash`、`revocation_tombstone`、`stop_latched`の6項目を要求。さらに次の信頼できない申告を受ける。

| 検査 | 形式上の判定条件 | 不適合時 |
|---|---|---|
| 書込み・読出し・取消し索引 | 合成状態がすべて`SYNTHETIC_CONFIRMED` | 復元不確実、停止継続 |
| 単調時計・書込み主体 | 合成`CLOCK_STABLE`、`SINGLE_WRITER` | 復元不確実、停止継続 |
| 故障注入 | D5-27で定義した10脅威のいずれかがある | 復元不確実、停止継続 |
| 停止ラッチ | 前後とも`true` | 停止ラッチ喪失、取引禁止 |
| レコード範囲 | 前後同一の合成`record_id` | 復元スコープ不一致 |
| 巻戻し | 復元後の世代・連番が前より小さくない | 巻戻し拒否 |
| 取消し墓標 | 取消しを復元後に消さない | 取消し消去拒否 |
| 不意の進み | 復元後の世代・連番は前と同じ | 外部証明がない進みを拒否 |
| チェックポイントハッシュ | 前後ハッシュ一致 | ヘッド不一致 |

全ての項目が一致しても、**実ディスク書込みの成功、第三者に独立した世代の存在、停止記録の真正性、復元の完了を証明しない**。本仕様では合成履歴と基準点を同時に改ざんして同じハッシュへ揃えたケースは検出不能として試験し、なお権限を与えない。

D5-23〜24からの既知の限界：攻撃者が復元前の基準値と復元後の値、履歴、第三の参照を全て改ざん可能なら、未信頼な比較では攻撃を検出できない。信頼された外部世代、署名、鍵・ストレージの保護、原子的書込み、ホストOSの故障注入は**G6未解決のまま**、後日別の個別承認が必要。

## 拒否判定一覧

1. `D529_DESIGN_REJECTED_FAIL_CLOSED`、`D529_SOURCE_BASELINE_REJECTED_FAIL_CLOSED`：仕様・過去申告の不正変更
2. `D529_INPUT_REJECTED_FAIL_CLOSED`、`D529_CHILD_CONTRACT_REJECTED_FAIL_CLOSED`、`D529_EVIDENCE_CASE_REJECTED_FAIL_CLOSED`、`D529_PROVENANCE_LINK_REJECTED_FAIL_CLOSED`、`D529_RESTORE_INPUT_REJECTED_FAIL_CLOSED`：入力不正、D5-28の偽GO・実証済み主張、出典リンク不備など
3. `D529_STOP_RELEASE_CLAIM_DENIED_NO_GO`、`D529_RESTORE_UNCERTAIN_NO_GO`、`D529_STOP_LATCH_LOSS_NO_GO`：解除申告や復元の不確実性
4. `D529_RESTORE_SCOPE_MISMATCH_NO_GO`、`D529_RESTORE_ROLLBACK_NO_GO`、`D529_REVOCATION_ERASURE_NO_GO`、`D529_REVOCATION_CHANGE_NO_GO`、`D529_RESTORE_UNPINNED_ADVANCE_NO_GO`、`D529_RESTORE_HEAD_MISMATCH_NO_GO`：復元比較異常
5. `D529_EVIDENCE_NOT_PREACCEPTABLE_NO_GO`、`D529_SYNTHETIC_PREACCEPTANCE_MATCH_NEVER_AUTHORIZED`：G2合成証拠の不足/内部整合。内部整合でもNO_GO
6. `D529_INPUT_EXCEPTION_FAIL_CLOSED`：予期しない例外

**全返却値**で`safety_hold_latched=true`、`phase_1=BLOCKED`、`runtime_go_no_go=NO_GO`、`verified_values=null`。実本人確認、出典真正性、口座同一性、ストレージ真正性、取消しの耐久性、停止解除、MT4起動、デモ/本番取引、発注、EA/EX4実行等の許可を表す全フィールドは`false`。

## 受入・次段階

- 新規73件、既存D5-28まで1,083件、**合計予定1,156件**。本PRもCIと本人Windows実行が必要。
- G1〜G9は全件`UNRESOLVED`、G2口座同一性は`NOT_RECONCILED`、建玉・予約注文・EAは`UNKNOWN`を維持。
- 楽天問い合わせを行わず、デモ口座追加なし。WindowsやMT4のローカルログ・機密IDは扱わない。
- [ ] GitHub Repository checks／Windows Python 3.13 CIが成功。
- [ ] 本人Windowsの全1,156件が成功。
- [ ] 本人がPR差分を確認し手動マージ。マージ・テスト成功は実環境アクセスの承認ではない。

**D5-29の完了は、完全なオフライン証拠形式・合成復元比較に限る。実装済みの運用可能な復元制御を意味しない。**
