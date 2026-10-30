# P0-01 D5-27：G2証拠確認票・G6停止履歴の脅威モデル（完全オフライン）

作成日：2026-10-30。前提はD5-26（PR #141、本人Windows954件OK、マージ済み）。D5-27は **OFFLINE_DESIGN_ONLY / SYNTHETIC_ONLY** に限定し、MT4の起動・ログイン・照会、EX4/EA実行、発注・決済、実ファイル保存、Windows時計の取得、通知、楽天問い合わせ、追加デモ口座を行わない。

**基本境界：G2とG6の未解決事実は、本工程では一件も解消されない。証拠の存在、時刻、実口座識別、独立Trust Anchorの真正性は推測できない。**

## G2：既存口座とEA・建玉の照合を始める前の準備

`specs/p0_01_d5_17_evidence_reconciliation_status.json`の従来記録を**変更せず**、新しい非実行型の確認票を設計した。

報告元の区別：

- `EV-OLD`：以前のMT4デモAについて、MACD Sampleが観察された、AutoTradingがOFFらしい、建玉**または**未約定注文があった、接続表示がCONNECTEDらしいという**過去のユーザー報告**。建玉と未約定注文のどちらかを特定した証拠ではない。
- `EV-NEW`：後日、既存の口座は休眠中で建玉・注文はないとする**別のユーザー報告**。
- 両報告の観測日時、対象口座が同一か、実際の現時点のEA・建玉・未約定注文は**未照合**。相互に矛盾が確定したとも、どちらかが誤りとも判断しない。口座・サーバーID、具体的な日時を作り足さない。

8項目の新規確認票（全て`NOT_PERFORMED`）：

| ID | 項目 | 将来の証拠境界 |
|---|---|---|
| P27-G2-01 | 端末識別 | 単一MT4端末・出典・観測時刻 |
| P27-G2-02 | 口座・サーバー同一性 | 旧デモA／休眠口座の対象と照合。実口座番号はGitHubへ保存しない |
| P27-G2-03 | 接続・セッション | 非同時ログイン、接続画面と時刻 |
| P27-G2-04 | EA装着・AutoTrading | MACD Sampleの装着状態とスイッチ表示を別々に確認する構想 |
| P27-G2-05 | 建玉 | 過去の「建玉または注文」を現在の建玉と同一視しない |
| P27-G2-06 | 未約定注文 | 建玉と独立して確認する構想 |
| P27-G2-07 | 出典・観測日時 | 原申告・口座スコープ・観測時刻・報告時刻を別記録 |
| P27-G2-08 | ローカルログ取扱い | 取扱ポリシー未実施。ログや機密情報をGitHubに登録しない |

実際の目視確認には、端末がすでに稼働しているか・EAがあるか・既存注文があるかの安全前提を確認し、**行為ごとに別途明示承認**が必要。新たなログインやMT4起動は本PRから許可されず、目視レビューが承認されてもEA/EX4の実行、注文、建玉操作の許可にはならない。D5-17の既存8件`S17-01〜08`の未実施状態も保持する。

## G6：停止履歴の真正性・永続化の脅威モデル

D5-23/24の合成履歴・基準点比較は、実Trust Anchor、実暗号署名、単調増加外部世代、原子的な書込み、取消し墓標の耐久性の証明ではない。

新しい`specs/p0_01_d5_27_g2_g6_offline_design.json`では、10件の設計上の障害注入対象を`P27-G6-01〜10`として登録した。

| 番号 | 障害・脅威 | 将来の受入条件案 |
|---|---|---|
| 01 | トランザクション途中破損 | ジャーナルと停止ラッチが確定しなければ自動復帰禁止 |
| 02 | 書込み途中の電源喪失 | 不完全な保存・復元時は停止保持 |
| 03 | 基準点の巻き戻し | 独立した単調基準で照合、異常なら停止 |
| 04 | 履歴・チェックポイント・基準点の同時偽造 | **現行の未信頼入力比較では検出不可**。別の署名/保護/独立基準が必要 |
| 05 | 取消し記録の削除 | 耐久的な取消し墓標と照合 |
| 06 | 複数書込み主体の競合 | 単一書込み主体の排他・競合検出 |
| 07 | Windows時計の再起動/補正 | UTCと単調増加時計を区別し、連続性不明なら自動解除禁止 |
| 08 | 署名鍵改ざん・窃取 | 鍵管理・検証経路の独立性 |
| 09 | 保存領域の書込み不可・破損 | 容量不足・I/O障害時は停止継続 |
| 10 | 古いバックアップ復元 | 外部に独立した世代・取消し記録との照合 |

