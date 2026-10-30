# P0-01 D5-35：G6発行主体の交代・鍵失効・世代継承の受入要件とG2公開境界

作成日：2026-10-30。D5-34 PR #149 はマージ済み、本人Windows 1,660件OK、GitHub CI成功。

## 工程の範囲

**設計と完全合成のオフライン検証のみ。** 楽天口座やMT4/EA/EX4の起動・ログイン・照会、発注、注文取消し、実ストレージ書込み、OS時計、独立Trust Anchor、実署名/鍵操作、実Gitフック/秘密スキャン、通知送信は行っていない。将来の個別承認が必要な操作を、この工程やPRマージによって承認したことにはならない。

## G6：鍵ライフサイクルと発行者交代

D5-33の5系統の合成証拠、D5-34のJournal/Anchor/Revocationの3役割を引き継ぎ、`transition`に前後の発行者名、発行者epoch、世代、連番、鍵状態、取消し墓標、停止ラッチを格納する。名前は `SYNTHETIC_ISSUER_...` に限定。鍵そのもの・公開鍵・署名・実口座識別子は格納しない。

| 合成申告 | 判定 |
|---|---|
| 前工程の発行者/epoch/世代/連番と不一致 | `D535_G6_PREDECESSOR_SCOPE_MISMATCH_NO_GO` |
| 次世代・連番が過去へ戻る | `D535_G6_EPOCH_OR_SEQUENCE_ROLLBACK_NO_GO` |
| 発行者交代イベント`ROTATION` | `D535_G6_UNVERIFIED_ISSUER_ROTATION_NO_GO` |
| 鍵失効/緊急停止イベント | `D535_G6_REVOCATION_EVENT_UNVERIFIED_NO_GO` |
| 無申告の発行者/epoch変更 | `D535_G6_UNDECLARED_ISSUER_CHANGE_NO_GO` |
| 鍵状態が有効/失効済みと主張 | `D535_G6_PRIOR_KEY_STATE_UNTRUSTED_NO_GO` または `D535_G6_KEY_STATE_CHANGE_UNVERIFIED_NO_GO` |
| 独立参照基準に裏付けられない世代/連番前進 | `D535_G6_UNPINNED_LINEAGE_ADVANCE_NO_GO` |
| 取消し墓標の消失 | `D535_G6_REVOCATION_ERASURE_NO_GO` |
| 停止ラッチ解除の主張 | `D535_G6_STOP_LATCH_LOST_NO_GO` |
| 本物の独立証明、署名・鍵、epoch固定、本人承認を偽申告 | `D535_G6_FALSE_REAL_PROOF_CLAIM_NO_GO` |
| 全て合成形式上整合 | `D535_SYNTHETIC_LIFECYCLE_COHERENT_NEVER_AUTHORIZED` |

**重要な意味上の区別**：この工程は有効な鍵・失効済み鍵を実際に識別するものではない。既定状態は`SYNTHETIC_UNVERIFIED`であり、見かけ上の鍵ローテーション成功を生成しない。将来の真正な交代には、旧鍵の取消し証拠、新鍵の独立本人認証、外部に保護されたepoch基準、鍵保管/失効ポリシー、クラッシュ時の移行中断と復旧、本人の個別承認が要る。合成レコードを同一の主体が全て書き換えられる限り、全値一致は真正性を証明できない。

## G2：3つの公開用面を横断監査

`DESIGN_RECORD`、`STATUS_SUMMARY`、`REVIEW_SUMMARY`の3つの**架空の公開用面**へD5-31/32以来の正規JSON固定5フィールドを適用する。いずれかの面に非公開ペイロードや追加の機密フィールドを添付、非公開の公開を申告、実スキャン済みを偽申告、D5-33/34の公開値と不一致のケースを拒否する。

**この3面は実GitHub PR本文やログのスキャンではない。** 未来の書込み経路やシークレットスキャンは未実装。現実のプライバシー保護が技術的に強制されたとは証明できない。G2の実口座同一性は`NOT_RECONCILED`、現建玉・未約定注文・EAは`UNKNOWN`。過去の`EV-OLD`と後の`EV-NEW`の時点/口座同一性も不明であり、実証されたデータに昇格しない。

## 実装の検査連鎖

`review_d535_handoff(contract, d534_contract, d533_contract, d532_contract, d531_contract, old_evidence, gap_matrix, d532_fixture, d533_case, d534_case, synthetic_case)` はD5-34の拒否専用ゲートを再実行し、下位ゲートの全安全フラグが`false`であることを確認してからG2/G6を検査する。前段の不一致や偽の`GO`・ブローカー認証申告も拒否する。

追加6ファイル：`scripts/p0_01_d5_35_handoff_review.py`、`specs/p0_01_d5_35_handoff_contract.json`、`specs/p0_01_d5_35_synthetic_fixture.json`、`tests/test_p0_01_d5_35_handoff_review.py`、`specs/p0_01_d5_35_status.json`、本書。**既存1,660件＋新規87件＝想定1,747件**。

すべての返値は`phase_1=BLOCKED`、`runtime_go_no_go=NO_GO`、`verified_values=null`、`safety_hold_latched=true`、`effective_approved_actions=[]`。G1〜G9は全件`UNRESOLVED`、実運用許可・停止解除不可。

## 未解決の実装・実証要件

| 順序候補 | 実装・実証すべきもの | 現在の扱い |
|---|---|---|
| 1 | G2実口座/端末/建玉/未約定注文/EAの証拠収集・口座同一性（個別閲覧承認、出典・観測時刻、機密保護） | **未実施** |
| 2 | G2公開可能メタデータの実強制境界、Gitフック/CI秘密スキャン、機密保護ストレージ/権限/削除手順 | **未実装** |
| 3 | G6独立アンカーの所有者・信頼根・認証方式の選定。合成参照と隔離した不可逆/単調な世代保証 | **未選定・未実証** |
| 4 | G6鍵保管・署名検証・鍵失効と発行主体交代。旧鍵取消しと新鍵継承の原子的な境界/停止保持 | **未実装** |
| 5 | G6真正の追記・取消し墓標、書込み主体fence、fsync/atomic replace等を含む実ストレージ機構 | **未実装** |
| 6 | 単調時計の再起動境界、独立基準点とローカル保存の不一致を含む隔離実クラッシュ試験 | **未実証** |
| 7 | 上記の個別承認、監査可能な証拠と、G1〜G9各ゲートの別途受入 | **全件未解決** |

**どの項目も本PRで実行・認可しない。** 現状の合成テスト追加だけでは、実際のG2/G6阻害要因は解消しない。

## 継続する運用前提と受入

単一MT4環境、複数同時ログイン禁止、楽天への問い合わせ中止、別デモB不採用を維持。損失上限0.5%/1.0%/日次1.5%、DDの段階停止・5%強制停止、NY17日次境界などの既存ルールは変更しない。

- [ ] GitHub Repository checksとWindows Python 3.13 / IANA time zones CI成功。
- [ ] 本人Windowsの全1,747件成功。
- [ ] PR差分を本人が目視し、本人が手動マージ。テスト/マージは実機・本番運用の許可ではない。
