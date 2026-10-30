# P0-01 D5-41：G6-02独立Trust Anchorの候補比較・必要証拠・選定条件

2026-10-30。前工程D5-40はPR #155マージ済み、本人Windows `Ran 2517 tests in 2.435s` / `OK`、GitHub CI成功。

## 目的と現段階の結論

G6-01で定義した4種の候補から、**実証可能性の検討対象**をローカルハードウェア保護候補と別管理領域のリモートWitness候補の2種類に絞り、将来の人間による選定に使う独立検証要件を比較した。**正式な方式採用、業者/製品選定、金銭的見積り、実Trust Anchorの構築は行っていない**。この比較は市場調査や製品性能認証ではなく、候補方式別の**未解決事項と必要証拠を漏れなく列挙する設計文書**である。

G6-02はG6-01の設計・独立性検査の後続。G2-06機密保管庫、G2-07 Git/CI漏えい防止、G8本人承認は設計上の先行関係として維持されるが、いずれも現実の実装・実証・本人承認を取得していない。

## 1. 比較対象の2方式

| 比較対象 | 有利になる可能性のある設計特性 | 本質的な未解決事項 |
|---|---|---|
| **LOCAL_HARDWARE_ROOT_CANDIDATE** | 特定の鍵操作/保管をローカルプロセス外の保護境界に置く設計余地。外部ネットワーク停止の影響範囲を抑えられる可能性 | Windows管理者・ディスク巻戻し、epoch世代と発行者失効の耐久性、独立時計・復旧・端末交換、ローカル単独の共有故障点。TPM等の製品仕様を未検証 |
| **REMOTE_SEPARATE_WITNESS_CANDIDATE** | 別運用者・別保存/承認境界によるローカル主体からの独立性を設計しうる | 同じクラウド/CI権限に支配されていない証拠、遠隔管理者の真正性、外部可用性・通信断、fork/split-brain、保管場所・漏えい防止、費用・運用継続性。サービス/事業者は未選定 |

同一プロセス内ミラーと単一ホストの別OSユーザーは独立外部証拠として採用しない方針を維持。ハードウェア保護やリモートWitnessにも、**独立アンカーを認証できる**という結論は出さない。共通のOS管理者が実装・鍵・復旧パスを支配すれば見た目の隔離は破られる可能性がある。

## 2. 14観点×2方式＝28個の未取得証拠

| 比較軸 | 将来の受入で必要な確認 |
|---|---|
| ADMIN_BOUNDARY | 実運用者・管理権限が独立していること |
| WRITE_BOUNDARY | 発行/証明の書込み主体が同時改ざんできないこと |
| CREDENTIAL_BOUNDARY | 鍵・資格情報/アクセス権の共通支配がないこと |
| ROLLBACK_RESISTANCE | OS復元・古い署名データの再生・epoch巻戻しを検知拒否できること |
| FRESHNESS_SOURCE | 時計/タイムスタンプの真正性と失効したデータの陳腐化判定 |
| REVOCATION_DURABILITY | 鍵失効・墓標が再起動/バックアップ復元で消失しないこと |
| KEY_ROTATION_AUTHORITY | 旧発行者から新発行者への交代を別の独立権限で承認できること |
| SPLIT_BRAIN_DETECTION | 異なる枝/世代が双方最新を名乗る状態を検出して停止すること |
| STOP_LATCH_CONTINUITY | Anchor・ネットワーク断・再起動時にも停止を維持すること |
| PRIVACY_NON_EXPOSURE | G2秘密/口座情報がAnchor・ログ・公開面に漏れないこと |
| LIFECYCLE_COST | 初期費用/継続/交換/退去費用の実見積りを出典・時点付きで照合 |
| OPERATIONAL_BURDEN | 人手の管理・復旧/アップデート・失効の権限/負担 |
| FAILURE_RECOVERY | 通信断・電源断・端末/設備交換/災害復旧と停止継続 |
| DATA_RESIDENCY | データの所在/外部送信の法令・契約・プライバシー適合性 |

