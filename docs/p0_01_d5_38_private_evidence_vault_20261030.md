# P0-01 D5-38：G2-06機密証拠の保管・保持・削除方式の設計

2026-10-30。先行工程D5-37はPR #152マージ済み、本人Windows 2,059件OK、GitHub CI成功。

## 目的と重要な境界

**本工程では保存・収集・削除・暗号化・Git履歴の検査を一切実行しない。** G2-06「PRIVATE_EVIDENCE_RETENTION」の**将来の必要条件**を仕様化した。4種の領域・6種の情報区分・12種の脅威をあくまで架空ラベルとして扱い、実機環境や実口座を認証したり、本物の機密保管庫を実装したりするものではない。

楽天MT4の起動・口座ログイン/照会、EA/EX4実行、注文/決済、通知、実OSファイル読書き/時計の参照、実Gitフック/CI秘密情報スキャン、暗号鍵・署名操作、実Trust Anchor発行、実バックアップ・削除を行わない。実行権限も増やさない。

## 1. 情報区分と境界

G2で将来保護すべきデータは以下6種。**実データは入力していない。**

1. `ACCOUNT_TERMINAL_IDENTIFIERS`：口座/端末の同一性
2. `BROKER_SESSION_AND_SERVER`：サーバー/セッション
3. `EA_POSITION_ORDER_EVIDENCE`：EA、ポジション、未約定注文
4. `RAW_LOG_AND_SCREENSHOT`：生ログ、画像、埋込みメタデータ
5. `SECRET_MATERIAL`：認証情報/鍵、実験用にもGitへ渡さない
6. `OBSERVATION_PROVENANCE`：実際の観測時刻・出典の情報

将来の保存領域の概念として、`PRIVATE_EVIDENCE_ZONE_DESIGN`、`SYNTHETIC_PUBLIC_METADATA_ZONE`、`INDEPENDENT_ANCHOR_ZONE_DESIGN`、`REJECT_OR_QUARANTINE_ZONE_DESIGN`を区別する。**すべて実パスはnull、実読取/書込/エクスポート権限はfalse、未実装。** 独立Trust Anchorを機密証拠保管庫と同じ信頼主体・権限・ストレージであるとみなしてはならない。G6-02の実Trust Anchorは未選定・未実装。

D5-31〜37の合成公開JSON固定5フィールドのallowlistを継承するが、本工程で現実のGitHub PR/コミット/履歴、CIログ/成果物を走査したわけではない。`.gitignore`だけでは、既にコミットされた内容や一時ファイル、CI成果物、クラッシュダンプを保護できない。

## 2. 保持期間・暗号化・鍵・削除

| 将来の設計対象 | 今回の扱い |
|---|---|
| 暗号化アルゴリズムと鍵管理・保管方法 | `UNDECIDED_REQUIRES_HUMAN_REVIEW`。勝手に選定しない |
| 期間、保存開始時点、法令・監査要件、例外・保全 | `UNDECIDED_REQUIRES_HUMAN_REVIEW`。日数や期限を捏造しない |
| バックアップ方式、復元、個人情報を含む複製 | `UNDECIDED_REQUIRES_HUMAN_REVIEW`。現実の消去実証なし |
| 削除操作 | `DELETE_REQUEST_NOT_ERASURE_PROOF`。削除要求、削除成功、全複製消去/暗号消去の証明はそれぞれ別 |
| 監査時刻/出典と公開前の検査 | `NOT_IMPLEMENTED`。実際のGit/CI egress防御もなし |
| G6独立基準点 | `SEPARATE_TRUST_BOUNDARY_NOT_IMPLEMENTED`。外部の独立根拠は未実証 |

実装を検討する際は、少なくともWindows NTFSアクセス制御、ユーザープロファイル/他プロセス権限、ジャンクション/シンボリックリンク脱出、temp/WAL/swap、バックアップ/スナップショット、クラッシュダンプ、監査ログ、Git履歴、CIログ、削除と鍵失効の違いを個別に確認する必要がある。これらは**検討項目**であり、本PRは実設定を変更しない。

## 3. G2-06の脅威と拒否要件（12件）

| 脅威群 | 架空ラベル | 将来の受入証明の例 |
|---|---|---|
| Gitへの混入 | ACCIDENTAL_GIT_COMMIT / GIT_HISTORY_REUSE | 実push以前の遮断、履歴/差分/削除済み記録を含む監査 |
| CI/デバッグ漏えい | CI_ARTIFACT_EXPORT / DEBUG_LOG_EGRESS | 成果物・ログ・実行時例外経路での秘匿検証 |
| OS一時/バックアップ漏えい | TEMP_WAL_SWAP_LEAK / BACKUP_OR_SNAPSHOT_LEAK / CRASH_DUMP_LEAK | 保存先/複製/クラッシュ経路の隔離を実証 |
| パス/ACL境界 | JUNCTION_SYMLINK_ESCAPE / UNAUTHORIZED_READER | 最小権限、リンク脱出/権限変更への耐性 |
| 保持・削除・独立性 | RETENTION_UNKNOWN / DELETION_WITH_REPLICA / SHARED_TRUST_ROOT | 期限・複製消去、G6独立基準との別保護境界 |

各架空脅威の`requested_action=DENY_ONLY`、`destination=DENY_SINK`、`control_implemented=false`、`real_evidence_observed=false`、`mitigation_state=DESIGN_REQUIRED`。PUBLIC_METADATA、GIT_REPOSITORY、CI_ARTIFACT、G6_ANCHORへの漏出申告、実ホスト操作、実消去、実保護実装の偽申告を拒否する。全ての出力はカテゴリー別コードだけであり、入力の秘密情報は出力しない。

## 4. 既存条件の維持と受入

`review_d538_private_vault(design, threat_matrix, workplan, tracking, d536_contract, d536_readiness, d536_actions, d536_predecessors)`はD5-37までの安全側の拒否を再実行し、15作業パッケージが未着手、G2/G6の15基準が未受入、G1〜G9が全件未解決であることを確認する。前段の`GO`や`broker_verified`等の偽昇格を拒否する。

**本工程の完了＝要件文書の作成・合成検査の成功のみ。** G2-06の「受入済み」「実装済み」「証拠採取完了」を意味しない。実証のための行動を提案する前に、その操作に関する対象・範囲・保管・有効期間・削除・取消しを含めた本人の別途個別承認が必要である。

新規6ファイル：
`scripts/p0_01_d5_38_private_vault_review.py`、
`specs/p0_01_d5_38_private_vault_contract.json`、
`specs/p0_01_d5_38_threat_matrix.json`、
`tests/test_p0_01_d5_38_private_vault_review.py`、
`specs/p0_01_d5_38_status.json`、
本書。

既存2,059件＋新規179件＝**予定2,238件**。合成脅威12×8条件96件、保管ゾーン4×4条件16件、操作権限15件、個別・横断・前工程チェック52件。GitHub Repository checks、Windows Python 3.13 CI、本人Windows単体テスト成功後、本人のPR差分目視と手動マージが必要。マージは実装承認・機密証拠の収集許可ではない。

継続：口座同一性`NOT_RECONCILED`、現建玉・未約定注文・EA`UNKNOWN`。G1〜G9`UNRESOLVED`、`PHASE-1 BLOCKED`、`runtime_go_no_go=NO_GO`、`verified_values=null`、`safety_hold_latched=true`。単一MT4環境、楽天への問い合わせ中止、別デモB不採用・同時複数ログインなし。単発0.5%/同時1.0%/日次1.5%、DD4%/5%の段階停止・本人承認、NY17の取引日区切りは変更しない。
