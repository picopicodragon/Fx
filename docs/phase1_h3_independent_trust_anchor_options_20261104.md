# H3: 独立Trust Anchor比較・選定前設計（G6）
作成: 2026-11-04。参照: PR #167、`docs/phase1_way_e_evidence_approval_packages.md`、`docs/phase1_way_e_gate_audit.md`、`specs/p0_01_d5_25_gap_verification_matrix.json`、`AGENTS.md`。

> **比較資料 / NOT_SELECTED / NOT_AUTHORIZED / NOT_EXECUTED。** H1欠落原議の追加探索は本人方針により当面保留するが、`PENDING_ORIGINAL`や安全仕様の本人承認要件を免除しない。G6未解決、G1〜G9全件BLOCKED、PHASE-1 BLOCKED、runtime NO_GO、安全停止ラッチ、実装許可falseを維持。

## 目的・脅威モデル

G6で必要なのは「ローカルWindows管理者がSQLite Journalとローカル基準tip・バックアップを同時に巻き戻しても、**外部の信頼主体に対する不一致が発覚し、安全側に停止できること**」。同時writer、クラッシュ途中、失効済み発行者、旧世代の再使用、承認の巻戻し、Witness不達を含む。

信頼の根はローカル管理者権限、同一PCのTPMだけ、ローカルバックアップ、GitHubリポジトリ、リポジトリ内のハッシュ、単独の署名鍵から**独立**していなければならない。独立とは物理的に別の保管場所だけではなく、**認証資格、更新/削除/復旧の管理権限、発行・失効権限、履歴の保持**に分離と検証可能性があること。クラウドのroot/所有者が両系統を変更できるなら完全独立と呼ばない。

### 分離すべき機能
1. **最新世代Witness**: `(system_id, epoch, sequence, journal_digest, stop_tombstone, issuer_generation)` の最新状態を、同一世代の条件付き更新（CAS）で防御。古い世代・重複・旧署名者・競合writerは拒否。単なるWORMオブジェクト置場はCASを提供しない。
2. **append-only保全証跡**: 各世代の承認・失効・停止の履歴を、管理範囲が分離された耐改ざん・保持期間つき領域に残す。WORMでも保持切れ、アカウント消去、管理権限集中は別途脅威として扱う。
3. **署名/発行者境界**: 許可された発行主体のみCAS更新、署名・鍵の世代と失効墓標を記録。単にクライアント側の固定シークレットを持たせる方式は危険。
4. **リカバリの意思決定**: ローカルSnapshotはWitness最新世代と完全に整合するまで復旧してはならない。不一致・アクセス不明・読み取り鮮度不足・曖昧コミット・長期停止後は**NO_GOを維持**。

## 候補比較（技術成立性は机上評価）
| 候補 | 独立性 / CAS / 永続ログ | 長所 | 致命的な確認点 | 費用・運用 |
| --- | --- | --- | --- | --- |
| A. ローカルSQLite + HMAC/TPM + 外付けバックアップ | **不足** / ローカルCASのみ / ローカル履歴 | 既存Windowsと親和・追加クラウド費用は小さい | ローカル管理者による同時巻戻し、バックアップ差替え、TPM認証状態の巻戻しへの独立証拠にならない | 安価に見えるがG6の独立性を満たさない |
| B. 外部の条件付き更新DB + 別権限WORM保管 | **有力な設計候補** / 可能 / 別系統で保全 | 最新世代CASと監査履歴を役割分担できる。Windowsクライアントがオフラインでもローカル状態はNO_GOに固定可能 | 単独クラウド管理者の削除・資格再発行、CAS成功とWORM書込の二重書込み問題、レイテンシとネット断、鍵失効・二重管理 | 従量課金＋固定/保管費、IAM、監視、保持管理が必要。金額未見積 |
| C. 独立管理の小型Witnessサーバー + 別保管の追記履歴 | **条件付き候補** / 独自実装 / 独自実装 | 管理権限をローカルPCから分離し、専用プロトコルにできる | 自作CAS・認証・耐久・復旧・監査の実装/運用責任が重い。サーバー単体障害、ホスト管理者の巻戻し、鍵共通化に弱い | VPS/専用端末＋保守の固定費が発生、監視/パッチ/バックアップ責任あり |
| D. WORMオブジェクトストレージ単独 | **不十分** / **最新世代CAS未提供** / 履歴保全に有用 | 過去世代の変更/削除を制限可能 | オブジェクトロックは現時点の正しいtipの同時writer裁定、古いクライアントの新オブジェクト発行防止、クラウド権限独立を自動保証しない | 保管/リクエスト/転送費。保持期限・ガバナンス回避権限の選定注意 |
| E. GitHubコミット・外部メール/プッシュ通知 | **不十分** / 非トランザクショナル / 人間の注意喚起 | 既存運用と親和 | 管理者が履歴と運用資格を同時に変更できる可能性、リアルタイム順序・CAS・復旧の証明欠落 | 低導入費だがAnchor代用不可 |

**現時点の設計推奨**: Bを**比較の第一候補**として限定した概念実証計画へ進める。ただし正式採用ではない。具体的な事業者・契約、CAS権限とWORM管理の独立性、費用、操作主体が未確定。A/D/E単独方式をG6充足としない。

