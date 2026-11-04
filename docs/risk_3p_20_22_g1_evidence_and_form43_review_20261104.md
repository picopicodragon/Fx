# RISK-3P-20〜22：G1の正式受入条件案・合成出典検査・FORM43件の審査台帳

作成日：2026-11-04。追加先：未マージのPR #179（RISK-3P-08〜19の既存ブランチ）。**今回も実MT4への接続・読取・実データの収集・発注・停止解除を行っていない**。新3ペアはUSD/JPY、EUR/JPY、EUR/USD。現行G1の歴史的旧4×5＝20項目はUNRESOLVEDのまま保全する。

> 本書でいう「受入条件」は**将来の本人審査に提示する候補条件**であって、実証済み・安全重要仕様承認済みという宣言ではない。PRへのコミットやCI成功により、新G1＝3×5の正式スコープを承認・有効化しない。

## 1. RISK-3P-20：3ペア×5属性の証拠審査チェックリスト

成果物 `specs/risk_3p_20_g1_acceptance_rubric_20261104.json` に、次の属性それぞれの前提を定義した。項目数は3ペア×5＝15件。1項目あたり**共通8条件＋属性固有3条件＝11条件**、計165の将来確認項目を候補として定義したが、現時点での合格項目はゼロ。

| 属性 | この項目で必ず区別する点 |
| --- | --- |
| `min_lot` | 数量の最小値と1lotの基準契約サイズ、同一口座・同一銘柄を区別 |
| `lot_step` | 最小数量と刻み、最大lot、端数を勝手に切り上げて上限を超えない保証 |
| `point_quote` | digitsとpoint幅を独立に裏付け、pip/pointを無断で同一視しない |
| `tick_size_points` | tick sizeとpoint換算を両方の単位から照合、tick=1pointの仮定を禁止 |
| `tick_value_deposit_currency` | tick当たり価値が何lot・何通貨か、EUR/USDのquote USDから入金通貨への換算時点の検証 |

共通条件は、①別途許可された非破壊観測、②実シンボル・口座同一性、③出典・UTC時刻、④単位、⑤独立した別証拠経路、⑥鮮度/契約変更、⑦本人の原証拠レビュー記録、⑧既存EAや建玉への副作用がないこと。**単一画面の二重転記・合成データの出所ID・契約値の推定は独立証拠ではない**。

15件すべて`PENDING_REAL_WORLD_EVIDENCE`かつ`NOT_EVALUATED`、属性値・単位・口座別名・正確なシンボル・出典・時刻・照合・本人確認はnull。現時点でリアルなブローカーの契約値は検証していない。

## 2. RISK-3P-21：合成出典メタデータの構造検査

`scripts/review_g1_synthetic_evidence_envelope.py` と `tests/test_risk_3p_21_g1_synthetic_evidence_envelope.py` を追加。完全に架空の出典・発行者・時刻・単位・口座別名だけを扱い、仮の属性値を一切取り込まない。秘密データや実観測値の入力を拒否する。

次の負ケースを検査する：同じ出典/発行者を2つの独立証拠と偽る、出典時刻不整合、数字/通貨単位の混同、EUR/USDシンボル違い、実観測値・秘密データの混入、実データ用の未承認TTLがあるかのように主張する、無効な確認フラグ、旧通貨ペア混入。

**重要：** 合成出典IDの異なる文字列だけで本当の独立性を証明することはできない。入力の形が全て整った場合も返答は`SYNTHETIC_METADATA_SHAPE_ONLY_NOT_G1_EVIDENCE`、`runtime_go_no_go=NO_GO`、`broker_access_authorized=false`、`g1_acceptance_approved=false`、`order_allowed=false`、`stop_release_allowed=false`。実証の代用にはならない。

## 3. RISK-3P-22：FORM-01〜10の43件をまとめて個別判断可能にする

