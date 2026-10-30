# P0-01 D5-30：G2証拠収集SOP案・G6独立保存アーキテクチャ案

作成日：2026-10-30。前工程 D5-29 はPR #144マージ、本人Windows 1,156件 OK、GitHub CI 成功。

**本工程の境界**：GitHubの仕様書・合成テストのみ。MT4の起動/ログイン/照会、口座へのアクセス、EA/EX4の実行、発注、OSローカルファイルへの保存・復元、実時計取得、通知送信、楽天への問い合わせ、別デモ口座の開設は行わない。本PRは今後の実機作業の承認を申請・取得・推定しない。

## 1. G2：将来の証拠収集と非公開・公開の分離

D5-17の未照合ユーザー報告は依然として以下の状態。

- `EV-OLD`：過去のMT4デモAでMACD Sampleの存在、AutoTrading OFFらしい表示、建玉**または**未約定注文ありという報告。対象の時刻・口座識別は未確認。
- `EV-NEW`：後の既存休眠口座について、建玉・注文なしという別報告。前報告と同じ口座・同じ時間の状態を意味しない。
- 現在の建玉・未約定注文・EAは`UNKNOWN`、口座同一性は`NOT_RECONCILED`。どちらのユーザー報告も認証済みの証拠ではない。

### 未実施の将来確認候補8件

| ID | 提案する確認対象 | 現在の実施状態 |
|---|---|---|
| D530-G2-01 | MT4端末の識別・出典 | NOT_PERFORMED |
| D530-G2-02 | 口座・サーバーの同一性 | NOT_PERFORMED |
| D530-G2-03 | 単一接続・セッション | NOT_PERFORMED |
| D530-G2-04 | EA装着・AutoTrading表示を別々に扱う | NOT_PERFORMED |
| D530-G2-05 | 現在の建玉の有無 | NOT_PERFORMED |
| D530-G2-06 | 現在の未約定注文の有無 | NOT_PERFORMED |
| D530-G2-07 | 観測/記録の時刻と証拠の出典 | NOT_PERFORMED |
| D530-G2-08 | 既存ログの取扱い | NOT_PERFORMED |

**具体的なSOP候補（実施していない）**：

1. 将来、作業の対象を既存の単一MT4環境に限定し、目視・既存ログ閲覧・新規起動・ログインなどの行為ごとに本人の**個別明示承認**を得る。旧デモAと休眠口座が同一か未確認のまま操作しない。
2. 目視確認の対象と観測の出典・時刻を明示的に区別し、建玉・未約定注文・EA装着・AutoTradingを独立に記録する。過去の報告に推測の日時を足さない。
3. 口座番号・サーバー識別・端末パス・スクリーンショット・MT4生ログ・IP/端末識別子・認証情報・実注文詳細・実観測時刻は、**将来の許可済みローカル保護領域だけ**に置く設計とする。保管方法、アクセス権、保存期間、削除・流出時の扱いは別途仕様・承認が必要。
4. GitHubへ記録する予定の公開用レコードには、原則として`check_id`、`design_state`、`simulation_only`など非識別・設計用メタデータ以外を許さない。マスキングを施しただけの画面/ログも、その安全性が別途確認されるまでGitに含めない。
5. 出典が不明、時刻が未確定、対象口座が不一致、建玉・注文・EAが不明な場合は`NOT_RECONCILED`を維持し、**自動GO・注文・EA実行・停止解除へ移行しない**。

これらの収集用UI、プライベート保管庫、マスキング実装、閲覧機能は**D5-30では未実装**。`specs/p0_01_d5_30_collection_persistence_architecture.json`は未実施のチェック項目とプライバシー区分を示すだけである。

## 2. G6：提案する責務の分割（すべて未実装）

| ID | 設計コンポーネント | 責務案 |
|---|---|---|
| C01 | STOP_LATCH_AUTHORITY | 不確かな状態で停止を保持。自動解除を許さない |
| C02 | SINGLE_WRITER_FENCE | 書込み主体の排他と世代境界 |
| C03 | APPEND_ONLY_JOURNAL | 停止・変更・取消しイベントの追記 |
| C04 | REVOCATION_TOMBSTONES | 取消しの耐久記録と消失拒否 |
| C05 | ATOMIC_COMMIT_COORDINATOR | ローカル保存処理の確定順序 |
| C06 | INDEPENDENT_MONOTONIC_ANCHOR | 別の書込み主体/保護境界にある単調な基準 |
| C07 | KEY_AND_SIGNATURE_VERIFIER | 鍵保護・署名検証・失効対応 |
| C08 | RECOVERY_VERIFIER | 復旧時に停止・世代・墓標・ハッシュを照合 |
| C09 | MONOTONIC_CLOCK_ADAPTER | 単調増加時計とUTCの役割分離、再起動異常の扱い |

**信頼境界**：同じPythonプロセスが作った履歴ハッシュ・チェックポイント・参照値を同じ場所で保護しても、3点の同時偽造には対抗できない。独立した署名検証者・鍵と単調な参照基盤・耐改ざん性の実証が必要である。現在それらの実体はない。

