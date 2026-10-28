# P0-01 D4-4 オフライン監査・回帰テスト記録

- 日付：2026-10-28
- 対象：D2 / D4-1 / D4-2 / D4-3の純Pythonオフライン検証経路
- 変更：監査用の単体テストと本文のみ。MT4・EA・口座・実測値・発注コードを変更しない
- 前提：PR #111はmainへマージ済み、本人報告のWindowsローカル463件OK、GitHub CI成功
- 本PRのCIおよび追加テスト：作成時点では未検証。結果を確認するまでマージ禁止

## 監査の対象と限界
1. Git管理下の `specs/p0_01_mt4_readonly_observation_plan.json` における4ペア×5属性の `verified_values=null` および `production_usable=false` を確認する。
2. D2設計ファイルの `phase_1=BLOCKED`、発注・実行・人間承認フラグがfalseであることを確認する。
3. D4-2 `deny_all` の出力を改変したとき `invariant_holds` が拒否することを確認する。
4. 合成データや手入力候補へ権限値を注入しても、実際の売買承認に昇格しないことを確認する。
5. オフライン検査コードに危険なMT4・ネットワーク・注文APIが静的に混入していないことを確認する。

監査は**現在の対象ファイルに対する回帰テスト**に限り、リポジトリ全体の全コード経路や将来の開発を機械的に完全保証するものではない。定期的な人間レビューとCIが必要。

## 絶対に変更しない安全条件
- `PHASE-1 BLOCKED`
- `broker_verified=false`、`production_usable=false`
- `orders_generated=false`、`terminal_execution_approved=false`
- `forward_trading_enabled=false`
- 新規デモ口座、既存建玉/注文、MACD Sample、EX4実行には触れない
- 合成値と未検証候補をBrokerの実測認証に自動昇格しない

## 次工程の判断基準
GitHub Repository checksとWindows Python3.13の双方の成功、本人Windowsローカルテスト成功、PR差分の本人レビューを経て、手動マージとする。実ブローカー照合やMT4起動は別途明示承認が必要。
