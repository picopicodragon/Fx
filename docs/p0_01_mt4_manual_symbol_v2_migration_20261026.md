# P0-01：MT4手動確認票 v2・既存入力の安全な移行（2026-10-26）

> 対象：ローカルに入力済みの`mt4_symbols_local.json`（v1）。**既存の数値を上書きせず、別名のv2ファイルを作る。** GitHub上の旧テンプレートと既存v1チェッカーは継続利用できる。MT4ログイン・EA実行・新規注文・データ送信は行わない。

## 変更理由

実際のMT4「気配値表示 → 仕様」には、既存v1確認票で表現できないスプレッド種別（フローティング）、証拠金通貨、利益/証拠金計算モード、ヘッジ証拠金、証拠金率、取引・執行・GTCモード、曜日別取引時間が表示される。一方で`MODE_TICKVALUE`、`MODE_LOTSTEP`、`MODE_TICKSIZE`は必ずしも画面にない。**表示されていない値を公式資料から推測して入力しない。**

## 1. 対応表：MT4表示項目とv2の入力位置

| MT4「仕様」 | v2 JSONのキー | 入力規則 |
|---|---|---|
| スプレッド：フローティング | `display_properties.spread_mode` | `"FLOATING"`。固定と確認できた場合のみ`"FIXED"`、不明なら`null` |
| スプレッド：観測数値 | `properties.spread_points` | 数値文字列または`null`。**フローティング表示だけなら`null`** |
| 小数桁 | `properties.digits` | 例`"3"` |
| ストップレベル | `properties.stop_level_points` | 数字。ゼロでも動的制限がないとはいえない |
| 契約サイズ | `properties.lot_size_base_units` | 例`"100000"`（画面の値のみ） |
| 証拠金通貨 | `display_properties.margin_currency` | 例`"USD"`、3文字の英大文字。口座の基準通貨とは異なり得る |
| 利益計算モード | `display_properties.profit_calculation_mode` | 画面の表示をそのまま文字列（コード値の推定なし） |
| 証拠金計算モード | `display_properties.margin_calculation_mode` | 同上 |
| 証拠金ヘッジ | `display_properties.hedged_margin_display` | 表示内容をそのまま文字列（数値/単位の解釈を保留） |
| 証拠金率 | `display_properties.margin_rate_display` | 表示内容をそのまま文字列（例`"4%"`、仮定例） |
| 取引 | `display_properties.trade_mode_display` | 画面の表示をそのまま |
| 執行 | `display_properties.execution_mode_display` | 画面の表示をそのまま |
| GTCモード | `display_properties.gtc_mode_display` | 画面の表示をそのまま |
| 取引時間（日～土） | `display_properties.trading_hours_display.sunday`～`.saturday` | 各曜日の表示をそのまま文字列。休止も`"Closed"`等の実表示を転記 |

v2でも従来の`properties.min_lot`、`lot_step`、`max_lot`、`point_quote`、`tick_size_points`、`tick_value_deposit_currency`、`freeze_level_points`を残す。**実際のMT4画面で確認していなければnull。** v1で入力した値は全てそのまま移行し、後から上書きしない。

## 2. 既存ファイルを残してv2を生成

PRマージ後、`Fx`フォルダーのPowerShellで：

```powershell
git switch main
git pull --ff-only origin main

$reviewDir = Join-Path $env:USERPROFILE "Documents\FxLocalReview"
$reviewFile = Join-Path $reviewDir "mt4_symbols_local.json"
$v2File = Join-Path $reviewDir "mt4_symbols_local.v2.json"

python -m scripts.mt4_manual_symbol_v2 migrate --input $reviewFile --output $v2File
```

`mt4_symbols_local.json`は読み取り専用で**一切変更しない**。出力が既存の場合、別ファイルであっても上書きせずエラー終了する。入力JSONが想定外の形式/値であれば`REVIEW_REQUIRED`として、v2ファイルを生成せず元のままにする。**v1とv2の個人観測値をGitHubへコミットしない。**

元のv1に`"spread_points": "フローティング"`がある場合、これは数値フィールドとして不正なので**先にv1をローカルで明示的に`null`へ修正**し、移行後に`display_properties.spread_mode`へ`"FLOATING"`を入力する（旧値のバックアップを個人の管理下で保持）。

### Windowsで `ModuleNotFoundError: No module named 'scripts'` が出る場合

v2初版の`python scripts/mt4_manual_symbol_v2.py migrate ...`は、Windowsで直接起動すると内部の`from scripts... import`に失敗する不具合があった。原因は`python <ファイルパス>`と`python -m <パッケージ名>`でPythonのモジュール検索開始位置が異なるためである。

**Fxリポジトリのルート**で`python -m scripts.mt4_manual_symbol_v2 migrate ...`を使用する。修正版では従来の直接起動方法でも同じ処理を行えるよう調整し、両方式のCLI起動・実際のオフライン移行をWindows/Linuxの自動テストで検査する。単に`sys.path`へ任意フォルダーを追加したり、ユーザーのPython設定を変更したりする必要はない。

