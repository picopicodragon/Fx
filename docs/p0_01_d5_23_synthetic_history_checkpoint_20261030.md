# P0-01 D5-23：合成承認履歴の再提出・巻き戻し・取消し欠落監査

作成日：2026-10-30。D5-22の合成承認状態遷移に対する追加監査。実装：
- `scripts/p0_01_d5_23_history_checkpoint.py`
- `tests/test_p0_01_d5_23_history_checkpoint.py`

**全てOFFLINE_SYNTHETIC_ONLY。SHA-256はこの工程では整合性比較用であり、署名・本人認証・永続アンカーではない。全結果NO_GO。**

## 1. 仕様上の課題

D5-22は、**提示された**イベント配列の連番・順序・時刻・状態遷移を検証する。だが、取り消した履歴の末尾を削り、古い配列を改めて提示した場合、配列だけを見ても失われたイベントを検知できない。

D5-23は、イベント列と**別入力として供給される合成チェックポイント**の比較で、巻き戻し・削除・改ざんを判定する。ただしチェックポイント自体は同じ呼出元から提供される未信頼データ。**独立した外部保存、署名、本人確認、信頼された時刻、改ざん防止は一切ない。** よって実環境のリプレイ防止の実装と解釈してはならない。

## 2. 合成ハッシュ連鎖

`build_synthetic_history_chain(lifecycle)` はD5-22の厳格なスキーマ・イベント遷移を通った合成ライフサイクルだけを受け取り、監査テスト向けのハッシュ列を生成する。外部入出力や時刻の読取なし。

各レコードのハッシュは、`domain="FX_D5_23_UNTRUSTED_SYNTHETIC_HISTORY_V1"`、承認レコード（操作・仮想口座・仮想端末・停止原因・発行/期限時刻・レコード識別子）、当該イベント（種類・連番・時刻・識別子）、直前ハッシュをキー順JSONで決定的に表現し、SHA-256で計算。最初の`previous_hash`はゼロ64字。

返される`journal`の行は`sequence`、`previous_hash`、`event_hash`のみ。入力側のスコープと状態にハッシュを結びつけるが、秘密鍵や署名はない。**誰でも任意の合成データで新たなハッシュ列を生成できる。**

## 3. チェックポイントとの比較

`audit_synthetic_history_checkpoint(bundle)` の入力は厳格な6フィールド：
`origin=SYNTHETIC_ONLY`、`schema_version=1`、`lifecycle`、`journal`、`checkpoint`、`integrated_fixture`。

`checkpoint`は`record_id`、`sequence`（0始まり）、`head_hash`の3フィールド。これはテストが用意する**仮想の独立参照値**であり、検証可能な外部ログではない。チェックポイントを偽装した入力も容易に成立する。

| 分類 | 状況 | 返値のstatus |
|---|---|---|
| 入力拒否 | 外側のスキーマ・チェックポイント・ハッシュ形式が不正 | `HISTORY_INPUT_REJECTED_FAIL_CLOSED` |
| 元履歴拒否 | D5-22の合成イベント・時刻・状態遷移に違反 | `HISTORY_LIFECYCLE_REJECTED_FAIL_CLOSED` |
| ハッシュ列不一致 | 行数、順序、前行ハッシュ、スコープ・時刻・イベントの内容が違う | `HISTORY_CHAIN_MISMATCH_NO_GO` |
| 巻き戻し | チェックポイントの連番が提示された末尾より後 | `HISTORY_ROLLBACK_DETECTED_NO_GO` |
| チェックポイントの相違 | 当該連番のハッシュ／レコードIDが異なる | `HISTORY_CHECKPOINT_MISMATCH_NO_GO` |
| 参照が古い | 提示された履歴の末尾よりチェックポイントが古い | `HISTORY_CHECKPOINT_STALE_NO_GO` |
| 下位ゲートの異常 | D5-22/D5-21が拒否契約から逸脱、偽GOや停止解除など | `HISTORY_DOWNSTREAM_REJECTED_FAIL_CLOSED` |
| 合成上の整合 | 元履歴、連鎖ハッシュ、末尾チェックポイントが一致し、D5-22/D5-21も**拒否状態** | `HISTORY_SYNTHETIC_CHAIN_CONSISTENT_NO_GO` |

**優先順位：** 不正構造・元イベント → ハッシュ列 → レコードID/連番 → 参照の一致・鮮度 → 権限拒否ゲート。チェックポイントが末尾の履歴と一致しても、実際の現在の承認履歴である証拠にはならない。

## 4. 許容できない権限の昇格

- `audit_synthetic_history_checkpoint`はD5-22の`audit_synthetic_lifecycle_with_authority`を呼ぶが、`LIFECYCLE_AND_AUTHORITY_NO_GO`と必要なすべての**拒否フラグ**が揃わない結果を却下する。
- 本人の実承認、EA実行、注文、停止解除の権限は出さない。
- `HISTORY_SYNTHETIC_CHAIN_CONSISTENT_NO_GO`も**内部整合した合成サンプル**を意味するだけである。
- 返値は固定コードと件数のみ。口座番号、承認トークン、イベント生値、ハッシュ原文はエコーしない。

全結果共通：
`approval_verified=false`、`action_authorized=false`、`ea_execution_authorized=false`、`order_authorized=false`、`stop_release_authorized=false`、`effective_approved_actions=[]`、`safety_hold_latched=true`、`runtime_go_no_go=NO_GO`、`verified_values=null`、`broker_verified=false`、`production_usable=false`、`read_only_ex4_execution_approved=false`、`terminal_execution_approved=false`、`orders_generated=false`、`forward_trading_enabled=false`、`phase_1=BLOCKED`。

## 5. 監査で**保証できない**こと

1. **両方の偽造：** ハッシュ連鎖とチェックポイントを同時に書き換えると、合成の比較は内部整合と判定する。これを回帰テストで明示。**本物の改ざん防止は未実装。**
2. **独立参照値の不在：** 信頼された書込み先、単調増加シーケンス、取消し墓標、二重起動排除、署名鍵・検証鍵の管理、ハードウェア/外部署名などは未設計・未検証。
3. **実時刻の不在：** 過去データを古い`as_of_utc`と一緒に再投入すれば、真の鮮度は認定できない。
4. **本人認証の不在：** `APPROVAL_CLAIMED`を記録しただけでは承認ではない。実本人認証・承認失効はG8として未解決。
5. **実環境の不在：** 楽天MT4のEA・注文・建玉・停止・通知動作は未実証。D5-12/D5-21のG1〜G9を解消していない。

## 6. テストと受入条件

- 新規**50件**、従来755件と合わせて**想定805件**。
- 取消し削除、古い提案/申告への巻き戻し、連番・ハッシュ・レコードID・口座・端末・操作・時刻の改ざん、旧参照、二重偽造の限界、下位ゲートの偽GO・状態不一致、入力不変を検査。
- [ ] Windows本人ローカル全805件成功
- [ ] PR本文に必須見出し「関連仕様ID」「テスト結果」「本人確認」が揃い、GitHub Repository checks / Windows Python 3.13 CI成功
- [ ] D5-22以前の実装・安全ゲートに変更なし
- [ ] 本人差分目視・手動マージ。PRはMT4操作・注文の承認ではない

現行方針：**単一MT4環境のみ／楽天への問い合わせ中止／別デモB非採用**。このPRでMT4に触れない。G1〜G9は引き続き未解決。

**D5-23の完了はインメモリ・合成履歴の比較と異常判定の完成のみ。実認証や実注文の安全認定ではない。**
