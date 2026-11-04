# H3-2: 外部CAS Witness + 独立WORMの具体構成・権限・費用評価（設計のみ）
作成日: 2026-11-04。前提: H3比較PR #168マージ済み。**未選定・実契約なし・実環境テストなし**。

## 0. 決定境界
本書はH3の候補B（外部CAS + 別管理のWORM）をAWS/Azureで具体化した**比較資料**であり、AWSの採用・支払・アカウント作成・秘密鍵発行・ネットワーク接続・安全仕様の確定・G6の解除を承認するものではない。欠落原議探索は一時保留するが、FX-SAF-001〜015は未承認。G1〜G9 UNRESOLVED、`PHASE-1=BLOCKED`、`runtime=NO_GO`、`safety_hold_latched=true`、`verified_values=null` を維持。実MT4/EA・注文・停止解除は対象外。

## 1. 具体的な構成案
| 分離機能 | AWS案（設計第一候補） | Azure案（対抗候補） | 合格に必要な独立性 |
| --- | --- | --- | --- |
| 最新tip・世代裁定 | DynamoDB単一リージョンの条件付き `UpdateItem` + `GetItem ConsistentRead=true` | Cosmos DB NoSQLのETag/`If-Match`、必要な整合性レベルを別途確定 | ローカル管理者がtipや条件式を直接上書きできず、issuer権限を限定できる |
| 保全・証跡 | S3 Object Lock **COMPLIANCE** のversioned bucket | Azure Blobのversion-level immutable WORM（locked policy） | Witnessの更新/削除権限とWORM管理権限を分離し、削除/保持短縮/アカウント閉鎖を脅威に含める |
| 発行者認証 | 専用発行者サービス（中継）＋最小権限IAM＋署名検証。鍵管理の候補はKMS等 | 専用中継＋Entra権限＋Key Vault等 | WindowsにWitness CAS更新可能な長期資格情報を置かない。署名主体と復旧/権限管理者を分離 |
| Windows側 | PythonがローカルJournalの停⽌状態を保持。**設計上**中継APIへ固定schemaの認証リクエスト | 同左 | 実通信は未実施。運用マシンからの直接クラウド管理操作は禁止 |
| 監査確認 | 外部のread-only監査者が最新tipと保持済みreceiptを比較 | 同左 | 同一ユーザーがCASと履歴を一括書換え/削除できるなら、独立防御としては不十分 |

**注意**: 同一クラウド内の「2サービス」を使うだけでは独立にならない。少なくとも別アカウント/サブスクリプション、別の管理認証・MFA・復旧経路、監査主体と外部証跡の組合せを審査する。単一個人が全rootを持つ場合の脅威は別途本人に説明する。完全に防げない管理者共謀やアカウント破棄は残余リスク。

### 安全性を左右する二重書込み
DynamoDBとS3、Cosmos DBとBlobには **両サービスを一括原子コミットする汎用トランザクションはない**。Witnessだけ成功、WORMだけ成功、両方不明、遅延/再試行、古い観測を全て区別する必要がある。

実装の設計案: `PREPARED_LOCAL -> WITNESS_COMMIT_UNKNOWN/CONFIRMED -> AUDIT_RECEIPT_UNKNOWN/CONFIRMED -> VERIFIED` とし、**最終的に独立した最新tip・保持receipt・local Journalが突合していない場合は常にNO_GO**。`WITNESS_CONFLICT / ISSUER_REVOKED / TOMBSTONE_MISSING / STALE / AUTH_UNKNOWN` は自動解除なし。タイムアウトは失敗確定ではなく結果不明として保存し、同じrequest_idで照会するまで**盲目的に再送しない**。証拠状態から取引許可フラグを直接導出しない。

