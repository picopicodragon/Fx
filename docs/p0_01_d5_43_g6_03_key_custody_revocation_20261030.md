# P0-01 D5-43：G6-03 鍵の保管・ローテーション・失効と発行者交代の安全設計

2026-10-30。D5-42 PR #157は本人Windows `Ran 2978 tests in 3.515s` / `OK`、GitHub CI両ジョブ成功、マージ済み。

## 範囲と厳密な禁止境界

本工程はG6-03「KEY_CUSTODY_ROTATION_REVOCATION」の**設計要件と合成監査のみ**。D5-36におけるG6-03の先行条件はG6-01/G6-02、外部依存G8である。G2-06機密保護・G2-07公開境界の未実装も維持する。

**実鍵の生成/保管/失効、暗号ライブラリによる署名/検証、外部Witness/TPMとの接続、ホストI/O、Git秘密情報監査、楽天MT4/EA/EX4起動、注文/決済、停止解除は一切行わない。** GitHubに追加するのはスキーマ、合成ラベル、インメモリ検証コード、架空のテストだけ。将来の秘密情報を置くパス、実運用主体、署名値、実証拠、実UTC観測値は記録しない。

## 1. 鍵保管/失効/発行者交代の12必須要件

| 設計必須条件 | 将来の独立証明 |
|---|---|
| CUSTODIAN_ISOLATION | 鍵の管理者と承認者を同一支配にしない |
| NON_EXPORTABILITY | 秘密鍵をGit、ログ、Anchorに混入させない実保護 |
| ISSUER_AUTHENTICATION | 発行者の真正性を別経路から検証 |
| EPOCH_MONOTONICITY | 過去epochの再生・履歴分岐を拒否 |
| REVOCATION_TOMBSTONE | 失効・墓標を独立保存し改ざん耐性を実証 |
| RESTART_REVOCATION_MEMORY | 再起動・OS復旧後も失効状態を維持 |
| REPLAY_PREVENTION | 旧署名、再利用鍵/nonce、過去承認の再利用を拒否 |
| ATOMIC_HANDOVER | 旧/新issuer、journal、Anchorの不整合な部分コミットを拒否 |
| INDEPENDENT_ROTATION_APPROVAL | 本人承認と外部独立権限を別の証拠で確認 |
| APPROVAL_EXPIRY_AND_SCOPE | 承認の有効範囲、期限、失効と再利用防止 |
| EMERGENCY_STOP_LATCH | 失効事故・鍵事故でSTOPを解除させない |
| PRIVATE_EVIDENCE_SEPARATION | 秘密鍵/口座情報/生ログを公開用メタデータに含めない |

12件すべて`REQUIREMENT_ONLY`、`real_evidence=null`、`real_attestation_verified=false`、`human_signoff=false`。

## 2. 合成ライフサイクル10経路

`NO_CHANGE`、`ROTATION_PREPARE`、`ROTATION_COMMIT`、`KEY_REVOCATION`、`ISSUER_REVOCATION`、`EMERGENCY_FREEZE`、`RESTART_RECONCILE`、`OLD_KEY_REPLAY`、`TOMBSTONE_ROLLBACK`、`UNAPPROVED_ISSUER_REBIND`。

固定の架空ラベル`SYNTHETIC_ISSUER_ALPHA`／`SYNTHETIC_ISSUER_BETA`、epoch 1→2、`SYNTHETIC_KEY_ALPHA`／`SYNTHETIC_KEY_BETA`は**鍵でも実署名でもない**。アプリが使える秘密情報や公開鍵材料は生成しない。架空の`SIMULATED_SAFE_PATH`でも結果は`D543_SYNTHETIC_SAFE_PATH_NOT_REAL_ATTESTATION`と常にNO_GO。旧鍵/issuerを失効後に有効に戻す遷移は実装しておらず、正規署名に見えても失効・epoch継続性は独立証拠がない限り不明。

## 3. 合成脅威10種類と失格方針

共有custodian/本人承認主体、偽issuer証明書、失効鍵リプレイ、epoch巻戻し、墓標消失、旧/新issuer同時有効化、部分コミット、Anchor不在の自動停止解除、秘密情報流出、承認再利用を各々固定する。**すべて`DENY_AND_HOLD_STOP`**。合成の`SIMULATED_ATTACK`は`D543_SYNTHETIC_REPLAY_REVOKE_OR_HANDOFF_DENIED`、仮想的に緩和できた`SIMULATED_MITIGATED`も実証明ではない。復旧・ローテーションを認証する仕組みではなく、実際の攻撃・実OS障害試験は0件。

本工程はG6-04の追記専用journal/墓標、G6-05単一writerフェンス、G6-06原子的コミット・復旧との将来統合を阻害しないことを設計上要求するが、これらの実保存/実装・耐久実証は行っていない。失効状態の真正性は単独で作ったJSONだけでは証明できない。

## 4. 実装構成

- `specs/p0_01_d5_43_key_lifecycle_contract.json`：G6-03の12必須条件・10ライフサイクル・10脅威、G6-01/G6-02/G8依存、秘密鍵・外部I/O未承認。
- `specs/p0_01_d5_43_synthetic_key_lifecycle.json`：架空issuer/鍵/epoch、合成の未実施ケース、実署名・実秘密情報すべてnull。
- `scripts/p0_01_d5_43_key_lifecycle_review.py`：合成データ完全一致と虚偽実証・承認の拒否。D5-42以前の全安全拒否経路を継承。
- `tests/test_p0_01_d5_43_key_lifecycle_review.py`：新規210件。12×2の実証偽装、10×6ライフサイクルの偽昇格、10×5脅威の失効・承認偽装、構成改ざん、前段安全条件、不正スキーマ、実I/O不在・入力非改変など。
- `specs/p0_01_d5_43_status.json`：G1〜G9未解決、実鍵0、実issuer認証0、実失効実証0。
- 本書。

前段2,978件＋D5-43新規210件＝**予定3,188件**。GitHub Repository checks、Windows Python 3.13 / IANA time zones、本人Windows全テストおよびPR差分目視の後、本人が手動マージする。成功は**合成仕様/監査コードの検証**であり、実鍵保管、実失効、独立Trust Anchorや本番運用が安全であるとの認定ではない。

## 5. 継続する安全条件

G2/G6実受入0/15、実作業0/15、G1〜G9`UNRESOLVED`、旧/新口座同一性`NOT_RECONCILED`、建玉・未約定注文・EA状態`UNKNOWN`。単一MT4、複数同時ログインなし、楽天問い合わせ中止、別デモB不採用。実鍵/OS/ネットワーク/実証拠/MT4/EA/EX4/注文/決済/停止解除は未承認。

`PHASE-1 BLOCKED`、`runtime_go_no_go=NO_GO`、`verified_values=null`、`safety_hold_latched=true`、`effective_approved_actions=[]`。初期10万円、単発0.5%、同時1.0%、日次1.5%、DD4%/5%の安全停止・承認、およびNY17:00の取引日境界を変更しない。
