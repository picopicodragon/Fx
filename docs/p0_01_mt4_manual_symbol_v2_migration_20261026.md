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

python scripts/mt4_manual_symbol_v2.py migrate --input $reviewFile --output $v2File
```

`mt4_symbols_local.json`は読み取り専用で**一切変更しない**。出力が既存の場合、別ファイルであっても上書きせずエラー終了する。入力JSONが想定外の形式/値であれば`REVIEW_REQUIRED`として、v2ファイルを生成せず元のままにする。**v1とv2の個人観測値をGitHubへコミットしない。**

元のv1に`"spread_points": "フローティング"`がある場合、これは数値フィールドとして不正なので**先にv1をローカルで明示的に`null`へ修正**し、移行後に`display_properties.spread_mode`へ`"FLOATING"`を入力する（旧値のバックアップを個人の管理下で保持）。

## 3. v2に未入力の画面表示だけを補う

```powershell
notepad $v2File
python scripts/mt4_manual_symbol_v2.py check --input $v2File
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