これらは**障害を実際に発生させて検証した結果ではなく、オフライン設計上の試験候補**。新しい合成ケースで障害コードを投入しても停止ラッチが維持されることのみ検証し、実WindowsへのI/Oは行わない。実OS試験が必要になった場合は、**MT4とは独立した専用環境と別の明示承認**が不可欠。

## 監査関数・検査の優先順位

`scripts/p0_01_d5_27_g2_g6_offline_preflight.py`は、(1)新確認票と脅威モデル、(2)元のD5-17ユーザー申告台帳、(3)D5-25 G1〜G9未解決マトリクス、(4)完全合成のG2/G6ケース、の**4つの未信頼入力**を受け取る純粋関数 `audit_d527_offline_preflight(design, original_evidence, gap_matrix, synthetic_case)`を提供。

結果の優先順位：

| 条件 | 結果 |
|---|---|
| 新設計に不足や不正な承認・検証済み主張 | `D527_DESIGN_REJECTED_FAIL_CLOSED` |
| D5-17台帳の不正な「照合済み」主張、報告・日時の改変 | `D527_EVIDENCE_BASELINE_REJECTED_FAIL_CLOSED` |
| D5-25 G1〜G9の実未解決条件の偽解除 | `D527_GAP_BASELINE_REJECTED_FAIL_CLOSED` |
| 合成ケースの不正な型/状態/追加許可フィールド | `D527_SYNTHETIC_CASE_REJECTED_FAIL_CLOSED` |
| 合成の停止解除申告 | `D527_STOP_RELEASE_CLAIM_DENIED_NO_GO` |
| G6障害ケースがある | `D527_G6_SIMULATED_FAILURE_LATCHED_NO_GO` |
| G2合成スコープ・日時・報告の不整合/不明 | `D527_G2_UNRECONCILED_NO_GO` |
| G2合成一致・G6障害なし | `D527_OFFLINE_DESIGN_COHERENT_NEVER_AUTHORIZED` |
| 不測の入力例外 | `D527_INPUT_EXCEPTION_FAIL_CLOSED` |

最後の「整合」は、合成入力が構造的に矛盾していないというだけで、実口座・履歴・停止状態・本人の同意を確認したという意味ではない。

**全結果で** `g2_real_world_resolved=false`、`g6_real_world_resolved=false`、`account_identity_verified=false`、`positions_verified=false`、`pending_orders_verified=false`、`ea_state_verified=false`、`trusted_anchor_verified=false`、`atomic_persistence_verified=false`、`revocation_durable_verified=false`、`real_transition_authorized=false`、`visual_review_approved=false`、`mt4_launch_approved=false`、`mt4_read_only_approved=false`、`host_io_approved=false`、`approval_verified=false`、`action_authorized=false`、`ea_execution_authorized=false`、`order_authorized=false`、`stop_release_authorized=false`、`effective_approved_actions=[]`、`safety_hold_latched=true`、`verified_values=null`、`broker_verified=false`、`production_usable=false`、`read_only_ex4_execution_approved=false`、`terminal_execution_approved=false`、`orders_generated=false`、`forward_trading_enabled=false`、`phase_1=BLOCKED`、`runtime_go_no_go=NO_GO`。

## 残る制限・受入条件

- 原申告、確認票、GAP台帳、合成ケースのすべてが入力側から改変されると、独立した真の証拠原本と比較できない。このモデルは本人認証・署名・信頼されたストレージの代用ではない。
- G1〜G9は**全件UNRESOLVED**。現在の口座同一性、EA、建玉、未約定注文はUNKNOWN。
- 楽天へのメール問い合わせを行わず、独立デモBを作らず、単一MT4環境・複数環境非同時運用を維持。
- 初期10万円、1取引0.5%、同時1.0%、日次1.5%、DD4%新規停止、DD5%強制停止+人間承認、NY17日次境界など**既存の安全規定を一切変更しない**。
- [ ] D5-26既存954件＋D5-27新規64件＝**想定1,018件**の本人Windowsテストが成功。
- [ ] GitHub Repository checks / Windows Python 3.13 CI成功。
- [ ] 本人が差分を確認してPRを手動マージ。PRマージは実環境へのアクセス承認ではない。

**D5-27完了の意味は、G2の未照合証拠の取扱い手順とG6の未信頼・模擬故障モデルの設計・合成検証のみ。**
