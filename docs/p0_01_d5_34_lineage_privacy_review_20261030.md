# P0-01 D5-34：G6証拠世代・発行主体の整合性とG2公開境界の合成監査

作成日：2026-10-30。前工程D5-33はPR #148マージ済み、本人Windows 1,567件OK、GitHub CI成功。

## 目的と非実行境界

G6の5系統の将来証拠源について、**新しく見える証拠でも世代の巻戻しがある場合、取消し記録だけ先行/遅延する場合、発行主体・鍵世代が切り替わった場合**の拒否条件を設計する。G2の公開・非公開境界を引き継ぎ、公開用JSONに機密情報が混入したり、実Git書込みを要求したりする申告を拒否する。

**すべて純粋関数・架空JSONのみ。** 実MT4/楽天口座の起動・ログイン・照会、EA/EX4、注文・決済、Windowsの実ファイルI/O・実時計、暗号署名・鍵管理、実Gitフック・秘密情報スキャン、独立Trust Anchorを一切動作させない。G1〜G9は全件`UNRESOLVED`、`PHASE-1 BLOCKED`、`runtime NO_GO`を維持する。

## G2：公開/非公開の厳格な境界

D5-31〜33で決めた、公開用メタデータの固定5フィールド・正規JSON形式を変えない。本工程では`public_export`という**合成申告**を追加し、以下を強制的に拒否する。

- `private_payload_attached=true`：非公開の証拠本文・ログ・口座情報を添付した申告。
- `private_export_requested=true`：非公開証拠の公開要求。
- `git_write_requested=true`：本工程の範囲外のGit書込み/実公開要求。なおPR作成のための設計文書・合成テストの通常Gitコミットとは無関係。
- `real_redaction_verified=true`：実ファイル全体を走査・マスキング済みとする偽申告。
- D5-33の公開JSONとD5-34の公開JSONが不一致、JSONに任意の追加フィールド・ネスト・時刻・秘密情報がある、非公開参照ラベルの型が不正。

実際には機密データの取得・安全な保存・GitHubへの転記・漏えい検査は行わない。合成プライベート参照ラベルは機密情報ではなく、独立した本物の証拠保管庫の存在も示さない。**本工程の許可フィールド検査は実Gitフックではない。**

## G6：世代・取消し・発行主体を比較する3つの合成役割

D5-33の5証拠源（ローカル履歴・独立基準点・取消しレジスタ・署名鍵検証・単調時計）を引き継ぎ、そのうち**順序管理の3役割**として`journal`、`anchor`、`revocation`を分離する。各役割が持つ情報は、架空の`generation`、`sequence`、`observed_tick`、`issuer_id`、`issuer_epoch`、`stop_latched`、`revocation_tombstone`。

| 合成状況 | 判定 | 留意点 |
|---|---|---|
| AnchorがJournalの世代/連番より古い | `D534_G6_ANCHOR_BEHIND_NO_GO` | Anchorの観測tickが新しくても拒否 |
| AnchorがJournalより先行 | `D534_G6_ANCHOR_AHEAD_NO_GO` | 保存と外部基準の原子性は未実証 |
| 取消しレジスタだけ先行 | `D534_G6_REVOCATION_AHEAD_NO_GO` | 先行記録を不当に確定扱いしない |
| 取消しレジスタが遅延 | `D534_G6_REVOCATION_BEHIND_NO_GO` | 消失または復元巻戻しの可能性 |
| いずれかの停止ラッチまたは取消し墓標が消失 | `D534_G6_STOP_OR_REVOCATION_LOST_NO_GO` | STOP保持 |
| 発行者ID/世代が共有履歴と食い違う、発行主体変更を申告する | `D534_G6_ISSUER_HANDOFF_UNVERIFIED_NO_GO` | 将来の独立認証・ローテーション手続が必要 |
| 合成tickが古い・未来 | `D534_G6_SYNTHETIC_STALE_OR_FUTURE_NO_GO` | 合成5tickは実時間制限ではない |
| D5-33の基準証拠と世代/連番/観測tickが不一致 | `D534_G6_PREDECESSOR_WITNESS_MISMATCH_NO_GO` | 入力間の整合検査のみ |
| すべて架空の入力上で整合 | `D534_SYNTHETIC_LINEAGE_COHERENT_NEVER_AUTHORIZED` | 実認証でもGOでもない |

発行主体のIDや世代が全て同時に別の架空ラベルへ置換された場合、元の本物の発行者を認証できないため、見かけ上の整合が成立しても**NO_GOのまま**である。発行主体の交代（ローテーション）が必要な場合は、将来、独立した本人認証/鍵失効/世代切替/取消し履歴の継承に関する別仕様・実装・個別承認が必要。

### 不可欠な信頼境界

この検査は5系統の証拠自体が本当に独立していることを認証しない。同一の攻撃者や同一の未信頼入力から、元Journal・Anchor・Revocation・全参照ハッシュ・世代の値を**同時に偽造**されれば、相互一致だけで検出できない。合成tickの鮮度は暗号検証/単調時計/UTCの実時刻を証明しない。署名・鍵・独立基準・原子的保存・取消し耐久性・実クラッシュ回復はいずれも**未実装・未検証**。

## 実装とQA

- `scripts/p0_01_d5_34_lineage_privacy.py`：D5-33の安全な拒否を確認してからG2/G6を検査する純粋関数`review_d534_lineage`。
- `specs/p0_01_d5_34_lineage_contract.json`：3役割、合成tick制限、発行者変更の扱い、実承認不可を固定。
- `specs/p0_01_d5_34_synthetic_fixture.json`：すべて架空の公開情報・発行者ラベル・世代値。
- `tests/test_p0_01_d5_34_lineage_privacy.py`：新規93件（明示69件＋3役割×8異常の24件）。
- `specs/p0_01_d5_34_status.json`：未承認・未実証・全ゲート未解決状態。

合計想定は**既存1,567件＋新規93件＝1,660件**。新規コードは実口座・OSやGitHubへのアクセス権を持たない。

## 完了条件と継続制約

GitHub Repository checks と Windows Python 3.13 / IANA time zones CIの双方、および本人Windowsのユニットテスト1,660件の成功が必要。その後、本人の差分目視を経て本人がPRを手動マージする。マージ/CI成功はMT4やブローカーの実運用・EA/EX4・発注・停止解除の許可ではない。

D5-17旧/新報告の口座同一性は`NOT_RECONCILED`、現在の建玉・未約定注文・EAは`UNKNOWN`、旧報告に存在しない観測時刻を推定しない。単一MT4環境・複数同時ログインなし、楽天への問い合わせ中止、別デモB不採用、既存の口座純資産連動リスク上限とDD停止条件、NY17日次境界は変更しない。全検査結果で`safety_hold_latched=true`、`phase_1=BLOCKED`、`runtime_go_no_go=NO_GO`、`verified_values=null`を維持する。
