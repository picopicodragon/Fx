# P0-01 D5-26：G1〜G9優先順位と工程移行判定（実行権限を発生させない設計）

作成日：2026-10-30。前段はD5-25（PR #140、本人Windows 906件OK、GitHub CI成功、マージ済み）。本工程は **OFFLINE_DESIGN_ONLY**。実機・MT4・楽天口座、本人認証、EA/EX4、実注文、停止解除、通知送信、外部保存を実施しない。

**位置付け：以下は次のレビューに向けた提案であり、本人の正式な実行承認・正式仕様変更ではない。** D5-25監査台帳でG1〜G9はすべて`UNRESOLVED`、`release_blocker=true`、`real_world_verified=false`。これを変更しない。

## 1. 二つの優先軸

**A：オフライン設計の直近重点**（G2とG6、並行で設計可能）
- **G2（単一MT4口座・既存EA・建玉・未約定注文の未照合）**：旧デモAのMACD Sample・未約定注文ありとの過去申告と、後日の休眠・保有なし申告について、同一口座・同一日時であることがまだ証明されていない。まず操作を伴わないチェックリストと、確認対象・観測時刻・不一致保持ルールを作る。現在の口座状態は`UNKNOWN`のまま。
- **G6（停止履歴の真正性・永続性）**：D5-23/24で「未信頼の履歴＋チェックポイント＋基準点を全て偽装すると検出できない」ことを明示済み。実際の原子的保存・独立Trust Anchor・二重書込み防止・停止履歴の真正性は未実装。先に脅威モデルと障害注入受入条件を設計する。

**B：将来の実証に向けた暫定レビュー順（提案）**

| 順位 | ID | 対象 | 前に実証が必要と想定するもの |
|---:|---|---|---|
| 1 | G2 | 単一口座の同一性・EA・建玉・未約定注文 | なし（実際の確認には別の明示承認） |
| 2 | G6 | 独立した停止監査基盤 | なし（実際の保存試験には別の明示承認） |
| 3 | G8 | 本人認証・権限・通知 | G6 |
| 4 | G7 | 時計・再起動・UTC/DST | G6 |
| 5 | G3 | 実注文経路の停止強制 | G2、G6、G8、G7 |
| 6 | G1 | 4ペア×5項目の契約属性 | G2 |
| 7 | G5 | 損益・日次計算 | G1、G7 |
| 8 | G9 | 営業日・市場時間 | G1、G7 |
| 9 | G4 | 再送・拒否・接続断・建玉照合 | G3、G5、G9 |

これは**依存関係を見やすくするための提案**であり、技術的な検証順序の一意の正解ではない。オフライン作業は各GAPについて並行可能。表の前提GAPが「解決済み」になったという意味でもない。実環境への移行許可ではない。

## 2. 工程移行候補と権限の分離

| 候補 | 現状 | 意味と条件 |
|---|---|---|
| `OFFLINE_SPEC_REVIEW` | `DESIGN_ONLY` | 仕様書・テスト・模擬データの検討のみ。端末の操作は含まない |
| `SINGLE_ENV_VISUAL_REVIEW` | `NOT_APPROVED` | **別途明示承認**が必要。G2対象の目視確認構想。MT4起動/ログイン許可の自動付与なし |
| `MT4_READ_ONLY_PREFLIGHT` | `NOT_APPROVED` | **別途明示承認**が必要。前の目視検討から自動移行しない。EA/EX4や注文は禁止 |
| `OFFLINE_PERSISTENCE_LAB` | `NOT_APPROVED` | 実WindowsファイルI/Oでの保存実験は別工程・別承認。今回ファイルI/Oの実装・実施なし |
| `DEMO_EXECUTION_EVALUATION` | `NOT_APPROVED` | 将来の独立承認、単一MT4、必要なGAP実証と安全隔離設計が前提。旧独立デモBを再採用しない |
| `LIVE_ACTIVATION` | `NOT_APPROVED` | G1〜G9の実証・包括安全評価に加え、独立した本人による本番稼働の明示承認が必要 |

`MT4_READ_ONLY_PREFLIGHT`と`SINGLE_ENV_VISUAL_REVIEW`は、G2を解消するための将来の**候補**であって、G2解消済みを前提とした承認ではない。実際の操作時に必要な追加の安全条件（Autotrading状態、ポジション確認、読取り境界、既存EAの扱いなど）は、その時点で別途確認・承認する。

実口座状態、契約スペック、EA装着状態、建玉、損益、注文機能の実証は今はできない。PRマージとCI成功は、これらの確認の承認ではない。

## 3. 機械可読な受入判定

- `specs/p0_01_d5_26_transition_priority_plan.json`に暫定順位・依存関係・工程案を置く。
- `scripts/p0_01_d5_26_transition_plan.py`の純粋関数`evaluate_offline_transition_plan(plan, baseline)`は、D5-25の未解決GAPマトリクスと照合し、不正スキーマ・GAP解決済みへの虚偽変更・解除条件の変更・依存関係の逆転・実証要件のすり替え・承認無しへの変更を拒否する。
- **受入時の返値も**`PLAN_DESIGN_VALIDATED_REAL_TRANSITIONS_BLOCKED_NO_GO`であり、現実の移行が許可されたことを意味しない。計画に問題があれば`PLAN_*_REJECTED_FAIL_CLOSED`で拒否する。
- 入力は**双方ともユーザー由来の未信頼JSON**。両方一緒に偽装された場合まで真正性を証明できない。GitHubの履歴と本人の差分レビューは変更検知の補助であり実権限認証の代用ではない。
- 固定出力はすべて`real_transition_authorized=false`、`visual_review_approved=false`、`mt4_read_only_approved=false`、`host_io_approved=false`、`demo_execution_approved=false`、`live_activation_approved=false`、`approval_verified=false`、`action_authorized=false`、`stop_release_authorized=false`、`effective_approved_actions=[]`、`safety_hold_latched=true`、`verified_values=null`、`phase_1=BLOCKED`、`runtime_go_no_go=NO_GO`。注文生成やForwardTradingも無効。

## 4. 観測されていない条件は引き続きNO_GO

G1〜G9の実世界の証拠は、D5-25の`external_or_real_evidence_required`を根拠として新計画内に引き継ぐ。例えばG2で前後の申告が一致しない状態や、G6で実存しないTrust Anchorを合成参照値で代替することを許さない。**どのGAPも今回解消しない。**

前提は楽天証券の**単一MT4環境のみ**。楽天への問い合わせ中止、独立デモB非採用、複数IDの同時運用なしを維持。

## 5. 受入基準

- [ ] 新規48テスト、既存906件を合わせて**954件**をWindowsで実行。
- [ ] GitHub Repository checksとWindows Python 3.13 / IANA time zones CI成功。
- [ ] G1〜G9全件を`UNRESOLVED`、`release_blocker=true`、`real_world_verified=false`のまま保持。
- [ ] PR差分を本人が確認して手動マージ。MT4操作・実稼働の承認に代えない。
- [ ] G2/G6の次の作業は**まずオフラインの手順書/脅威モデルの作成**。実機・ローカル永続化・本人認証実装などに進む場合は別途個別承認を取得する。

**D5-26の完了とは「暫定計画と、その安全な記述のオフライン検証」の完了のみ。** 実証計画の実行許可や本番移行判定ではない。
