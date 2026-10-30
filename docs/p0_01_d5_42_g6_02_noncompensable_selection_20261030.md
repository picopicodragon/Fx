# P0-01 D5-42：G6-02 独立Trust Anchor候補の失格条件と人間選定の境界

2026-10-30。D5-41はPR #156マージ済み、本人Windows `Ran 2748 tests in 2.910s` / `OK`、GitHub CI双方成功。

## 本工程の目的と最重要ルール

G6-02のローカルハードウェア保護候補（HW）と独立リモートWitness候補（RW）に対し、**安全必須条件を費用・利便性・見せかけのスコアで相殺させない**失格・選定ポリシーを定義する。これは実装済みのTrust Anchorを審査する仕組みではなく、**全ての独立証拠が未取得のままのオフライン設計**である。これらのテストで仮想`SIMULATED_PASS`を設定しても、実証拠、独立検証、本人承認、選定結果にはならない。

独立性の10条件（D5-40/41）に、**障害復旧とデータ所在の適合性**を追加し、候補ごと12個を安全必須条件とした。残り2条件（検証済みのライフサイクル費用、運用負担）は、実証により全必須条件を満たした候補について初めて比較可能な補助条件とする。費用が安いことだけで失格を取り消せない。安価・高価の架空ケースは円金額・見積り・製品評価を示さない。

## 1. 安全必須12条件（非相殺、2候補で24件）

| 分類 | 必須条件 | 合格のため将来必要な実証 |
|---|---|---|
| 権限分離 | ADMIN_BOUNDARY / WRITE_BOUNDARY / CREDENTIAL_BOUNDARY | 発行者・書込者・保護者・検証者の共通管理者/資格情報を排除した独立確認 |
| 履歴の真正性 | ROLLBACK_RESISTANCE / FRESHNESS_SOURCE | ロールバック・旧データ再生・偽時刻を受け入れない実障害証拠 |
| 鍵・発行者 | REVOCATION_DURABILITY / KEY_ROTATION_AUTHORITY | 失効墓標とissuer/epoch交代の永続/真正性と本人認証 |
| 二重履歴・停止 | SPLIT_BRAIN_DETECTION / STOP_LATCH_CONTINUITY | fork・ネットワーク断・再起動時にSTOPを保持できる独立実証 |
| プライバシー | PRIVACY_NON_EXPOSURE | G2の秘密情報/口座データを外部AnchorやCIへ出さない実測検証 |
| 災害復旧・法令 | FAILURE_RECOVERY / DATA_RESIDENCY | 端末交換/バックアップ復元時に信頼とSTOPを継承し、所在地・契約の要件を満たすこと |

全24行の既定値は`UNVERIFIED`、実際の独立証拠`null`、実人間承認`false`。D5-41の28証拠項目（2候補×14軸）を削除せず、安全必須と補助の責務を分離したものである。**実環境の合格件数は0件**。

## 2. 即時失格とする8つの重大条件（2候補×8＝16ケース）

1. `COMMON_ROOT_OR_ADMIN`：同じ主体がJournalとAnchorを同時変更できる
2. `REPLAY_OR_ROLLBACK_ACCEPTED`：旧履歴/旧epochを最新として受け入れる
3. `REVOCATION_LOSS_ACCEPTED`：失効・墓標を復元や再起動で失う
4. `WITNESS_OUTAGE_REENABLES_TRADING`：独立基準の通信断で新規売買が再開できる
5. `FORK_ACCEPTED_AS_CURRENT`：複数の履歴を同時に正当な最新として扱う
6. `PRIVATE_RECORDS_EXPORTED`：秘密情報・口座/EAのデータを公開/Anchorに混入させる
7. `UNAUTHENTICATED_ISSUER_ACCEPTED`：真正性不明な発行者/鍵交代を受け入れる
8. `CRASH_RECOVERY_UNLATCHES_STOP`：再起動/障害復旧で承認なしにSTOPを解除する

1つでも**実証された場合**は失格候補とし、順位付け・低費用・利便性による例外は不可。今回のテストは`SIMULATED_VIOLATION`を入力した場合に`D542_SYNTHETIC_HARD_KNOCKOUT_NO_SELECTION`を返す動作を確認するだけで、実環境の検出成功は**0件**である。故障実試験も実際には行わない。独立証拠を取得できなかった場合も、合格とはみなさず`NO_GO`にする。

## 3. 選定の6段階レビュー（全て未開始）

| 段階 | レビュー内容 |
|---|---|
| 1 | G2 PRIVATE EVIDENCE保護/機密境界の実装実証 |
| 2 | Anchorの独立管理者・発行権限・出典の検証 |
| 3 | 全12安全必須条件の独立実証と真正性審査 |
| 4 | 全8即時失格条件の障害試験・原本照合 |
| 5 | 必須条件合格後に限る費用/運用負担の比較 |
| 6 | 人間による**別途明示的な設計選定**（G8依存） |

設計選定の本人承認と**運用開始/実取引の本人承認は別物**であり、後者は前者を持って自動発行されない。今回の段階は6つとも`PENDING`、本人署名・根拠`null`、実承認`false`。本PRを人間が手動マージしても、上記の設計選定に同意したという記録にはならない。

## 4. コードと検査の境界

- `specs/p0_01_d5_42_selection_rules.json`：12の非相殺条件、2つの補助比較条件、8の即時失格基準、6段階レビューと全実行権限false。
- `specs/p0_01_d5_42_synthetic_selection_review.json`：2候補×12条件の未検証台帳、2×2補助項目、2×8障害ケース、承認段階6件。実情報は格納しない。
- `scripts/p0_01_d5_42_selection_policy_review.py`：合成障害を**失格→必須不合格→補助比較→仮想合格**の順に審査し、いずれも実選定/権限付与せず停止保持。D5-41以前の拒否安全条件を再検証。
- `tests/test_p0_01_d5_42_selection_policy_review.py`：新規230件。安価候補の不合格、全仮想合格でも不許可、実証済み/承認済み/選定済み偽装、前工程の改ざんを拒否する。
- `specs/p0_01_d5_42_status.json`：G1〜G9未解決、G2/G6実受入0/15、実候補選定0、実Trust Anchor0。
- 本書。

既存2,748件＋新規230件＝**予定2,978件**。GitHub CIのRepository checksとWindows Python 3.13 / IANA time zones、本人Windowsローカルテストを確認し、本人のPR差分レビュー後に手動マージする。全て合成ラベルのインメモリ検査であり、実鍵・実サービス・実口座/MT4・実ネットワーク/OSファイル・実Git秘密スキャン・発注・決済・停止解除は行わない。

## 5. 継続する安全条件

G1〜G9全て`UNRESOLVED`。口座同一性`NOT_RECONCILED`、建玉/未約定注文/EA現状`UNKNOWN`。単一MT4環境、複数同時ログインなし、楽天問い合わせ中止、追加デモB不採用。初期資金10万円、単発0.5%/同時1.0%/日次1.5%、DD4%/5%停止条件、人間承認/NY17:00の日次境界は変更しない。

`PHASE-1 BLOCKED`、`runtime_go_no_go=NO_GO`、`verified_values=null`、`safety_hold_latched=true`、`effective_approved_actions=[]`、`forward_trading_enabled=false`。合成設計・CI・PRのマージによって実世界の実装・受入・運用許可は増えない。
