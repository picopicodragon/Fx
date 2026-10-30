# P0-01 D5-33：G2公開/非公開の境界とG6独立証拠の将来受入要件

作成日：2026-10-30。前段D5-32：PR #147マージ済み、本人Windowsの1,469件OK、GitHub CI成功。

**範囲は設計とオフライン合成検証のみ。** 実楽天口座・MT4・EA/EX4、実証拠収集、実ファイルI/O、Gitフック実装、実秘密情報スキャン、暗号署名・鍵検証、Windows単調時計取得、注文/決済、停止解除を行わない。すべての合成結果とPRマージは実運用への権限を発生させない。

## 1. G2：公開レコードと非公開証拠を明確に分離する

D5-31/32の公開JSONは、`check_id`、`design_state`、`origin`、`schema_version`、`simulation_only`の固定5フィールド・固定値のみである。公開JSONが非公開データから自動生成されたことはない。今後の公開・保管が承認されたわけでもない。

D5-33では、非公開領域の**合成上の封筒（envelope）**を別データとして定義した。内容は架空の口座ラベル、`EV-OLD/EV-NEW`の参照、`raw_payload_present=false`、`private_export_requested=false`、`provenance_authenticated=false`、`account_identity_verified=false`、`observed_at_verified=false`、`simulated_only=true`だけ。実口座番号、実スクリーンショット、実MT4ログ、取引明細、パスワード、実観測時刻を**渡す設計ではない**。

検査では、非公開情報の公開要求、秘密データを含む余分なフィールド、出典・口座・観測時刻が実証済みだという偽申告を拒否する。合成公開JSONはD5-32で事前定義した文字列と一致させ、異なる公開チェックIDを勝手に組み合わせた場合も拒否する。非公開の架空ラベルが整合しても、実際の同一口座認証の根拠にはならない。

### 既知の限界

この構成は**入力形式を受け入れないための純粋関数**であり、実GitHubコミット、変更差分、ログ、過去のGit履歴、未表示メタデータなどの全域スキャンではない。Gitフック・CIシークレットスキャン・ローカル保護領域・秘匿化エクスポータは未実装。機密情報が実Gitへ混入しないことを保証できない。将来これらを導入する場合は実データを不用意に公開しない設計と個別承認が必要。

`EV-OLD`は過去のMT4デモAの状態申告、`EV-NEW`は後の休眠口座申告。観測日時も口座同一性も不明。建玉・未約定注文・EAの現在値は`UNKNOWN`、口座同一性は`NOT_RECONCILED`を維持する。

## 2. G6：独立証拠を要件として記載（実体は未実装）

将来の真の復元判定に必要な証拠の候補を5種類の`witness`に分ける。

| 証拠源の概念 | 将来検証すべき役割 | 現在 |
|---|---|---|
| LOCAL_JOURNAL | 停止・イベント連番・履歴ヘッド | 合成ラベルのみ |
| INDEPENDENT_ANCHOR | 別保護境界で保持される単調な世代基準 | **未実装** |
| REVOCATION_REGISTER | 取消し墓標の永続性と復元後の消失拒否 | **未実装** |
| SIGNATURE_KEY_VERIFIER | 独立鍵・署名・失効・所有者の信頼関係 | **未実装** |
| MONOTONIC_CLOCK_WITNESS | 再起動・時刻補正に左右されない時間根拠 | **未実装** |

合成レコードの項目は、架空の`record_id`、世代・連番・ヘッドハッシュ、取消し墓標、停止ラッチ、`observed_tick`、`source_boundary`等。試験には`simulated_reference_tick=100`という架空の基準を使い、観測との差が**合成5tick以内**であるかだけを確認する。これは実秒数・有効期限を設定したものではなく、実時刻の真正性を検証しない。実時計・再起動・DST等の問題はG7も含め未解決。

5レコードは必ず既定の種類/順序/形式に一致し、D5-32の基準スナップショット（未信頼）と同一の対象、世代、連番、ハッシュ、取消し墓標、停止ラッチを持つ必要がある。いずれかの欠落・余分・重複・スコープ不一致・未来tick・古いtick・署名/独立性実証の偽申告・共有境界・停止解除要求は**NO_GO**。

### 独立性と改ざん防止の重要な限界

