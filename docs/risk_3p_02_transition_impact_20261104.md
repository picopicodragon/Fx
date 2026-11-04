# RISK-3P-02：3ペア移行影響監査と旧4ペア互換性境界

作成：2026-11-04。基準main：PR #172マージ後 `95cea668504b1377e5e6e3e5d12ef666bc8049dd`。

> **移行範囲の棚卸しであり、実装変更・G1再受入・楽天MT4実測・運用許可ではない。** Q3の旧4ペアは歴史的事実として保持し、2026-11-04の本人指示による新3ペア `USD/JPY`、`EUR/JPY`、`EUR/USD` を将来の設計対象とする。

## 調査結果
GitHubのmainのツリー、関連Pythonソース・MQL4読み取り専用ソース、テスト、JSON台帳、設計文書を調査した。確認結果は `specs/risk_3p_02_transition_impact_20261104.json` に個別のファイル名・カテゴリ・対応方針・理由とともに記録。リポジトリ全ファイルを原議照合したものではない。

| 分類 | 代表的な対象 | 現在の扱い |
| --- | --- | --- |
| 旧4ペアを前提とする検査コード | `scripts/validate_mt4_manual_symbol_specs.py`：EXPECTED_PAIRSに旧4ペア、要素数4 | 新3ペア専用の別版を必要とする。旧版は変更しない |
| 旧4ペア v2移行ツール | `scripts/mt4_manual_symbol_v2.py`：旧定数をimportし、要素数4 | ユーザーのローカルv1/v2入力を上書きせず、後続に非破壊3ペア版を設計 |
| 旧5属性検査と円換算fixture | `scripts/p0_01_offline_five_field_mock.py`、`scripts/p0_01_d5_3_synthetic_contract.py` | EUR/USDのUSD建て損失とJPY換算の扱いを別途設計 |
| 旧MQL4 read-only | `mt4/read_only/P0_01_ManualSymbolSnapshot_ReadOnly.mq4` とその静的監査 `scripts/audit_mt4_readonly_source.py` | 旧4入力の履歴として保全。新3ペアのMQL4設計・実行は別承認 |
| 旧テスト | MT4シンボルv1/v2、D5-3、MQL4ソース監査、公開証拠検証 | 回帰保証として残す。新3ペアは別テスト/別fixtureで検証 |
| 旧仕様・テンプレ | `specs/p0_01_mt4_manual_symbol_template.json`、`...template_v2.json`、`...five_field_offline_mock_design.json` | 元ファイルは改変せず、3ペア版を別名で追加する |
| 正式未解決ゲート | `specs/p0_01_d5_25_gap_verification_matrix.json`、D5-26優先計画 | 現行G1の旧4×5=20項目はBLOCKED。新設計は3×5=15項目に変更予定だが正式受入や実証は別判断 |
| 旧公開契約根拠・観測計画 | `specs/p0_01_rakuten_mt4_public_contract_evidence.json`、`...mt4_readonly_observation_plan.json` | EUR/USDの契約値や実口座の同一性について根拠なし。過去の記録を捏造して補完しない |
| 現行3ペア合成算術 | `scripts/phase1_three_pair_synthetic_risk.py`、対応テスト | 正しい3ペア集合だが実損失算式の承認/MT4注文許可ではない |

## 重要な差異と未決事項

1. **G1はまだ4ペア×5属性のまま**。旧20項目の未取得/未受入が3ペア化で自動的に解決するわけではない。本人の変更承認を伴う正式ゲート・証拠台帳の改版後も、実契約属性が確認されるまでG1 UNRESOLVEDのまま。
2. **EUR/USDに必要なブローカー証拠がない**。正確なMT4銘柄表示、suffix、最小lot、lot step、契約サイズ、tick value、stop/freeze level、取引時間・JPY換算の価格証拠を新規確認する必要がある。
3. **旧GBP/USD・AUD/USDの公開根拠・検証fixtureは新EUR/USDの根拠にならない**。旧文書を上書きせず、異なる証拠時点/単位を混同しない。
4. **EUR/USDのP&L/SLの円換算**は、USD建て結果をUSD/JPYの適切なbid/askで換算する一連の証拠、スプレッドや手数料、同時時刻、口座通貨を確認する必要がある。単純に「quote=USD」と追加しただけでは安全算式にならない。
5. **三角関係によるネット0はリスク0ではない**。Q116の0.5%/1.0%非相殺円換算審査、未約定注文の全約定想定、単一通貨の集中・グロス・ストレスの算式と本人承認が必要。
6. **旧4ペアテストがPASSしても新3ペア契約検証済みを意味しない**。旧fixtureは旧仕様回帰試験のままとし、新スキーマ/証拠/テストを分離する。

## 追加した検査
- `scripts/audit_risk_3p_02_migration.py`：設計対象3ペア、歴史的Q3、対象15属性と旧20属性、旧コード一覧、未実装/未承認状態、既存G1のBLOCKED、3ペア合成テストのみの権限境界を静的検査。
- `tests/test_risk_3p_02_migration.py`：新3ペアからの逸脱、旧Q3の改変、偽のGO/受入、4ペアコードの登録漏れ/誤分類、欠落文書等を拒否。
- 旧ソースをすべて置換するのではなく、`scripts/`と`mt4/`に残る旧ペア名の参照を監査台帳と照合。旧4ペアコードの登録漏れはエラーとする。静的文字列検査は動的生成されるコード/名前を全て検知できない。

## 推奨移行順
| ステップ | 次工程 | 承認境界 |
| --- | --- | --- |
| RISK-3P-03 | 新3ペアのオフライン入力スキーマ/fixtureと非破壊validator案。EUR/USD未検証属性は`UNKNOWN`として拒否 | 合成設計のみで可能 |
| RISK-3P-04 | 旧版との互換テスト、Q116計算の仕様・個別JPY換算・同時注文リスクの審査 | 安全重要仕様は本人承認が必要 |
| G1スコープ改版 | 20項目→15項目の正式な証拠/受入マトリクス改版 | 本人による差分と安全ゲート審査が必要 |
| H2/H4等 | 将来の単一MT4閲覧、独立Trust Anchor/OS試験 | 環境/アクセス権/操作範囲は毎回別途承認 |

## 維持する安全状態
FX-SAF-001〜015は全件実装未承認。G1〜G9 UNRESOLVED、PHASE-1 BLOCKED、runtime NO_GO、safety_hold_latched=true、verified_values=null。1取引0.5%、同時合計1.0%、日次1.5%、DD4%新規停止/DD5%到達の本人承認停止は変更しない。新口座/同時MT4/EA/EX4/発注/停止解除/鍵操作を実施しない。欠落原議追跡は保留のまま。

検査コマンド：`python scripts/audit_risk_3p_02_migration.py`、`python -m unittest tests.test_risk_3p_02_migration`、`python -m unittest discover -s tests -p "test*.py"`、既存のRepository/Way E/traceability検査。PRのCIは安全実装承認を代替しない。