### ハード境界
1. ローカル管理者だけでの旧snapshot/tip復元→Witness最新版と一致しなければ拒否。
2. 同世代での2 writer→CASは一方のみ成功。敗者が独自の次世代へ進むことは禁止。
3. 確認できないSTOP墓標、発行者失効、時計/オフライン期間→必ず停止継続。
4. 読取りは古いキャッシュ/最終的整合性ではなく、選択した実装での**保証された最新読取**が必須。DynamoDBの `ConsistentRead=true` は単一リージョンのtable読み取りを想定（Global table他regionを同じ強整合として扱わない）。
5. Witness不達・WORM不達・費用/認証失効→**fail closed**。クラウド障害のためにSTOP解除条件を緩めない。
6. KMS/Key Vault、通知、監査ログ、IAMの実動作とWindows OSクラッシュは別のH4個別承認後に試験する。

## 2. 権限分離・責任分界（具体構成では未確定）

| 役割 | 許す機能 | 禁止・分離すべき権限 |
| --- | --- | --- |
| Windows runtime | 発行者サービスに認証要求、自己のlocal Journalと停止ラッチ保持 | DynamoDB/Cosmos DB管理権限、WORM削除権限、長期root資格情報 |
| Issue service | 限定schemaを検査し、条件付きCASの一意request_idを発行 | WORM保持削除、認証・権限ポリシーの単独変更、停止承認の偽造 |
| WORM writer | 許可済みreceiptのappendのみ | 保持短縮、既存版削除、Witness最新世代の編集 |
| Independent auditor | 最新tip・署名・audit receiptを読取、異常報告 | 発行、消去、STOP解除 |
| Recovery approver (human) | scope/期限/失効を限定した復旧承認の意思表示 | ローカル単独での安全解除、取引許可の暗黙付与 |
| Account/root administrators | 契約・請求と権限構成の管理 | 両系統を単独・無監査で復旧/削除できるならG6独立性の成立を主張しない |

管理者本人、復旧手段、MFA、アカウント停止、課金不能、ログ監査を含むRACIを別途確定する。1人開発で完全な管理主体分離は難しい可能性があるので、**管理者自身の悪意まで防げると偽らない**。

## 3. 費用モデル：金額の断定ではなく測定可能な見積式

**現時点でAWS/Azureの契約リージョン、実際のイベント頻度、課金モード、最低費用、無料枠、通知費用、為替、保管方針が未定**。月額円価格をでっち上げない。公式料金計算機で、適用リージョンを選んだ上で次式を埋める。

| 変数・入力 | 30日あたりの算出 | 注 |
| --- | --- | --- |
| `N` = 永続化イベント/日 | `30N` | 取引注文だけでなく停止理由、revocation、監査を含む。設計値であり運用事実ではない |
| Witness CAS requests | `30N` + conflict/retry / evidence reads | DynamoDBのWRUはアイテムサイズ1KiB単位、強整合RRUは4KiB単位。条件付き更新の失敗時課金も見積 |
| 強整合read requests | 少なくとも `30N` +起動/復旧/定期監査 | 断線中は確認不能でNO_GO |
| audit WORM append | `30N` +異常/復旧追加 | 1イベント1新versionならObject Lockの保持・リクエスト料金を含む |
| audit保存量 (MiB) | `30N * B / 2^20` (`B` = receipt bytes) | 保存期間分だけ蓄積。版数、WORM保持、バージョン管理請求を含む |
| 中継/鍵管理/監視 | 呼出数、常時稼働最小料金、KMS/Key Vault、監視、ログ | トラフィックが少なくても固定費が優勢になり得る |
| 金額合計 | CAS + read + storage + WORM writes + intermediate service + key + logs + network + taxes | コストアラート/請求停止時は新規売買を許可しない |

**説明用ボリューム、保証/予測ではない**:
- 低: `N=10` → 300 append/月
- 中: `N=100` → 3,000 append/月
- 高: `N=1440`（毎分1件）→ 43,200 append/月
- `B=1024 bytes`かつ高ケース・30日分: 43,200KiB ≈ 42.2MiB の**生receipt量のみ**。インデックス/世代履歴/追加コピー/保持期間は別。
- 30日運用ではなく90日保持なら定常蓄積は約3倍（頻度一定時、削除不可期間を考慮）。
- **費用の比較成立条件**: 東京等の同等リージョン、レート/契約日、通貨換算、月ごと/時間ごとの最低請求、DynamoDB on-demandとCosmos serverless/provisionedの違い、WORM保管と監視固定費を同一入力で見積。クラウド料金表は地域、プラン、時期で変わる。後続の人間選定前に公式計算機のスクリーンショット/見積IDを**Git外で**保管する。