このImportErrorは移行処理の開始前に発生するため、元のv1入力データは書き換わっていない。既存のv2出力がある場合は**絶対に上書きせず**、どの段階で生成されたか本人が確認する。

## 3. v2に未入力の画面表示だけを補う

```powershell
notepad $v2File
python -m scripts.mt4_manual_symbol_v2 check --input $v2File
```

すべての数値は浮動小数型ではなくJSONの文字列（例`"100000"`）とする。追加の表示項目は原文の文字列でよい。日曜～土曜の時間表示は各キーに分ける。存在しない情報を`0`、`"UNKNOWN"`、既存ルールの推定値に置き換えず`null`にする。例えばスプレッド欄が**フローティング**とだけ表示されるペアには：

```json
"properties": {
  "spread_points": null
},
"display_properties": {
  "spread_mode": "FLOATING"
}
```

上記は**関連キーだけの説明であり、そのままJSONへ貼り付けて既存`properties`の11項目を置換しない**。

## 4. 判定結果

- `INCOMPLETE`（終了コード2）：必要な端末/ブローカー値などが未取得。**画面で読めない項目を無理に埋めない。**
- `REVIEW_REQUIRED`（終了コード1）：構文異常・型/項目数の不一致・浮動スプレッドへの数値誤投入・ブローカー公開単位との不一致など。**旧ファイルは変更しない**。
- `COMPARED_FIELDS_ONLY`（終了コード0）：手動入力の一部の形式・公開資料照合が通過しただけ。**実装・注文の安全承認ではない**。

端末に存在しないMQL4 API項目は将来の別途許可を得た読取り検証を要する。v2の取引モード・GTC・証拠金率・取引時間は**生の表示テキストの保存のみ**とし、執行権限やマージン算式に自動適用しない。タイムゾーンと取引日開始NY17、夏冬DSTの算式は変えない。

## 5. 既存環境・安全停止

v1テンプレート・チェッカーは既存利用者のため残す。新しい`specs/p0_01_mt4_manual_symbol_template_v2.json`と`scripts/mt4_manual_symbol_v2.py`だけを追加する。本人が現行v1入力済みのデータを破壊的に変換しないことを優先する。

**安全状態：** `implementation_approved=false`、`human_safety_approval=false`、`owner_approved_for_safety=false`、`forward_trading_enabled=false`、`PHASE-1 BLOCKED`。FX発注/注文更新・口座の自動読取は実施しない。

## 2026-10-26補足：移行時に原因不明のREVIEW_REQUIREDが出る場合

v2初版では、元のv1の型違い・公開契約の不一致・既存の出力ファイル・パスと読み取り問題等を同一の一般メッセージにまとめていた。修正版では、**入力された数値・原文を表示せず**、原因を固定コードと許可済みフィールド名で区別する。

まずリポジトリルートで次を実行する（読み取り専用）。

```powershell
$reviewDir = Join-Path $env:USERPROFILE "Documents\FxLocalReview"
$reviewFile = Join-Path $reviewDir "mt4_symbols_local.json"
$v2File = Join-Path $reviewDir "mt4_symbols_local.v2.json"

Test-Path $reviewFile
Test-Path $v2File
python -m scripts.mt4_manual_symbol_v2 diagnose --input $reviewFile
```

`diagnose`はファイルを作成・変更しない。`INCOMPLETE`はMT4画面にない項目が`null`のためで、移行そのものを禁止する理由ではない。`REVIEW_REQUIRED`は、以下のフィールド名や原因コードを本人が確認する。

- `INPUT_FILE_MISSING` / `OUTPUT_DIRECTORY_MISSING`：指定パスと保管先の存在を確認
- `INPUT_INVALID_JSON` / `INPUT_ENCODING_UNSUPPORTED`：JSONの構文や文字コードを確認
- `V1_SCHEMA_OR_FIELD_TYPES` / `EXPECTED_DECIMAL_STRING_OR_NULL`：v1の11項目は`"3"`など文字列か`null`。JSON数値`3`や余計なキーは形式不整合。**勝手な修正/削除はせず元データを別途控えてから対応**
- `PUBLIC_RULE_DIFFERS`：端末上の契約数量やPOINTが公開ルールと一致しない。ブローカー条件/転記を確認し、矛盾を隠す変更はしない
- `OUTPUT_ALREADY_EXISTS`：以前作成したv2が既に存在。**自動上書きしない**
- `INPUT_INSIDE_GIT_OR_INVALID_PATH` / `OUTPUT_INSIDE_GIT_OR_SAME_AS_INPUT`：Git管理外に分離し、入力/出力に別のファイルを使用

問題の判定コードだけを共有すれば、機密の口座情報、実際の価格、ファイル本文をGitHubへ送らずに対処できる。`diagnose`が`INCOMPLETE`でも、スキーマ・入力値に矛盾がなければ`migrate`を別途実行できる。旧v1の値は不変、別名v2のみ新規作成。