前半の10軸はD5-40で定義したG6-01の検証軸をそのまま引継ぎ、4軸を運用判断用に追加した。28件の`real_evidence_status=NOT_COLLECTED`、`human_review_status=NOT_GRANTED`、`actual_evidence=null`、`real_cost_amount=null`、`actual_acceptance=false`。金額・SLA・プロバイダー名は作り上げない。**設計上の列挙の完成と28件の実証完了を混同しない。**

## 3. 16種類の障害/攻撃の将来の検証ケース

各候補で共通管理者、過去状態のリプレイ、Witness欠測、分岐した最新レコード、失効した発行者、停止ラッチの欠落、私的データの混入、災害復旧の**8ケース**を要求し、計16ケースを固定。すべて`test_state=NOT_RUN`、`simulation_only=true`、`real_fault_executed=false`、`real_recovery_verified=false`、`stop_release_authorized=false`。許容すべき故障時の判定は全件`DENY_AND_HOLD_STOP`。

実際の見積りや製品適合性、ロールバック/失効の独立証明は、将来の**別途承認された実環境**で採取・認証する必要がある。既存のG2保管庫/公開境界も未実装なので、実証拠のGitHubコミット・PRへの転記を認めるものではない。

## 4. 今回の合成監査関数

`review_d541_anchor_candidates(contract, matrix, predecessor_bundle)` は、D5-40の12脅威/4候補の拒否関数とさらに以前のG2/G6合成ゲートを再実行する。全入力は未信頼で、2候補/14軸/28件/16障害のID・順序・出典区分・未実証ステータスを固定照合する。実装済み・証明済み・費用確認済み・方式採用済み・本人承認/停止解除済みとする偽申告は例外なく拒否する。

- `specs/p0_01_d5_41_anchor_selection_contract.json`：2方式、14軸、選定無効の設計契約。
- `specs/p0_01_d5_41_candidate_evidence_matrix.json`：28件の受入証拠の未取得台帳と16障害ケース。
- `scripts/p0_01_d5_41_anchor_selection_review.py`：純粋な拒否監査。ホストのファイル/OS/Git/ネットワーク/鍵/MT4を参照しない。
- `tests/test_p0_01_d5_41_anchor_selection_review.py`：新規231件。28証拠×3偽昇格84件、16故障×4偽申告64件、候補2×3偽昇格6件、無断の選定/鍵/実証明/費用/ネットワーク等16件、横断・前段・非I/Oの61件。
- `specs/p0_01_d5_41_status.json`：実受入0件、実Anchor0件、G1〜G9未解決と停止保持。
- 本書。

既存2,517件＋新規231件＝**全2,748件（CI・本人Windowsでの確認前の予定値）**。CI成功/本人ローカルテストの成功は純粋合成審査の成功に限る。本人がPRの差分と判定を確認したうえで手動マージし、後日必要なら明確な別工程として方式選定の審査を行う。自動採点/自動採用はしない。

## 5. 継続する安全条件

G1〜G9`UNRESOLVED`、`PHASE-1 BLOCKED`、`runtime_go_no_go=NO_GO`、`verified_values=null`、`safety_hold_latched=true`、`effective_approved_actions=[]`。G2/G6の15基準の実受入0/15件、実作業0/15件、実独立Trust Anchor0件。旧/新口座同一性`NOT_RECONCILED`、建玉/未約定注文/EA状態`UNKNOWN`。

単一MT4、同時複数ログインなし、楽天問い合わせ中止、追加デモB不採用。実口座/MT4/EA/EX4、外部Witness構築、TPM/鍵生成/暗号署名、実OS/Git/ネットワーク、秘密情報/証拠収集、注文・決済・通知・停止解除は一切未承認。本工程で実施しない。既存の単発0.5%、同時1.0%、日次1.5%、DD4%/5%の停止条件およびNY17の取引日区切りは変更しない。
