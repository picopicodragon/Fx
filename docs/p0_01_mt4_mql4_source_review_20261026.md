# P0-01：MT4読取専用MQL4スクリプトのソースレビュー（2026-10-26）

**本人承認の範囲：作成のみ。** 2026-10-26の「承認する」は、4通貨ペア5属性の**MQL4ソースコードを作成してPRに載せることだけ**を許可する。**コンパイル、MT4端末へのコピー、起動、実端末データ取得、取引・決済・注文変更・自動売買実装の承認ではない。**

## 1. 作成物

- ソース：`mt4/read_only/P0_01_ManualSymbolSnapshot_ReadOnly.mq4`。MT4の`MQL4/Scripts`ディレクトリ**外**に保存し、GitHubにレビュー可能なプレーンテキストとして登録する。
- 静的監査：`scripts/audit_mt4_readonly_source.py`。禁止関数、デフォルト停止、5属性と4ペア対応の静的チェックだけを行う。MetaEditorのMQL4コンパイラに代わるものではない。
- 回帰テスト：`tests/test_p0_01_mql4_readonly_source_audit.py`。無効化したソースの模擬改変をテストする。**MQ4の実行も外部通信もない**。

### 対象の5属性

| 手入力v2のキー | MQL4で参照する属性 | 単位・注意 |
|---|---|---|
| `min_lot` | `MarketInfo(symbol, MODE_MINLOT)` | ロット |
| `lot_step` | `MODE_LOTSTEP` | ロット刻み |
| `point_quote` | `MODE_POINT` | 価格表示の1ポイント |
| `tick_size_points` | `MODE_TICKSIZE` | **ポイント単位のティック幅** |
| `tick_value_deposit_currency` | `MODE_TICKVALUE` | MT4公式APIでは口座通貨建てのティック価値。単位・ロット換算と時価変動の検証が別途必要 |

対応ペアは`USDJPY`、`EURJPY`、`GBPUSD`、`AUDUSD`（MQL4実シンボル表記）。**スラッシュ付きの`USD/JPY`等はv2の論理名**。端末の実シンボルに接尾辞や特殊表記がある場合は、本人による別の確認を要する。入力欄は存在するが、デフォルトが実際のブローカー銘柄名と一致する保証はない。

## 2. ソースの安全ガード

1. `#property strict`、`#property script_show_inputs`を指定した**一回限りのScript**（EA・タイマーではない）。`OnStart`以外のイベントハンドラは作らない。
2. `InpExplicitReadApproval = false`で初期状態は即時終了。**今はこの値を変更しない。**
3. `IsConnected()`で状態を確認し、未接続なら属性照会へ進まない。接続操作は一切行わない。
4. 事前に4つの論理ペアとシンボル名の対応・重複を確認。`SYMBOL_SELECT`は**状態の照会**であって、`SymbolSelect()`によるMarket Watchの追加/削除はしない。未選択なら拒否する。
5. `MarketInfo`以外の契約属性呼出し、売買注文操作、DLL、Web通信、ファイル書込、自動保存、通知送信、スクリーンショット、口座番号/氏名/残高の取得はしない。
6. 読取に失敗、ゼロ・負値・無限大・NaN、エラーなら`UNVERIFIED`。5属性のうち1件でも未確認ならそのペアを`INCOMPLETE_DO_NOT_USE`と記録する。
7. 成功時でも`OBSERVED_NOT_VERIFIED`であり、金融リスク計算の承認ではない。`MODE_TICKVALUE`は通貨換算・時価などの独立検証が必要。
8. **ローカルMT4のExpertsログへ`Print`される構造**。本スクリプト自身はファイルを書かないが、MT4自身がローカルログを保持する可能性がある。ログを丸ごとGitHubへアップロードしない。今は出力を発生させる実行をしない。

メッセージの先頭は`MT4_RO`。コンパイル可能性・4ペアの属性の実際の取得成功・サーバーTZ・価格鮮度・口座通貨は**検証していない**。取得された値も完全な真正性証明ではない。

## 3. 今回実行できる作業（WindowsのPythonのみ）

GitHub PRをレビューして手動マージした場合に限り、Fxルートで以下は**MQL4のコンパイル/起動なし**で実行できる。

```powershell
python scripts/audit_mt4_readonly_source.py
python -m unittest discover -s tests -p "test*.py"
```

`PASS`は静的な文字列/関数構成のチェックに過ぎず、MQL4コンパイラによる構文検査ではない。MetaEditorを使ったコンパイルやMT4ターミナルの読取実行は**現在承認されていない**ため、コマンド/配置手順は今回案内しない。

## 4. 次の承認で別途検討すべき条件（現時点未承認）

コンパイル可否、端末の銘柄名（接尾辞）、Market Watchの選択状態、対象口座の区分、ログに記録される情報の取扱い、取得の際の通信と権限制御、数値精度（表示の12桁小数）、ロット・ティック値の換算、サーバー時刻とNY17/DSTの相違、取得結果の再現性を本人がレビューする必要がある。

取得した5つの値を人間が`mt4_symbols_local.v2.json`に転記する工程も、独立検証と元の入力データ保護の条件を決めるまでは**自動化しない**。`INCOMPLETE`をゼロ埋めや公開値の推測で回避してはならない。

公式一次資料：
- [MQL4 MarketInfo](https://docs.mql4.com/marketinformation/marketinfo)
- [MQL4シンボル属性](https://docs.mql4.com/constants/environment_state/marketinfoconstants)
- [MQL4スクリプトOnStart](https://docs.mql4.com/basis/function/events)
- [SymbolSelectはMarket Watchへの追加/削除を伴う](https://docs.mql4.com/marketinformation/symbolselect)
- [IsConnected](https://docs.mql4.com/check/isconnected)
- [MathIsValidNumber](https://docs.mql4.com/math/mathisvalidnumber)

**変わらない安全状態：** FORM-01/FORM-03保留、`implementation_approved=false`、`human_safety_approval=false`、`owner_approved_for_safety=false`、`forward_trading_enabled=false`、PHASE-1 BLOCKED。