### Bの実装例（確定仕様ではない）
- 例1: AWS DynamoDBの条件付き更新で最新世代を裁定し、異なるIAM責任境界のS3 Object Lock Compliance保管で履歴を保持。ただし**同一AWSアカウントの所有者・root権限が双方を管理可能なら独立性の要求を満たすと断言できない**。二つのストア間には原子的な一括トランザクションがない。失敗途中は隔離し再照合までSTOP。
- 例2: Azure Cosmos DBのETag `If-Match` 条件更新 + Azure BlobのバージョンレベルWORM。こちらも権限分離と二重書込み不確定が問題。AzureとAWSの間の費用/運用/アクセス主体は未比較。
- 「ログを書けば常時稼働できる」という設計は禁止。Witnessの強整合な再読取、コミット確認、証跡の保全確認が不明なときは fail closed。

公式仕様の参照（2026-11-04時点で確認。料金・制限・規約は将来再確認）:
- DynamoDB conditional writes: https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/WorkingWithItems.html
- S3 Object Lock（Compliance/Governance、保持期間）: https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock.html
- S3 Governance bypass条件: https://docs.aws.amazon.com/ja_jp/AmazonS3/latest/userguide/object-lock-managing.html
- Cosmos DB ETag OCC: https://learn.microsoft.com/en-us/azure/cosmos-db/database-transactions-optimistic-concurrency
- Azure Blob version-level WORM: https://learn.microsoft.com/en-us/azure/storage/blobs/immutable-version-level-worm-policies

## 試案プロトコル（安全実装ではない）

`LocalJournal.prepare(next_seq, prior_digest, event_digest, latch)` → `Witness.CAS(expected_epoch, expected_seq, expected_digest, next_..., authenticated_issuer)` → `AuditWORM.append(receipt)` → `LocalJournal.finalize` という単純な4段階だけではクラッシュ時の二重書込み曖昧性が残る。したがって運用上は **全段階が一意のreceiptと独立読み取りで検証されるまで、NO_GO**。いずれか不明なら勝手に再試行/上書き/次世代へ進まない。

概念データ最小案（仕様版・schemaは選定後に人間承認）:
```text
system_id / environment_id (口座番号ではない非機密ID)
epoch / seq / predecessor_digest / journal_tip_digest
stop_reasons_digest / tombstone_generation / issuer_generation
request_id (冪等性照会専用)
witness_commit_receipt / witness_observation_version
audit_receipt / audit_retention_policy_ref
```

要検討: WORM先行またはWitness先行、障害時の書込順と二相プロトコル、認証された発行者と失効検証、タイムアウト後の結果不明照会、"新規許可"と"安全停止書込み"の権限分離。安全停止をリモートに記録できない時はローカルFail Closedを優先し、遠隔証跡が欠けたことをもって解除してはならない。

## H3候補に対するFail Closedと負試験

| 脅威/故障 | 拒否/確認原則 | 将来の独立試験 |
| --- | --- | --- |
| ローカルJournalとbackupの同時巻戻し | 外部最新世代と不一致ならNO_GO | 古いSnapshot再ロード→停止継続 |
| 同じexpected_seqの並列writer | 一方のみCAS成功、敗者は隔離 | 独立クライアント2系統の競合 |
| Witness成功・WORM不達（逆も） | 曖昧コミットとしてSTOP、決済/注文実行に直結させない | クラッシュ段階注入とreceipt再照合 |
| Witnessの読取不達/タイムアウト/古いキャッシュ | 成功と扱わずSTOP | 断線・期限切れ応答・遅延応答 |
| Witness権限管理者が旧tipへ更新 | 防御境界自体の破綻。独立監査/別管理主体と失効を要件化 | 管理者脅威試験、失効/警報 |
| 発行者失効、鍵回転、盗難 | 新issuerの昇格は別承認、古い署名は拒否 | 旧鍵/再送/二重昇格の拒否 |
| WORM保持期限切れ/アカウント削除 | 証拠完全性なし、採用不可または隔離 | 期限/削除権限/保持ポリシー監査 |
| 停止墓標の消失・復旧直後 | 独立した停止理由を一つでも失えばNO_GO | 再起動、古い世代、停止理由欠落 |

これらは**試験計画であり未実施**。P1-04故障注入26件・P1-05模擬ブローカー27件も引き続きNOT_EXECUTED。

## 本人のH3方式選定前に残る決定（優先順）
1. **信頼主体**: ローカルPC管理者とは別の所有者/管理資格・別クラウドアカウント・別組織/第三者Witnessなど、何に対する独立性を要求するか。単一個人が両方のrootを保持する場合は残余リスクを明示。
2. **候補選択**: B（CAS + WORM）/ C（独立Witness）/ 不採用。どのベンダー/アカウント構成か。
3. **WORM保持/削除**: 期間、復旧時の照合窓、保存量、保持期間満了とアカウント削除の扱い。
4. **可用性**: WAN断/クラウド障害/課金停止時にNO_GOを維持できる運用制約と復旧責任。
5. **予算**: 受入可能な月額上限、最小従量課金、転送、保管、監視、ログ、SMS/通知、鍵管理の見積条件（価格未見積）。
6. **実施権限**: 実アカウント作成、鍵生成、端末/ネットワーク操作、実OS故障注入・STOP解除は全部別途明示承認。

**方式の推奨と、利用者による方式選定、H4実証の許可、運用/売買開始は別の意思表示。** このPRではいずれも代理承認しない。

## 後続の作業
- オフラインの純粋な状態遷移モデル（WITNESS_UNAVAILABLE / PENDING / COMMITTED / AUDIT_PENDING / CONFLICT / REVOKED / LATCHED）を、個人/クラウドの資格情報なし・発注経路なしで仕様化することは可能。これは安全仕様の未解決パラメータを推測して決めない範囲に限定する。
- 方式選定後、G6-01〜04、G6-08の独立試験計画と、H4専用の破棄可能な環境の故障注入計画を別承認する。
- H1原議探索保留を変更する場合も安全仕様15件の未承認/欠落は保持。
