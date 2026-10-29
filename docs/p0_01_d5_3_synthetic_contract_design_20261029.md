# P0-01 D5-3：合成契約単位・口座通貨・ロット刻み整合性テスト

作成：2026-10-29。楽天証券の実測データは一切使用しない。

## 目的
D2の4ペア×5属性の合成入力に対し、**追加の仮定を明示した**契約数量と通貨単位の内部整合を検査する。ロット刻みは例示的にmin_lotを起点とする。実際のMT4の発注可能刻みの起点は別途ブローカー検証が必要。

## 合成テスト専用追加情報
- `origin=SYNTHETIC_ONLY`、`account_currency`、`quote_currency`
- `contract_size_base_units_per_lot`、`quote_to_deposit_synthetic_rate`（架空の換算係数）
- `tick_value_basis=PER_1_LOT`、`requested_lots`。
- 通貨一致の場合、合成換算係数は1。
- 仮定の式：`contract_size_base_units_per_lot * point_quote * tick_size_points * quote_to_deposit_synthetic_rate = tick_value_deposit_currency`。この等式は合成入力の自己整合性用であり、実ブローカーの評価式と断定しない。

## 厳格な制限
- 合成換算係数は**市場レートではない**。決してリアルタイム為替レートや注文ロット算出に使用しない。
- 合成PASSは `SYNTHETIC_CONTRACT_CONSISTENT_NEVER_VERIFIED`。BROKER_VERIFIEDとはしない。
- 任意の入力異常、通貨不一致、換算係数欠落、刻み不一致、tick value不整合は安全側の`REVIEW_REQUIRED`または`INCOMPLETE`。
- 表示するのは固定ステータス/falseフラグのみ。口座番号や実測値を保存・出力しない。
- `PHASE-1 BLOCKED`、実端末・口座・EX4起動・MarketInfo・発注は引き続き禁止。
- このD5-3は独立した合成検証であり、D4-2の承認禁止ゲートを改修して取引を許可する機能ではない。

## オフライン回帰テスト
正常な合成値、口座通貨一致/不一致、契約数量、ロット刻みと最低ロット、tick size、欠損、無効数値、承認偽装、秘密文字列非出力、入力の不変性を確認。

G1/PF1の独立デモ同時保持の証拠不足は解消しないため、実環境移行はNo-Goのまま。
