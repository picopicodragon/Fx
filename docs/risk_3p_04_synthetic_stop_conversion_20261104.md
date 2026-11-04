# RISK-3P-04：EUR/USD円換算・SL距離・数量・未約定の合成リスク検証（非運用）

作成日：2026-11-04。前提：PR #170/#172/#173/#174マージ後、設計対象はUSD/JPY・EUR/JPY・EUR/USD。実契約属性・リスク算式の本人承認は未取得。

> **NON-OPERATIONAL SYNTHETIC ONLY。** 本書とテストは実際の楽天MT4のレート・約定・注文の安全性を証明しない。Q116の円換算損失を既存の仮定数値で検算するのみであり、承認された損失推定アルゴリズムではない。すべてNO_GO、PHASE-1 BLOCKED、停止ラッチ維持。

## 1. 実施対象と未決条件
| 項目 | 今回の合成検証 | 未承認・未確認事項 |
| --- | --- | --- |
| FORM-01（契約仕様） | 契約サイズ/lotと最小lot、lot step、max lotの計算整合を確認 | 楽天MT4の実契約・EUR/USD銘柄表示、tick value、口座同一性 |
| FORM-02（損切り） | BUYで entry > stop、SELLで stop > entry の架空差額を説明用に計算 | 注文種別ごとの滑り、実約定値、実サーバーSL、ギャップ |
| FORM-03（円換算） | EUR/USDの**正のUSD想定損失**に、同一合成snapshot内のUSD/JPYの**ask**を掛けた保守側の一例 | 負の損益、口座通貨、MT4のtick valueの基準、清算・JPY換算に使う実bid/ask、レート変動時の安全バッファ |
| FORM-04（費用） | 追加のquote建て不利変動、JPY建て費用をすべて明示入力 | スプレッドの二重計上回避、手数料・スワップ、SLのギャップ損失に有限上限がない場合の対応 |
| FORM-05（同期） | 3通貨ペアの合成snapshot_id・観測時刻の一致、建玉・未約定・inflight照合状態を要求 | 実brokerの複数注文が原子的に照合されるという保証、取引中の競合/再送 |
| FORM-06（同時発動） | POSITION/PENDING/CANDIDATEの損失説明値を、方向相殺・三角関係なしで加算 | 部分約定、取消未確認、OCOの実保証・同時発動、相関ストレス・通貨集中の限度値 |
| FORM-07（精度） | Decimalで刻み条件と 500.01/1000.01 円の境界を確認 | 最小lotに基づく実注文サイズ丸め方向、費用項目のJPY小数端数と量の桁 |

旧 `specs/p0_01_risk_formula_open_decisions.json` のFORM-01/03が旧4ペアを記載していても、記録を改ざんせず、後続の3ペア新対象を独立した設計変更として取り扱う。旧20属性のG1を勝手に15属性承認済みに変更しない。

## 2. 説明用の計算（採用数式ではない）
次の入力はすべて**架空**。EUR/USDの正のquote損失（USD）を、同時点の架空USD/JPY askでJPYへ換算する。例えばEUR/USDをBUY 0.01 lot、架空の1lot=100,000 EUR、entry=1.2000、stop=1.1990、追加不利変動0.0001 USD/EUR、架空手数料等5 JPY、架空USD/JPY bid=150、ask=151とすると：

```text
差額 = (1.2000 - 1.1990 + 0.0001) USD/EUR = 0.0011
数量 = 0.01 lot × 100,000 EUR/lot = 1,000 EUR
架空のUSD損失 = 1.1 USD
説明用JPY損失 = 1.1 × 151（架空ask）+ 5 = 171.1円
```

この171.1円は**MT4の契約値から推計した最大実損失ではない**。急変時の実損失はSLとの差額を大幅に超え得る。架空askを選んだことだけで全リスクを保守的に評価できたとは主張しない。USDJPYのbid/askが1秒でも不一致なら拒否する単一合成世代の検査であり、現実の鮮度の許容秒数を設定したものではない。

USD/JPY・EUR/JPYの架空quote損失はJPY建ての説明値としてそのまま合計するが、実口座がJPY建てであること・手数料/SWAPがJPYであることは未検証である。

## 3. テストに実装した安全上の拒否
- `min_lot`未満、刻み不一致、最大lot超過、契約サイズ欠落、ロットの勝手な切り下げ・繰り上げ
- BUYでSLがentry以上、SELLでSLがentry以下、SL欠落、方向や注文状態が未確認
- USDJPY/他2ペアのquote欠落、交差bid/ask、時刻・snapshot_id不一致、NaNや数値型を文字列として勝手に解釈
- quote建て不利変動・費用の入力欠落、`OUTCOME_UNKNOWN`、`PARTIALLY_FILLED`、未照合のcancel/inflight、2候補や同一ID
- 円換算後の架空候補損失が0.5%、全POS/PENDING/CANDIDATEが1.0%を**超えた場合を区別**。上限以下でも注文許可しない。

全状態は`broker_contract_verified=false`、`costs_verified=false`、`stop_execution_guaranteed=false`、`order_allowed=false`、`result_authorizes_trade=false`、`runtime_go_no_go=NO_GO`、`phase_1=BLOCKED`、`safety_hold_latched=true`、`stop_release_allowed=false`、`automatic_retry_allowed=false`、`verified_values=null`。

## 4. スコープ外と次の設計判断
このモデルは発注サイズの計算・券面契約照合・実市場データ取得・SL設定・注文発行・MT4/EA接続・UI・クラウドCAS・本番リスク審査コードを含まない。Q116の損失は実市場では必ず有限の上限を設けられるとは限らない。したがって、`adverse_buffer_quote_per_base`を入力しただけで損失額が保証される設計にはしない。

本人承認を要する未決：①ブローカー確定のEUR/USD契約とtick価値・口座通貨、②約定種別別のentry/stopとギャップの保守扱い、③bid/ask換算と通貨別市場変動のストレス、④スプレッド・手数料・スワップの配賦・二重計上、⑤部分約定・OCO・取消確認・予約とリスク枠、⑥数量/円端数と最小lot、⑦ネット/グロス通貨集中の数値閾値。ここで数値を新しく正式決定しない。

次工程RISK-3P-05候補は、これら未決事項をFX-SAF-001/002・FORM-01〜07・G1の3ペア影響と対応付けた**本人判断用仕様草案**の作成。実環境G1照合・MT4実行・安全実装はそれぞれ別承認。

## 5. 検査
- `python -m unittest tests.test_risk_3p_04_synthetic_stop_conversion -v`
- `python -m unittest discover -s tests -p "test*.py"`
- `python scripts/check_traceability.py`
- `python scripts/check_phase1_way_e.py`
- `python scripts/audit_risk_3p_02_migration.py`

証拠・承認の状態はすべて従来通り。FX-SAF-001〜015 `implementation_approved=false`、G1〜G9 UNRESOLVED、PHASE-1 BLOCKED、runtime NO_GO。ローカルの原議欠落探索保留も安全実装受入の省略にはならない。