### コミット/復元の順序案

1. `LATCH_STOP_BEFORE_ACTION`：新規操作より前に停止を保持する。
2. `PREPARE_JOURNAL_AND_TOMBSTONE`：停止・取消しの記録候補を準備する。
3. `FLUSH_DURABLE_LOCAL_STATE`：将来の永続化境界で実際の耐久性を確保する。
4. `VERIFY_CHECKPOINT_AND_WRITER_FENCE`：チェックポイントと書込み主体を再確認する。
5. `PUBLISH_INDEPENDENT_ANCHOR`：独立した参照基準へ進める。
6. `FINALIZE_LOCAL_CHECKPOINT`：ローカルの確定状態に反映する。
7. `VERIFY_RECOVERY_WITH_STOP_STILL_LATCHED`：復旧時も停止が維持されていることを確認する。

**これはプロトコルの候補であり、異なる保存先を横断する真の原子性を保証するものではない。** 例えば外部基準だけが進み、クラッシュでローカル確定値が古いままとなる可能性がある。その場合に復旧を自動許可するのではなく、証拠不一致として停止を保持する。永続化順序の実装可能性・鍵管理・性能・権限・実OSクラッシュ試験は未評価。実装前の別レビューでトランザクション仕様を具体化する必要がある。

### 障害と将来受入条件

D5-27〜29の10脅威（原子的保存破損、書込み中断、巻戻し、3点同時改ざん、取消し削除、同時書込み、時計異常、鍵攻撃、保存不可、旧バックアップ復元）を`D530-G6-F01〜F10`に対応付け、全て`STOP_LATCHED_NO_GO`を設計上の期待値とする。

`real_fault_injected=false`、`independent_proof_required=true`。G6の各部品は`DESIGN_ONLY`であり、実ファイルI/O・Windowsの停止時間計測・署名/鍵管理・独立Trust Anchorは存在しない。本人が明示的に将来の非MT4隔離試験を承認し、実際の障害試験を経ない限り検証済みにしてはならない。

## 3. 機械可読の拒否専用監査

`scripts/p0_01_d5_30_architecture_review.py` の

`review_d530_offline_architecture(plan, original_evidence, gap_matrix, synthetic_case)`

は、未信頼なD5-30設計とD5-17原申告記録、D5-25未解決G1〜G9台帳、完全合成の診断ケースを再照合する純粋関数である。

| 入力状態 | 判定 |
|---|---|
| 設計/スキーマ不正、実行済み・実証済みの偽装 | `D530_DESIGN_REJECTED_FAIL_CLOSED` |
| D5-17出典・旧口座状態の不正改変 | `D530_SOURCE_BASELINE_REJECTED_FAIL_CLOSED` |
| D5-25 G1〜G9の虚偽解消 | `D530_GAP_BASELINE_REJECTED_FAIL_CLOSED` |
| 合成ケースの不正形式・秘密データの余分なフィールド | `D530_CASE_REJECTED_FAIL_CLOSED` |
| MT4/EA/OS I/O/発注/解除の実行申告 | `D530_UNAUTHORIZED_OPERATION_DENIED_NO_GO` |
| G2機密・出典・口座/時刻スコープの合成異常 | `D530_G2_CAPTURE_OR_PRIVACY_UNSAFE_NO_GO` |
| G6コミット・巻戻し・取消し・時計・鍵等の合成故障 | `D530_G6_RECOVERY_UNTRUSTED_NO_GO` |
| 合成データが整合 | `D530_ARCHITECTURE_DESIGN_COHERENT_NEVER_AUTHORIZED` |

全結果で`safety_hold_latched=true`、`phase_1=BLOCKED`、`runtime_go_no_go=NO_GO`、`verified_values=null`。G2/G6実検証・証拠取得、MT4起動、ログイン、実ファイル保存、発注、EA、停止解除、本番稼働などの許可は**すべてfalse**。どんな合成結果も実環境での実行権限に昇格しない。

## 4. 品質確認と残条件

- 前段1,156件、新規75件、**想定合計1,231件**。
- 既存D5-17〜29のコード・証拠台帳・リスク上限を一切変更しない。
- G1〜G9は全件`UNRESOLVED`、G2の口座同一性は`NOT_RECONCILED`、建玉・未約定注文・EAは`UNKNOWN`。
- 楽天への問い合わせを送らず、別デモBを作らず、単一MT4環境と複数環境非同時ログイン方針を維持する。
- [ ] GitHub Repository checksとWindows Python 3.13 / IANA time zonesのCI成功。
- [ ] 本人Windowsで全1,231件のユニットテスト成功。
- [ ] 本人によるPR差分のレビューと手動マージ。マージや合成テスト成功は人間承認/実運用許可ではない。

**D5-30完了の意味は、将来の収集・保存に向けた設計案と、その拒否専用オフライン検証の完成のみ。** 実口座の照合、プライベート保管・暗号署名・原子的書込み・真正なTrust Anchorは未実装であり、以降も個別明示承認なしに実機へ進まない。
