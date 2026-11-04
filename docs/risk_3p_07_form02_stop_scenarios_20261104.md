# RISK-3P-07：FORM-02 売買方向・注文種別・損切り状態のオフライン審査

作成日：2026-11-04。基準main：`51a9b2ee6d500f0002065886a925345442ac6f66`（PR #177マージ後）。

> **合成データと本人審査用草案のみ。** 買い/売り、成行/指値/逆指値の形式・状態が検証できても、予定価格で約定すること、サーバーSLが実在すること、実際の損失が有限範囲内に収まること、また注文・決済・SL変更が許可されたことは示さない。EA・MT4・ブローカー・クラウドへの接続なし。

## 1. 確定済み条件と今回の範囲

- 今後の設計対象はUSD/JPY・EUR/JPY・EUR/USDの3ペア。旧Q3の4ペア履歴を改変しない。
- FX-SAF-001/002、Q6/7/13/116の既存ハード上限（1取引0.5%、同時非相殺合計1.0%）を維持。日次1.5%、DD4%新規停止/5%全決済・人間承認の停止要件も変更しない。
- 旧FORM-02は`UNDECIDED_IMPLEMENTATION_DETAIL`。実際の仕様承認やG1証拠は今回の対象外。
- **成行・指値・逆指値の合成形状と拒否条件**の設計のみ。Q116の円換算最大想定損失や数量調整の実運用算式ではない。

## 2. 価格根拠は注文状態により異なる

| 対象 | 合成審査で採る参照値 | 取引安全上、未解決の点 |
| --- | --- | --- |
| 成行候補（MARKET / CANDIDATE） | `planned_entry` | 計画価格は約定保証ではない。実fillまでリスク不確定 |
| 未約定（LIMIT/STOP / PENDING） | `trigger_price` | 現在bid/askとの関係が妥当でも、発動/滑り/ギャップにより実約定が異なる |
| 保有建玉（POSITION） | `fill_price`の**合成例** | 実ブローカー建玉と一致しなければ失格。部分約定、再起動時の変化を独立照合 |

BUYのSLは選択した参照価格より低いこと、SELLのSLは高いことを算術上確認する。ただし、この確認だけではSL配置可否、ストップレベル、実約定損失の上限、ティック価値、JPY換算は検証できない。

Pendingの参考的な価格形状の期待は、BUY LIMITは現在Askより低い、SELL LIMITは現在Bidより高い、BUY STOPは現在Askより高い、SELL STOPは現在Bidより低いという4方向の合成例。実発注許可の条件ではなく、実ブローカーのstop/freeze level・現在のspread・トリガー約定の規則は別途実証が必要。保有建玉では現在気配と過去triggerの位置関係を検査せず、確認済みの実fillを基準にする。

## 3. Server SL・変更確認・部分約定の扱い

- 候補はまだ発注していないため`server_stop_state=NOT_SENT`であり、存在しないサーバーSL確認を捏造できない。
- 未約定注文・保有建玉については合成上でも`server_stop_state=CONFIRMED`・同じepochのSL確認を要求。不明・遅延・削除・別世代では**新規発注を拒否する**。
- 保有建玉のSL変更は`stop_update_state=CONFIRMED`を合成上検査するが、この結果を使って実SL変更やSTOP解除を実行しない。変更保留・確認失敗・状態未知は新規拒否。
- `PARTIALLY_FILLED`、`CANCEL_REQUESTED`、`OUTCOME_UNKNOWN`等の未知状態は別の口座/注文/予約照合（FORM-05/06）なしで合格させない。**既存建玉の必要な保護措置を放棄するという意味ではない**。既存建玉の管理は別の安全要件と人間承認に従う。
- 発注予定価格やpending triggerが合成検査で適切でも、未確定の滑り・ギャップ・費用を無視して有限の損失上限を宣言しない。急変や有限上限不明の状態では新規注文拒否が原則。

## 4. 具体的な合成試験

| 種類 | 件数・内容 | 安全性の限界 |
| --- | --- | --- |
| 基本注文形状 | 16ケース：BUY/SELL、MARKET/LIMIT/STOP、CANDIDATE/PENDING/POSITION（MARKET/PENDINGは無効として除外） | **SHAPE ONLY**。約定実績やSLの保証ではない |
| 負ケース | 17分類：SL欠落、方向逆転、ゼロ距離、成行価格保証誤認、pending trigger欠落・方向不正、サーバーSL未確認、更新/削除結果不明、部分約定、取消未確定、発注結果不明、ギャップ・スリップ未確定、価格epoch不一致・気配逆転、口座/inflight不整合 | 全て新規拒否・NO_GO |
| 本人判断 | F02-1〜F02-6 | 具体的な価格根拠、SL確証、ストップ制約、部分約定、ギャップの扱い、再起動/保護状態の承認が必要 |

台帳`specs/risk_3p_07_form02_stop_review_draft_20261104.json`では全17負ケースに`DENY_NEW_ENTRY_NO_GO`、6判断に`UNDECIDED`を設定。監査`/scripts/audit_risk_3p_07_form02_draft.py`ではG1〜G9とFORM-02の未決/NO_GOが維持されることを検査する。

## 5. 実装上の境界と次の判断

- 付属`/scripts/phase1_form02_synthetic_stop_scenarios.py`は取引I/Oを持たない純粋関数で、実損失JPY値を計算しない。合成`epoch`一致は実証されたデータ鮮度上限を示すものではない。
- shapeが正しい場合でも`real_broker_stop_verified=false`、`measured_loss_jpy=null`、`finite_gap_loss_bound_verified=false`、`order_allowed=false`、`stop_release_allowed=false`、`runtime=NO_GO`、`PHASE-1=BLOCKED`、`safety_hold_latched=true`。
- FORM-01で3ペア×5契約属性は未確認。FORM-03のJPY換算、FORM-04費用、FORM-05/06同期/非相殺、FORM-07数量精度、FORM-08〜10の日次/ DD/時刻仕様は未決。FX-SAF-001〜015承認済みではない。
- 次のRISK-3P-08候補は、**FORM-03のEUR/USD USD→JPY換算方式・符号・bid/ask・同一世代の本人審査草案**。ここでも実レートや契約属性は未取得で、方式・閾値の承認は別途必要。

## 6. 確認コマンド

```text
python -m unittest tests.test_risk_3p_07_form02_stop_scenarios -v
python -m unittest tests.test_risk_3p_07_form02_draft -v
python scripts/audit_risk_3p_07_form02_draft.py
python -m unittest discover -s tests -p "test*.py"
python scripts/check_traceability.py
python scripts/check_phase1_way_e.py
```

PRのCI PASSやマージはFORM-02の本人承認でも安全重要実装承認でもない。実MT4/EA/注文/SL変更/新口座登録・契約値取得は禁止を維持。