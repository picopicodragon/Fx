# P0-01 D5-36：G2/G6実装準備・受入条件・個別承認の分離

作成日：2026-10-30。前工程D5-35はPR #150マージ済み、本人Windows `Ran 1747 tests in 1.286s` / `OK`、GitHub CI成功。

## 1. 工程の目的と判断

D5-27〜35までの合成拒否検査を積み重ねた結果、G2とG6の実環境上の未解決事項は**合成テストの件数を増やしただけでは解消しない**ことが明確になった。D5-36は、今後どの成果物があれば実装に進めるかを、人間が判断できる**15件の具体的受入基準**として整理する。本工程で実現したのは受入条件の仕様化と虚偽の実証・承認昇格を防ぐオフライン検査であり、各基準の実装・受入ではない。

全15基準は`implementation_state=NOT_IMPLEMENTED`、`real_evidence_state=NOT_COLLECTED`、`human_approval_state=NOT_GRANTED`、`acceptance_state=BLOCKED`。これらを外部データなしに更新することは許されない。ユーザーの明示承認を要する将来の行為を、設計書・GitHub PR・成功したCIが代替することはない。

## 2. G2：実口座状態と機密保護の受入基準（7件）

| ID | 必要な受入証拠・将来の検証内容 | 操作区分 | 情報の扱い |
|---|---|---|---|
| G2-01 | 実際の単一MT4端末、口座・サーバー・デモ環境の識別、旧EV-OLDとEV-NEWの対象スコープ照合 | 将来の限定読取 | 非公開 |
| G2-02 | 口座セッションとサーバー識別の整合。接続画面の表示を真正な業者照合と誤認しない | 将来の限定読取 | 非公開 |
| G2-03 | 装着EA、AutoTrading表示、MACD Sample等の状態を取得時刻・対象端末とともに確認 | 将来の明示承認済み目視 | 非公開 |
| G2-04 | 建玉と未約定注文の有無を同一口座・同時点で照合。過去の申告から現在値を推定しない | 将来の限定読取 | 非公開 |
| G2-05 | 出典・観測時刻・真正性・時計境界の照合。G7の時計・再起動条件にも依存 | 将来の限定読取 | 非公開 |
| G2-06 | 機密保管先の権限、暗号化、保存期限、削除、事故時の手順を実装・別途監査 | 将来のOS保存操作 | 非公開 |
| G2-07 | 実際の公開経路に固定5項目allowlist・CI/Gitフックの秘密情報スキャンを適用し、機密混入の遮断を検証。G8にも依存 | 将来のOS/Git操作 | 公開可の合成メタデータのみ |

実証する前提：単一MT4環境、複数環境・別ログインの同時運用なし。楽天へのメール問い合わせなし、独立デモB不採用。現在の口座同一性は`NOT_RECONCILED`。現在の建玉/未約定注文/EAは`UNKNOWN`。実口座番号・スクリーンショット・生ログ・秘密鍵はGitへ置かない。公開可能な合成設計用メタデータも実Gitフックで保護済みとは主張しない。

## 3. G6：独立証拠・実永続化・復旧の受入基準（8件）

| ID | 必要な受入証拠・将来の検証内容 | 操作区分 | 先行要件 |
|---|---|---|---|
| G6-01 | 独立信頼根の所有者、発行権限、改ざん・同時偽造・復旧時の脅威モデルを人間が承認 | 将来の設計レビュー | なし |
| G6-02 | 真正の独立Trust Anchor、保護された世代番号、異なる権限境界の証明 | 将来の外部証明 | G6-01 |
| G6-03 | 実署名/鍵管理、旧鍵失効・新鍵への交代、リプレイ対策、G8本人承認の証拠 | 将来の外部証明 | G6-01/02・G8 |
| G6-04 | 実追記ジャーナル、取消し墓標の永続性・権限、機密・破損検査 | 将来のOS保存操作 | G6-01 |
| G6-05 | 単一書込み主体、排他とフェンス、二重書込み・クラッシュ時の封じ込め | 将来のOS保存操作 | G6-04 |
| G6-06 | 実ストレージのflush/fsync相当の保証、アンカー/ローカル境界の整合、途中電源断・復旧拒否 | 将来の隔離OS障害試験 | G6-02/04/05 |
| G6-07 | Windows単調時計、再起動・補正・DST・UTC記録、経過時間計測の証拠とG7条件 | 将来の隔離OS試験 | G6-06・G7 |
| G6-08 | 失効・承認・復旧の署名付き証跡、拒否と承認解除の分離、G8の個別承認 | 将来の外部証明 | G6-03/06/07・G8 |

