# RISK-3P-08〜12 一括工程：FORM-03〜07 3通貨ペア合算リスクのオフライン審査

作成：2026-11-04。基準main：PR #178マージ後 `8ac478698d5f96bc05256cf6e13ac4eb110316ec`。後続指示により関連する5工程を**ひとつのPRに集約**。最後のmain反映のみ本人差分/CI確認の対象とし、工程ごとに手動マージを求めない。PRのマージは安全重要仕様承認ではない。

> **純粋な合成データによる算術・拒否テストと、未承認仕様の整理のみ。** 楽天MT4・口座・クラウド・価格API・鍵・EA・発注・実ストップ操作を一切行わない。スプレッド/SL/ギャップ/手数料/契約値/通貨集中は実証・承認されておらず、合成損失額は将来の実取引損失上限ではない。

## 1. 5工程を1 PRへまとめた範囲

| 工程 | FORM | 今回の検証（すべて合成） | 正式未決事項 |
| --- | --- | --- | --- |
| RISK-3P-08 | FORM-03 | EUR/USDの正のUSD損失×USD/JPY ask、JPY建て損失×1、同一epochとbid/ask検査 | broker入金通貨、side別換算レート、逆数・利益/損失の符号、実レートと鮮度上限 |
| RISK-3P-09 | FORM-04 | SPREAD / COMMISSION / SWAP / SLIPPAGEの4区分、追加・既算入の二重計上区別、欠損拒否 | 実費用の単位・時刻・分類、SLギャップの有限上限を保証しない扱い |
| RISK-3P-10 | FORM-05 | 口座・価格・予約epoch一致、broker/pending/inflight/通貨別照合flag、未知のdispatch/cancel拒否 | 実ブローカー状態の真偽、独立CAS、同時writer、再起動・二重発注競合 |
| RISK-3P-11 | FORM-06 | POSITION / PENDING / RESERVED / CANDIDATEを非相殺合算。部分約定FILLEDとREMAINDER双方を別sliceとして計上 | 三角関係、OCOの真正保証、通貨別集中・ストレス閾値、実lot・約定の独立照合 |
| RISK-3P-12 | FORM-07 | Decimalでstrict lot min/step/maxとリスク0.5%/1.0%超過を検知、端数切捨てなし | 楽天MT4のcontract・lot桁とJPY金額丸めを本人が確定 |

旧仕様`specs/p0_01_risk_formula_open_decisions.json`のFORM-03には旧Q3の4ペアが残る。新設計はUSD/JPY、EUR/JPY、EUR/USDの3ペアだが、過去記録は消さず、後続の正式変更と区別する。FX-SAF-001〜015、FORM-01〜10、G1〜G9の未決・未承認を減らさない。

## 2. 説明例：合成3ペアの非相殺損失

合成quote snapshot USD/JPY bid=150、ask=151、EUR/JPY bid=181、ask=182、EUR/USD bid=1.20、ask=1.21、epoch=11。各値は市場から取得したものではない。

| slice | 架空のquote損失 | 換算・費用の扱い | 合成JPY表示 |
| --- | --- | --- | ---: |
| EUR/USD BUY候補 | +2 USD | 2×151 + JPY建て追加費用5、spread既算入1は加算しない | 307円 |
| USD/JPY SELL保有 | +200 JPY | 200 + JPY建て追加費用5 | 205円 |
| EUR/JPY BUY未約定 | +300 JPY | 300 + JPY建て追加費用5 | 305円 |
| **合計** | | ネット方向と三角相殺を考慮せず全損失を加算 | **817円** |

10万円の架空純資産に対し候補307円は既存0.5%枠（500円）以内、非相殺合計817円は1.0%枠（1000円）以内と**算術上**表示される。しかし、出力は無条件で`NO_GO`、`BLOCKED`、注文/SL解除不可。失敗系として500.01円と1000.01円も厳密超過判定する。

