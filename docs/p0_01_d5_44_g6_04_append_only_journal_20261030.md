# P0-01 D5-44：G6-04追記専用Journal・失効墓標・履歴改ざん検出の安全設計

2026-10-30。D5-43はPR #158マージ済み、本人Windows `Ran 3188 tests in 4.022s` / `OK`、CI両ジョブ成功。

## 目的・実施していないこと

G6-04「APPEND_ONLY_JOURNAL_TOMBSTONES」の**将来受入条件と合成の欠損・改ざん拒否ロジック**を定義した。実ホストや独立Trust AnchorでのJournal追記/保管/削除防御、ハッシュ計算/実鍵署名、外部で固定されたGenesis/tip、真の失効墓標、実OSファイル/ネットワーク/MT4アクセスは行っていない。純粋関数のPythonコードが読むのは呼出し元から渡された辞書だけである。

**特に重要：架空のTAG_DESIGN_01などは暗号学的ハッシュでない。** この合成データの厳密一致が「真の任意長履歴に対する改ざん検出能力」「外部独立性」「原子的耐久性」を証明することはない。ローカル側のJournalも検証ラベルも同一主体が書換え可能なら、双方の同時偽造・履歴全体の巻戻しを原理的に排除できない。G6-02独立Anchor未実装のため実世界のHistoryはUNKNOWN扱いのまま。

## 12の保護要件

| 識別名 | 将来の実受入に必要な独立証明 |
|---|---|
| APPEND_ONLY_HISTORY | 既存レコードの上書き・削除・差込みを拒否できる実保存/監査 |
| TOTAL_SEQUENCE | 欠番・重複・順序変化・巻戻し時の連番の一意性 |
| PREDECESSOR_BINDING | 署名または適切な暗号学的参照により直前レコードとの関係が認証できること |
| GENESIS_IDENTITY | 独立して認証・固定されたGenesisの真正性 |
| INDEPENDENT_TIP_COMPARISON | 別の管理/保存/権限境界に固定されたtipの真正性と鮮度 |
| TOMBSTONE_NON_ERASURE | 鍵・issuerの失効墓標が再起動/復旧/差戻しを生き残ること |
| SINGLE_WRITER_COMPATIBILITY | G6-05単一writer/epochフェンスの実証が必要 |
| ATOMIC_PERSISTENCE_COMPATIBILITY | G6-06原子的Journal・Anchorコミット/障害復旧の実証 |
| RESTART_ROLLBACK_DEFENSE | 再起動・OS復元後の履歴と停止ラッチ連続性 |
| PRIVATE_CONTENT_SEPARATION | G2機密情報、口座、生ログ、鍵が公開面/Anchorに漏れないこと |
| ISSUER_EPOCH_AUTHORITY | G6-03で設計した鍵・issuer・epochの独立認証 |
| NO_STOP_RELEASE_ON_GAP | 欠測/不整合があれば取引/STOP解除を拒否すること |

G6-04の直接の前提はG6-01。G6-03、G6-05、G6-06、G2-06、G2-07は将来統合すべき境界として設計に明記する。依存関係そのものをG6-03/05/06の実装受入に昇格してはいない。

## 合成Journalの12のイベントラベル

`GENESIS`、`ISSUER_REGISTER`、`WRITER_FENCE`、`JOURNAL_COMMIT`、`KEY_ROTATION_PREPARE`、`KEY_ROTATION_COMMIT`、`KEY_REVOKE_TOMBSTONE`、`ISSUER_REVOKE_TOMBSTONE`、`STOP_LATCH`、`RESTART_CHECKPOINT`、`AUDIT_MARKER`、`HANDOFF_REJECTED`。

各合成レコードは連番1〜12、架空previous_tag/entry_tag、架空issuer/epochラベルのみ。実payload/署名/タイムスタンプはnull、`real_persisted=false`、`real_witness_verified=false`。実保存パスはnull、外部に固定したGenesis/tipもnull。実証拠・秘密情報・実口座IDは格納しない。

## 14の脅威・攻撃ケース

| カテゴリー | 脅威 |
|---|---|
| 欠損・順序 | RECORD_DELETION / PREFIX_TRUNCATION / RECORD_REORDER / RECORD_DUPLICATE / SEQUENCE_GAP |
| 参照改ざん | PREVIOUS_LINK_REBIND / GENESIS_REWRITE |
| 失効消失 | KEY_TOMBSTONE_LOSS / ISSUER_TOMBSTONE_LOSS |
| 同時偽造・障害 | FORKED_TIP / PARTIAL_CRASH_WRITE / RESTART_ROLLBACK |
| 機密・排他 | PRIVATE_DATA_EGRESS / FENCE_EPOCH_BYPASS |

失効墓標を含むレコードを上書き・削除しても「旧鍵・旧issuerが再び使用可能」とは判定しない。今回は固定合成フィクスチャの変化を拒否する検査だけを行う。`SIMULATED_ATTACK`は`D544_SYNTHETIC_JOURNAL_ATTACK_DENIED_NO_GO`、`SIMULATED_MITIGATED`も`D544_SIMULATED_MITIGATION_NOT_REAL_PROOF`。実故障注入・独立検証・ストレージ破壊/復旧テストは**0件**。

## ファイルと品質条件

- `specs/p0_01_d5_44_journal_contract.json`：12保護条件、12イベントID、14脅威、将来のG6/G2依存、実I/O権限すべてfalse。
- `specs/p0_01_d5_44_synthetic_journal.json`：12の架空Journalレコードと14脅威。実ファイル/証拠/秘密鍵/署名/Genesis/tipなし。
- `scripts/p0_01_d5_44_journal_review.py`：レコード削除/重複/順序/リンク・欠損/失効墓標の偽申告を厳格に否認。D5-43以前の全拒否安全条件を再検証。実OS I/Oなし。
- `tests/test_p0_01_d5_44_journal_review.py`：**新規163件**。14脅威×2の合成攻撃/緩和、12レコード×5の偽実証/参照改ざん、11実契約権限の偽承認、7実操作偽装、前段/スキーマ改変の追加テスト。
- `specs/p0_01_d5_44_status.json`：全実操作0、G2/G6受入0/15、全ゲート停止。
- 本書。

既存3,188件＋新規163件＝**予定3,351件**。PRのGitHub Repository checksとWindows Python 3.13/IANA time zones CI、本人Windowsローカルの全3,351件と差分目視後、本人が手動マージする。CIやGitのマージは実ストレージ導入/証拠保存・人間の実運用承認ではない。

## 安全条件

G1〜G9全件UNRESOLVED、PHASE-1 BLOCKED、runtime NO_GO、verified_values=null、safety_hold_latched=true。G2/G6実受入0/15、実作業0/15、実Journal 0件、実墓標認証0件、独立Anchor0件。口座同一性NOT_RECONCILED、現建玉/未約定注文/EAはUNKNOWN。単一楽天デモMT4環境、複数同時ログイン禁止、追加デモB不採用、楽天メール問い合わせ中止。単発0.5%/同時1%/日次1.5%、DD4%/5%の停止・承認、NY17:00の取引日境界は変更しない。実MT4/EA/EX4、実鍵/OS/ネットワーク/独立Anchor、証拠収集、売買・決済、停止解除は未承認・未実施。
