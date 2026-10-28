# P0-01：完全オフライン5属性モック検証 設計 v1（2026-10-28）

**現在の成果は実装設計のみ。モック値の生成処理・新しい本体コードはまだ作成しない。MQL4コンパイル・MT4接続・EX4実行・注文の許可を含まない。**

## 1. 現在の到達点

- GitHubのPR #105までmainにマージ済み。ユーザーWindowsで**421 tests / OK**を報告。
- 楽天MT4デモで別口座を同時保持できるか不明。楽天公式のMT4デモ口座の利用サポート対象外の制約により、既存デモの再作成/入替による影響を排除できない。新規MT4/デモ環境は触らない。
- 現状のデモMT4にはチャート装着`MACD Sample`と既存建玉または未約定注文あり。口座は変更せず、読取専用EX4は`FxLocalReview/CompileOnly`のまま。
- 本番想定資金100,000円と楽天MT4デモ初期資金5,000,000円は別物。どちらの数値も実口座安全性を裏付けるものではない。

## 2. モック仕様の入力と出力

対象は`USD/JPY`・`EUR/JPY`・`GBP/USD`・`AUD/USD`の4ペア、各5属性（計20件）。

| フィールド名 | MQL4 API定数 | 単位 | オフライン検査 |
| --- | --- | --- | --- |
| `min_lot` | `MODE_MINLOT` | lot | 有限正の十進文字列のみ |
| `lot_step` | `MODE_LOTSTEP` | lot刻み | 有限正、min_lotとの不整合を検出 |
| `point_quote` | `MODE_POINT` | クオート価格の1point | 有限正、`digits`との検証は別証拠が必要 |
| `tick_size_points` | `MODE_TICKSIZE` | 1tick当たりのpoint数 | 有限正、`point_quote`と混同しない |
| `tick_value_deposit_currency` | `MODE_TICKVALUE` | 口座通貨建てtick価値 | 有限正でも**口座通貨/契約単位の独立証拠がなければ未検証** |

検証は**Python標準ライブラリ・純粋関数・メモリ上の合成フィクスチャのみ**。既存`scripts/validate_mt4_manual_symbol_specs.py`の`safe_decimal()`（Decimal文字列、float拒否）を再利用するか相当条件を満たす。不正文字列・`nan`・`Infinity`・0・負値・長大入力・bool/int/floatの混入・不明/重複銘柄・余計なフィールドは**fail-closed**。

戻り値は`field_name`と`INCOMPLETE`/`REVIEW_REQUIRED`/`SYNTHETIC_CHECKS_PASS_NEVER_VERIFIED`などの固定ステータス**のみ**。検証値自体をログへ出さない。

`SYNTHETIC_CHECKS_PASS_NEVER_VERIFIED`は実データが存在する・Broker照会に成功した・投資判断に利用可能という意味ではない。モック値を`specs/p0_01_mt4_readonly_observation_plan.json`の`verified_values`やローカル`mt4_symbols_local.v2.json`へ転記しない。GitHubに実際の口座・ログやモックの「実観測を装う」JSONをコミットしない。

## 3. 検証シナリオ

1. 合成の4×5組がすべて正の有限Decimal文字列のケース：形状検証PASS。ただし**本物として利用不可**。
2. 20項目のうち各項目の`null`、空欄、欠落：`INCOMPLETE`またはスキーマ不正として停止。
3. `0`、負値、`NaN`、`Infinity`、オーバーフローにつながる極端な指数値、bool/int/float：`REVIEW_REQUIRED`。現実性のない巨大正値も単なる有限正だけでは安全を証明せず、ビジネス範囲や独立証拠を要求する。
4. `lot_step > min_lot`など単位・ロット関係の不整合を拒否。**合成の正常値から最小ロットや刻みを補完・推測しない**。
5. `point_quote`と`tick_size_points`を混同すると価格tick幅の計算が変わることを合成例で検出。関係式は`tick_price_increment = point_quote * tick_size_points`。
6. `MODE_TICKVALUE`は口座通貨・1lot等の契約単位を仮定して損益計算に利用しない。口座通貨が未確認なら`FORM-03=UNVERIFIED`。
7. 仮想10万円のリスク上限は、1取引500円・同時1000円・日次1500円・過去最高純資産からのDD 5%であり、デモ500万円の値に引っ張られない。DD 5%到達の一時停止・人間承認という仕様を変更しない。
8. 20項目すべてのモックがPASSでも、**MT4接続不可、EX4の実行不可、新規注文不可、本番許可不可**。
9. 例外発生・スキーマ不整合時は固定エラーコードで判定し、入力値/ユーザーの実ファイル内容/口座情報を出力しない。

## 4. 実装ファイル構成（次のPRで提案、今回は作成しない）

- `scripts/p0_01_offline_five_field_mock.py`：Python純粋関数。MT4・ネットワーク・ファイルI/Oの実装禁止。公式値を断定しない。最終判定は常に`...NEVER_VERIFIED`。
- `tests/test_p0_01_offline_five_field_mock.py`：決定論的な合成フィクスチャだけで異常値、重複/欠損、単位、禁止条件を網羅。実口座値は一切使用しない。
- `specs/p0_01_five_field_offline_mock_design.json`：本設計の機械可読条件。

これらの新規実装は**別PR**とし、Linux Python 3.12、Windows Python 3.13双方のCI、自動売買・FXリスク変更なし、Q109のトレーサビリティを確認してから本人が手動マージする。

## 5. ゲート

| 工程 | 状態 |
| --- | --- |
| D1 設計・条件整理 | 今回のPRでレビュー待ち |
| D2 純Pythonモック検査コード実装 | 未着手 |
| D3 CI・危険なI/O呼び出し混入検査 | 未着手 |
| D4 ブローカー実測値との照合 | 未承認、当面不可 |

**重要：** 既存`scripts/mt4_manual_symbol_v2.py`は既にローカルの手入力確認票を検査できるが、手入力と合成モックを混在させない。モックの合格を実測値や本番売買承認へ自動昇格させない。

`PHASE-1 BLOCKED`、`terminal_execution_approved=false`、`forward_trading_enabled=false`、`implementation_approved=false`、`human_safety_approval=false`を維持する。