上記quote損失自体が外部からの**架空の自己申告値**であり、実ブローカーSL、価格急変、最小lot・契約単位、スリッページによる最大実損失は評価していない。プログラムが算出した「損失上限」と読み替えてはならない。各費用の`INCLUDED_IN_BASE`も合成入力側の主張であり、真正な会計証拠ではない。

## 3. 重要な拒否条件

- USD/JPYなど対象3ペアのbid/ask・snapshot_id・epoch・口座通貨の整合性が欠ける、クロス・逆転・不正数値、EUR/USD quote currencyをJPYと偽る
- 4つの費用項目が欠ける、重複する、`ADDITIONAL`と`INCLUDED_IN_BASE`の旗が矛盾する、負数/NaN、確認されていないギャップを有限と決めつける
- broker・pending・inflight・通貨露出の状態が一致しない、スナップショット世代が違う、`DISPATCHING`・取消中・発注結果不明を既知として扱う
- 予約・未約定・反対方向の建玉を相殺して損失枠を増やす、同じsliceを二重登録する、分割約定のFILLED/REMAINDERが欠落・重複/銘柄不一致
- lotのmin/step/maxに反する数量、浮動小数点・指数・無効な金額、500.01/1000.01を丸めて上限以下と誤認する

本人承認待ち20項目は`specs/risk_3p_08_12_form03_07_batch_review_20261104.json`で**すべてNOT_RECORDED**と記録。安全重要コードの仕様変更をこのPRで承認することはない。既存日次1.5%、DD4%新規停止、DD5%全決済・本人解除要件を変更しない。

## 4. 生成物とゲート

- `scripts/phase1_form03_07_synthetic_bundle.py`：合成3ペアUSD→JPY換算・費用項目・同一スナップショット・非相殺損失・Decimal境界の純粋関数。プログラムによる本番/デモ発注機能なし。
- `tests/test_risk_3p_08_12_synthetic_bundle.py`：正常例もNO_GO、欠損/不整合/偽の費用根拠/部分約定/同時注文/限度額超過を確認する負試験。
- `specs/risk_3p_08_12_form03_07_batch_review_20261104.json`、`scripts/audit_risk_3p_08_12_owner_batch.py`、`tests/test_risk_3p_08_12_owner_batch.py`：5未決FORM・20未決選択肢・通貨ペア・リスク・承認ラッチを静的に監視。
- `specs/traceability.json`、`tests/test_phase1_way_e_audit.py`：Q109のsource/test対応を`production_authorized=false`として追加。

## 5. 未解決と次の段階

**実際に判断を要するのは** FORM-01の契約実証、FORM-02のSL形状・安全仕様、FORM-03の換算方法、FORM-04の費用/ギャップ、FORM-05/06の実注文と予約の照合、FORM-07の数量/金額の端数、FORM-08〜10のNY17/ DD/時刻の実装詳細、G1 3×5の実ブローカー証拠、FX-SAFの原議照合・承認。

今後は関連工程を**同じ開発ブランチ・PRに追加し、関連テストが揃ってから1回のレビュー/手動マージ**に集約する。実際の発注機能、停止解除、ブローカー接続、G1承認等の高リスクな境界を一括PRで自動的に越えない。今後の文書レビュー・安全設計も、PRマージと安全重要仕様の本人承認を別記録とする。

再現手順：
```text
python -m unittest tests.test_risk_3p_08_12_synthetic_bundle -v
python -m unittest tests.test_risk_3p_08_12_owner_batch -v
python scripts/audit_risk_3p_08_12_owner_batch.py
python -m unittest discover -s tests -p "test*.py"
python scripts/check_traceability.py
python scripts/check_phase1_way_e.py
```

**不変：** FX-SAF-001〜015未承認、G1〜G9 UNRESOLVED、PHASE-1 BLOCKED、runtime NO_GO、safety_hold_latched=true、verified_values=null。現時点で楽天MT4やAWS/Azureを操作していない。