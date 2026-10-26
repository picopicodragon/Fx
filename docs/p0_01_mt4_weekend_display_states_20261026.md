# MT4 v2：土曜・日曜の「未記録」と「セッション欄が表示されない」を区別する（2026-10-26）

## 本人のWindows照合結果

384件のunittestが`OK`。4通貨ペアの`check`では数値属性5項目が`INCOMPLETE`。これと別に、`trading_hours_display.saturday`・`.sunday`の2欄が`null`。これは**未記録という意味のみ**で、休場、マーケットが閉じている、サーバー側で発注禁止などを意味しない。

## 画面上の確認に応じた入力

`display_properties.trading_hours_display`は曜日ごとの**画面表示記録**であり、発注可能時間の判定に使用しない。

| MT4「仕様」画面で実際に確認できたこと | v2の値 | 読取専用検証の状態 |
|---|---|---|
| 土曜・日曜をまだ見ていない/判別不能 | `null` | `UNRECORDED` |
| その曜日の呼値・取引ともセッション行が表示されていないのを本人が確認した | `"NO_SESSION_DISPLAYED"` | `NO_SESSION_DISPLAYED_UNVERIFIED` |
| その曜日の呼値・取引時間が実際に表示された | そのままの表示文字列（例：`"呼値(00:00-24:00) / 取引(01:00-23:55)"`） | `DISPLAY_TEXT_RECORDED_UNVERIFIED` |

`NO_SESSION_DISPLAYED`は**「画面に表示がなかった」**という人工的な記録用ラベルである。`NO_TRADE`や`CLOSED`や「土日は休場」などの取引可否・事実の断定ではない。MT4画面に日曜と土曜の欄そのものが空なのか、MT4サーバーからセッション情報を正常取得できていないのかをこの値だけでは判別できない。本人が目視確認していなければ`null`のまま残す。

今回のプログラム変更は`check_v2`の**表示ラベル**だけで、既存ファイルの自動変更、文字列からの時刻解析、注文・売買時間帯判断、ブローカーへのアクセスは一切行わない。

## 検証の限界と後続設計

[MQL4 SymbolInfoSessionTrade](https://docs.mql4.com/marketinformation/symbolinfosessiontrade)および[SymbolInfoSessionQuote](https://docs.mql4.com/marketinformation/symbolinfosessionquote)では、曜日/セッション番号ごとの時間値を別々に取得する。各APIの`false`は**要求したセッションのデータが取得できない**ことを示し、それだけで休場確定とは判断しない。サーバー時刻とJST/NY17/DSTの関連は別途検証が必要。

`min_lot`、`lot_step`、`point_quote`、`tick_size_points`、`tick_value_deposit_currency`の5数値属性が依然未取得なら、週末表示を記録しても4ペアは`INCOMPLETE`のまま。数値を捏造/推測して埋めず、[MT4読取専用観測・検証計画](p0_01_mt4_readonly_observation_plan_20261026.md)に従い将来別途確認する。

`implementation_approved=false`、`human_safety_approval=false`、`owner_approved_for_safety=false`、`forward_trading_enabled=false`、PHASE-1 BLOCKED。