`source_boundary=SYNTHETIC_SEPARATE_LABEL_ONLY`は**独立したTrust Anchorや秘密鍵の存在を意味しない**。この5レコードは同じ呼出元が作成・同時偽造できる。全レコードとD5-32の基準値まで同時に改ざんした場合、値の比較だけで改ざんを検出できない。署名もハッシュの暗号的な真正性も一度も確立していない。

将来必要なのは、独立した信頼根・発行者の本人確認・鍵/世代の保護・単調な外部比較基準・取消しの耐久性・クラッシュ時の復旧境界に関する実装と、別途承認された障害試験。これらが欠ける間は、合成内容が整合しても**停止解除・自動再開を認めない**。

## 3. D5-32の横断検査と拒否コード

`review_d533_independent_proofs(contract, d532_contract, d531_contract, old_evidence, gap_matrix, d532_fixture, synthetic_case)` は全入力を未信頼として再検査する。まず前段のD5-32クラッシュ地点×脅威マトリクスが**必ずNO_GOで内部整合**するか、返値の承認フラグが全部偽であるかを確認し、その上でG2/G6を評価する。前段が別の拒否結果になった場合も停止を維持する。

代表的な拒否コード：

- `D533_CONTRACT_REJECTED_FAIL_CLOSED`、`D533_CASE_REJECTED_FAIL_CLOSED`：設計・入力形式の不正
- `D533_G2_PUBLIC_PRIVATE_MISMATCH_NO_GO`：G2公開レコードの不整合
- `D533_PREDECESSOR_BASELINE_REJECTED_FAIL_CLOSED`、`D533_CHILD_DENIAL_INVARIANT_REJECTED_FAIL_CLOSED`、`D533_PREVIOUS_STAGE_DENIED_NO_GO`：過去のG1〜G9台帳改変や前段の不一致
- `D533_OPERATION_CLAIM_DENIED_NO_GO`、`D533_G2_PRIVATE_EXPORT_DENIED_NO_GO`、`D533_G2_PRIVATE_EVIDENCE_UNTRUSTED_NO_GO`：実操作、非公開の公開、実証済みの偽申告
- `D533_G6_PROOF_SET_REJECTED_FAIL_CLOSED`、`D533_G6_PROOF_SCOPE_REJECTED_FAIL_CLOSED`：G6必要証拠の欠落・重複・形式不一致
- `D533_G6_FALSE_AUTHENTICATION_CLAIM_NO_GO`、`D533_G6_SHARED_TRUST_BOUNDARY_NO_GO`、`D533_G6_SYNTHETIC_STALE_OR_FUTURE_NO_GO`、`D533_G6_WITNESS_CONTRADICTION_NO_GO`：独立性や署名の偽申告、共有根、古さ、矛盾
- `D533_SYNTHETIC_PROOF_FORMAT_COHERENT_NEVER_AUTHORIZED`：合成上で整合。**認証・承認を意味しない**
- `D533_INPUT_EXCEPTION_FAIL_CLOSED`：不測の入力・例外

全て`safety_hold_latched=true`、`phase_1=BLOCKED`、`runtime_go_no_go=NO_GO`、`verified_values=null`、`effective_approved_actions=[]`で、MT4・口座照会・EA/EX4・注文・停止解除・実I/O・本番稼働に関連するフラグはすべて`false`。

## 4. QA・受入・残条件

- 追加するもの：`scripts/p0_01_d5_33_proof_boundary.py`、`specs/p0_01_d5_33_proof_boundary_contract.json`、`specs/p0_01_d5_33_synthetic_fixture.json`、`tests/test_p0_01_d5_33_proof_boundary.py`、`specs/p0_01_d5_33_status.json`、本書。
- 既存1,469件＋今回98件、**合計想定1,567件**。
- [ ] GitHub Repository checksとWindows Python 3.13 / IANA time zones CI成功。
- [ ] 本人Windowsの全1,567件成功。
- [ ] 本人の差分目視確認後、手動マージ。マージも口座・注文・停止解除の承認ではない。

既存の損失/DDリスク上限、NY17日次境界、単一MT4環境、楽天へのメール問い合わせ中止、別デモB不採用・同時複数ログインなしを継続。**G1〜G9はすべて未解決**。実証は必要な個別許可と事前レビューを得てから別工程で検討する。
