# RISK-3P-03: 新3ペア MT4契約属性の非破壊オフライン入力テンプレートと検証

作成日 2026-11-04。前提：PR #170・#172・#173マージ後。RISK-3P-02で旧4ペア前提のコード・台帳・テンプレを棚卸し済み。

## 0. 権限・受入の境界
本工程はUSD/JPY・EUR/JPY・EUR/USD専用の**未検証データ入力テンプレート**と入力形式の**オフライン検査**のみ。AWS/Azure、楽天MT4、Windows端末、ブローカー口座への接続・実験、資金の移動、鍵発行、注文、STOP解除を行わない。新しい数値を確定せず、旧4ペアの元データやローカル観測ファイルを上書きしない。

G1の現行台帳は4ペア×5項目のままUNRESOLVED。新3ペア×5項目は将来の**設計対象15項目**であり、G1受入済み、値取得済みの証拠ではない。すべての出力は`runtime NO_GO`、`PHASE-1 BLOCKED`、`safety_hold_latched=true`、`verified_values=null`。FX-SAF-001〜015は未承認。

## 1. 新設ファイル
| ファイル | 用途 |
| --- | --- |
| `specs/mt4_manual_symbol_3p_v3_template.json` | 3ペアに限定。各銘柄に旧v2と同じ11個の数値属性・表示属性、実際のターミナル銘柄名・UTC観測時刻・データ種別を**すべてnull**で定義 |
| `scripts/review_mt4_manual_symbol_3p_v3.py` | 外部データ取得を行わない入力形式・数値整合・文字列スキーマの検査、秘匿値非表示、Git内の実観測ファイルを拒否 |
| `tests/test_risk_3p_03_symbol_v3.py` | 合成データのみの負試験。欠損、旧4ペア混入、偽証拠、数値桁、bid/askとは別の属性と時刻、個人情報、コマンドライン出力を確認 |
| `specs/traceability.json` とWay Eテスト | production_authorized=falseの紐付けと旧オフライン登録を維持 |

## 2. 主要5項目（1ペアあたり）
| キー | 意味 | 検証の限界 |
| --- | --- | --- |
| `min_lot` | 最小取引ロット | 実MT4ルールや口座資金で約定可能とは主張しない |
| `lot_step` | ロットの増分 | min_lot以下など、**算術的整合のみ** |
| `point_quote` | 価格1ポイント分の通貨単位 | digitsが入力されれば10^-digitsとの一致を確認。業者の価格定義を保証しない |
| `tick_size_points` | 1tickに相当するpoints | point_quoteとの積の形式検査のみ |
| `tick_value_deposit_currency` | デポジット通貨換算tick価値 | 実データによる証拠も口座通貨・lot単位も未検証 |

補助欄として`lot_size_base_units`、`max_lot`、`digits`、`stop_level_points`、`freeze_level_points`、`spread_points`を残す。FLOATING表示を数値スプレッドとみなさない。後続のQ116実装にはこれらの追加属性、注文約定状態、bid/ask側の正確な円換算などが不可欠であり、本工程で確定させない。

各ペアの`observation`には、実端末に表示される正確な`terminal_symbol`（将来確認）、実観測の`observed_at_utc`（YYYY-MM-DDTHH:MM:SSZ）、`source_kind=MANUAL_MT4_SPECIFICATION`を記すことを**将来の別承認後の入力仕様として**想定。ただし記載されていても、真正な証拠・最新値・口座属性であるという保証はなく、現在はすべてnull。

## 3. 返却状態
| 状態 | 意味 | 権限 |
| --- | --- | --- |
| `REVIEW_REQUIRED` | 3ペア集合不一致、追加/欠落キー、数値不正、証拠文字列の構造不正など | NO_GO |
| `INCOMPLETE` | 5項目または対応観測欄がnullで未入力 | NO_GO |
| `FIVE_FIELDS_PRESENT_UNVERIFIED` | **架空の例であっても**5属性と観測メタデータが入力形式上揃っただけ。実MT4事実確認ではない | NO_GO |

どの状態でも`broker_queried=false`、`production_authorized=false`、`broker_contract_verified=false`、`g1_real_world_verified=false`、`order_allowed=false`、`automatic_retry_allowed=false`、`stop_release_allowed=false`、`verified_values=null`。

## 4. 個人観測値の保護と既存ファイルの扱い
テンプレートを直接編集してGitにcommitしない。将来、**別途承認された範囲で**取得したプライベート観測値を取り扱う場合、リポジトリ外に保存し、GitHub、Issue、CIログ、ChatGPTに生値・口座識別子・資格情報・ログ・スクリーンショットを持ち込まない。コマンドラインチェックはファイルを読むだけで、ファイルの新規作成や上書きを行わない。出力は既知の属性名と固定ステータスだけ。読み取り前に外部パスと64KiB上限をチェックする。

形式チェックの構文：`python -m scripts.review_mt4_manual_symbol_3p_v3 --input <Git外のプライベートJSONパス>`（今は実観測ファイルの作成/収集を要求しない）。exit code 1=REVIEW_REQUIRED、2=INCOMPLETE、3=FIVE_FIELDS_PRESENT_UNVERIFIED。**exit code 0を設けない**ため、CLIが返す値を誤って証拠承認の成功判定に使用できない。

旧`specs/p0_01_mt4_manual_symbol_template.json`、`..._v2.json`、`scripts/mt4_manual_symbol_v2.py`、旧4ペア検査と既存のローカル`mt4_symbols_local.json`等は変更しない。GBP/USD・AUD/USDの過去資料をEUR/USDの代替として移入しない。

## 5. 次の工程
RISK-3P-04：旧4ペアのローカルv1/v2入力の保管方針と3ペアV3との非破壊移行案、EUR/USD新規手入力をUNKNOWNのまま保持、USD建てEUR/USDをJPYに換算する方向・bid/ask・時刻・有効期限とQ116損失算式を**正式な安全仕様承認前の設計課題**として検証。G1の実証スコープ改版や実MT4閲覧は別々の明示承認が必要。

### 再検査
- `python -m unittest tests.test_risk_3p_03_symbol_v3 -v`
- `python -m unittest discover -s tests -p "test*.py"`
- `python scripts/audit_risk_3p_02_migration.py`
- `python scripts/check_traceability.py`
- `python scripts/check_phase1_way_e.py`

本PRのCI成功は静的検査・合成モデルの成功であり、ブローカー契約値を検証したことや本番売買の許可ではない。