**G6のトラスト境界の要点：** D5-30〜35のラベル・epoch・合成tick・ハッシュが5つ整合しても、同じ未信頼主体に全体を同時偽造されれば真正な独立証明にはならない。独立Trust Anchor、鍵失効、単調な外部基準、書込み耐久、実復元・クラッシュ時の停止保持は**未実装・未実証**。G2/G6の両方が将来実証されても、G1・G3〜G5・G7〜G9など他ゲートの受入を飛び越すことはできない。

## 4. 承認と受入の区分

- **設計・要件のレビュー（現在可）**：GitHub上の合成仕様・コード・単体テストの確認。実口座情報の閲覧・保存・署名・実環境操作の承認ではない。
- **将来の限定閲覧・機密証拠収集**：行為、対象口座/端末、閲覧範囲、収集対象、保管先、実施者、有効期限、取消しを特定した別のユーザー明示承認が必要。今回の`D536_NO_ACTION_REQUEST`は全12操作フラグ`false`。
- **将来のOS保存、独立アンカー、鍵、障害試験**：隔離環境・最小権限・人間承認・停止保持を別途設計し、先行要件を受入確認した後に個別許可。アーキテクチャ図や単体テストだけでは証明にならない。
- **モジュール/フェーズ受入と取引実行**：Q110のTASK/MODULE/PHASEを混同しない。現状`PHASE-1 BLOCKED`で本番・デモ自動売買、EA/EX4起動、停止解除を許可しない。実装・実証と人間承認がすべて揃うまで`runtime NO_GO`。

## 5. オフライン監査関数とテスト

`review_d536_readiness(contract, readiness, action_claims, predecessor_bundle)`は全入力を未信頼として読み、固定15件のID/順序/依存関係/情報区分/将来の操作区分を厳密に照合する。受入台帳の**単一行**でも`IMPLEMENTED`、`VERIFIED`、`GRANTED`、`ACCEPTED`などに書き換えられたら拒否する。12種の個別承認もすべて`false`が必須。前工程D5-35までの拒否系を再実行し、`NO_GO`、`safety_hold_latched=true`、`broker_verified=false`等を再照合する。例外時も拒否する。

実装：`scripts/p0_01_d5_36_readiness_gate.py`、`specs/p0_01_d5_36_acceptance_contract.json`、`specs/p0_01_d5_36_readiness_register.json`、`specs/p0_01_d5_36_synthetic_authorization.json`、`tests/test_p0_01_d5_36_readiness_gate.py`、`specs/p0_01_d5_36_status.json`、本書。

- 既存1,747件＋新規123件＝**想定全1,870件**。新規テストは、15基準×4種類の虚偽昇格60件、12操作の無断承認12件、契約/ギャップ/下位ゲート/形式・非I/Oの検証を含む。
- 判定コード：`D536_CONTRACT_REJECTED_FAIL_CLOSED`、`D536_READINESS_REGISTER_REJECTED_FAIL_CLOSED`、`D536_FALSE_REAL_READINESS_CLAIM_NO_GO`、`D536_ACTION_SCHEMA_REJECTED_FAIL_CLOSED`、`D536_UNAUTHORIZED_ACTION_CLAIM_NO_GO`、`D536_PREDECESSOR_BUNDLE_REJECTED_FAIL_CLOSED`、`D536_PREDECESSOR_SAFETY_INVARIANT_FAIL_CLOSED`、`D536_PREDECESSOR_NOT_COHERENT_NO_GO`、`D536_DESIGN_CRITERIA_DOCUMENTED_REAL_ACCEPTANCE_BLOCKED`、`D536_INPUT_EXCEPTION_FAIL_CLOSED`。
- 「DESIGN_CRITERIA_DOCUMENTED」は**設計レコードの整合のみ**。実際の15基準の受入完了件数は常に0、`effective_approved_actions=[]`。

## 6. PRレビューと安全条件

GitHubのPR本文には「関連仕様ID」「テスト結果」「本人確認」の見出しを設ける。Repository checksとWindows Python 3.13 / IANA time zones CI、本人Windowsの全1,870件成功を確認し、本人が差分を目視して**手動マージ**する。マージは人間の実行承認ではない。

G1〜G9全件`UNRESOLVED`、`phase_1=BLOCKED`、`runtime_go_no_go=NO_GO`、`verified_values=null`、`safety_hold_latched=true`。以前のリスク上限（単発0.5%・同時1.0%・日次1.5%、DD4%停止・5%強制停止）、ニューヨーク17:00日次境界・人間承認条件は変更しない。