公式課金仕様: https://aws.amazon.com/dynamodb/pricing/ 、https://aws.amazon.com/s3/pricing/ 、https://azure.microsoft.com/en-us/pricing/details/cosmos-db/standard-provisioned/ 、https://azure.microsoft.com/en-us/pricing/details/storage/blobs/ 。

## 4. Windows接続と運用制約（未実装）
- Python 3.13/Windowsローカルに置くのは**非特権のクライアント境界**。サービス認証の方式（端末証明書、短期トークンなど）は未選定。GitHub Actions/PRへ資格情報やログ生データを送信しない。
- 通信TLS、サーバー証明書検証、再送の冪等性、単調時計とUTCの別管理、DNS/ネット障害時のNO_GO、監査ログの秘匿化、MFA/権限取り消しを要件化。VPN/プロキシなど実ネットワーク条件はH4以前に観測していない。
- ローカルSQLiteの最終状態だけでWitnessの「成功」を擬装しない。ウォームスタート、Windows再起動・強制終了・途中電源断後はreconciliation成功までNO_GO。
- **権限・状態の分離:** 「本人による方式選定」「サービス設定実施」「H4実証」「G6独立受入」「安全実装仕様本人承認」「PHASE受入」「MT4接続/EA」「注文・STOP解除」を別々に記録する。

## 5. 代替候補と条件付き比較結論
- **AWS（暫定比較第一位）:** DynamoDB条件付Update + 単一リージョン強整合Get、別責任範囲のS3 Object Lock Complianceを採用検討。メリットはCAS/強整合の仕様が明確、immutable保持仕様が明記。デメリットはIAM/root権限分離、2系統の原子的コミット不能、AWSアカウント削除・請求・事業者依存。
- **Azure（対抗）:** Cosmos DB ETag OCC（HTTP 412で競合）、version-level immutable Blobを検討。デメリットは選択整合性/料金モード/条件付更新時の一貫性の検証、アカウント管理の独立性。
- **見送り**: ローカルTPM+バックアップ単独、GitHub、S3/Blob WORM単独を最新tipの独立CASとして扱わない。
- **採用ではない**: AWSの第一候補は机上比較に過ぎない。アカウント管理者分離を十分に満たせないなら実装しない選択肢も残す。

### 公式一次資料
1. DynamoDB 条件式: https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Expressions.html
2. DynamoDB read consistency: https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/HowItWorks.ReadConsistency.html
3. S3 Object Lock: https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock.html
4. Azure Cosmos DB ETag: https://learn.microsoft.com/en-us/azure/cosmos-db/database-transactions-optimistic-concurrency
5. Azure version-level WORM: https://learn.microsoft.com/en-us/azure/storage/blobs/immutable-version-level-worm-policies

## 6. 次のH3本人判断と検査
**必要な選定**: (a) AWS vs Azure vs 再設計、(b) 実アカウント管理主体（root/IAM/KMS/WORMの独立管理が成立するか）、(c) 保持期間と削除ポリシー、(d) 1日当たりのイベント量と月額許容上限、(e) 停止中の監査と復旧体制、(f) 実証の隔離環境/予算。

**未実施**: クラウド作成、鍵生成、Windowsアプリ接続、CAS/WORM実障害試験、H4、G6実証、P1-04の26件・P1-05の27件。文書/CI成功のみでG6をTESTED/RESOLVEDにしない。

**方式Eの続工程として自律的に可能**: 資格情報と外部接続が一切ない模擬状態遷移の拒否試験、コスト算定テンプレート、役割/権限の機械的境界テスト。ただし未承認の安全仕様数値を固定しない。必ずCodexを含むPR・CI・本人マージで扱う。