`specs/risk_3p_22_form43_owner_review_docket_20261104.json` は、元のF01（5件）、F02（6件）、FORM03〜07（20件）、FORM08〜10（12件）を**原設問・提案内容・出典ファイル・本人判断ID**と関連付けた。43件すべて`NOT_RECORDED`、`original_record_verified=false`、`implementation_approved=false`。

| 優先順位 | FORM | 先に解消すべき前提と依存関係 |
| ---: | --- | --- |
| 1 | FORM-01 | 実契約・口座・lot/tick単位とG1範囲 |
| 2 | FORM-02 | サーバーSL・約定価格・異常時の保護/拒否 |
| 3 | FORM-05 | 既存建玉、未約定、結果不明、リスク予約の世代同期 |
| 4 | FORM-06 | 予約、部分約定、ネット/グロス、OCO相殺の禁止 |
| 5 | FORM-03 | EUR/USD損益のUSD→JPY換算レートとbid/ask |
| 6 | FORM-04 | スプレッド・手数料・スワップ・ギャップの計上 |
| 7 | FORM-07 | 最小lot・丸め・JPY端数・0.5%/1.0%境界 |
| 8 | FORM-08 | NY17を基準とする日次1.5%・入出金調整 |
| 9 | FORM-09 | 高水位/DD2〜5%と再起動後の解除条件 |
| 10 | FORM-10 | 入力源ごとの鮮度・UTC・DST/時計異常 |

優先順位は**審査の進め方の提案**であり、上位FORMを承認したわけではない。原議が未取得の仕様、正式ブローカー証拠が不足する仕様は合格・本番移行扱いにしない。必要なら後に個別に審査・改版する。PRマージだけで43件を一括承認しない。

## 4. 監査と失敗系

`scripts/audit_risk_3p_20_22_owner_evidence.py` は、新ルーブリック・43件の台帳を既存のFORM原台帳、RISK-3P-18/19、V3テンプレ、G1〜G9と突き合わせる**読み取り専用**検査。`tests/test_risk_3p_20_22_owner_evidence.py` は出典の問い/提案の変更、43件の欠落・重複、15属性の値や受入状態の捏造、承認・STOP解除・無審査マージの偽装を拒否する。

```text
python -m unittest tests.test_risk_3p_21_g1_synthetic_evidence_envelope -v
python -m unittest tests.test_risk_3p_20_22_owner_evidence -v
python scripts/audit_risk_3p_20_22_owner_evidence.py
python -m unittest discover -s tests -p "test*.py"
python scripts/check_traceability.py
python scripts/check_phase1_way_e.py
```

## 5. 次に残る実際の意思決定

FORM-01〜10の43件には、本人の設計方針の個別判断、原議照合または明示的な新仕様への同意、版管理された受入条件が必要。**それらは今回採択していない**。G1正式スコープの3×5改版と、既存EA・建玉が存在していたデモ環境の読取専用確認許可も、それぞれ本人の**別の明示的承認**が必要。

従来の原議と旧4ペア記録を保存し、未証明のUSD/JPY・EUR/JPY・EUR/USD属性を勝手に記載しない。実口座・発注・Cloud/EA操作は引き続き実施しない。

**不変の安全要件：** 1取引損失≤純資産0.5%、建玉＋未約定＋候補の非相殺合算≤1.0%、日次1.5%、DD4%新規停止、DD5%全決済と本人承認。G1〜G9 UNRESOLVED、FX-SAF-001〜015未承認、PHASE-1 BLOCKED、runtime NO_GO、safety_hold_latched=true、verified_values=null。

> **後続の本人決定による更新（2026-11-04、RISK-3P-28）**：当初この資料で未決としたP03「G1正式審査対象」は、本人が**新3ペア×主要5属性（計15項目）への変更を承認済み**。旧4×5の未解決記録は別snapshotに保存した。G1の実属性0/15・G1〜G9 UNRESOLVED・PHASE-1 BLOCKED・runtime NO_GOは不変。P02原議照合とP04実MT4非破壊観測の安全な個別許可は依然未決。参照：[G1範囲変更](risk_3p_28_g1_owner_scope_approval_20261104.md)。
