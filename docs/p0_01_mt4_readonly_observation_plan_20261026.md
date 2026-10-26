# P0-01：MT4の未確認5属性とv2表示入力を区別する検証計画

**状態：読取専用の設計資料のみ。** 実際の楽天MT4端末、実口座、価格配信サーバーへのアクセス・MQL4実行・EA接続・注文は行っていない。本人Windowsのv2判定は4ペアとも`INCOMPLETE`、各5数値属性を未取得。

## 1. 現在のv2照合ログの読み方

`PENDING FIELDS`は旧数値`properties`の未確認項目を表す。本人ログにある5項目は、MT4の「気配値→仕様」で表示された値に相当するものがないため保留で正しい。**入力されていないだけで誤値とは判定できない**。

旧版`check`は`display_properties`の日曜～土曜や執行モードが未入力でも、未確認フィールド名を表示しなかった。そのため、`INCOMPLETE`と5項目のリストを見ただけでは「表示情報が入力済み」とは断定できなかった。

今回の改善では`PENDING DISPLAY FIELDS`を追加し、もし表示情報が全項目入力済みなら`DISPLAY INPUT: ALL_RECORDED_NOT_VERIFIED`と表示する。**書式検査や項目の存在確認であり、本人入力と端末の一致は証明しない**。入力された原文・数値は標準出力に表示せず、表示されない項目を勝手に埋めない。数値5項目が`null`のままなら結果は`INCOMPLETE`。

## 2. MQL4で読取可能と文書化された5属性

| v2のキー | MetaQuotes公式属性 | 型・単位 | 未確認時 |
|---|---|---|---|
| `min_lot` | `MarketInfo(symbol, MODE_MINLOT)` | 最小ロット | `null` |
| `lot_step` | `MarketInfo(symbol, MODE_LOTSTEP)` | ロット刻み | `null` |
| `point_quote` | `MarketInfo(symbol, MODE_POINT)` | 決済通貨で表した1ポイントの価格幅 | `null` |
| `tick_size_points` | `MarketInfo(symbol, MODE_TICKSIZE)` | **ポイント単位**の1ティック | `null` |
| `tick_value_deposit_currency` | `MarketInfo(symbol, MODE_TICKVALUE)` | **口座通貨建て**のティック値（API記述） | `null` |

この5項目は、既存公開ルールの0.01ロットや5桁/3桁という一般説明から推測・確定してはいけない。とくに**`MODE_TICKSIZE`はポイント単位、`MODE_POINT`は価格差**なので、単位混同により円建て想定損失が桁違いになり得る。`MODE_TICKVALUE`は口座通貨の変換条件、注文の買売・数量と同時に妥当性を確かめる必要があり、取得値をそのまま**FXの0.5%損失上限の公式計算式**へ昇格させない。

MetaQuotes公式：
- [MarketInfo](https://docs.mql4.com/marketinformation/marketinfo)
- [MQL4 Symbol Properties](https://docs.mql4.com/constants/environment_state/marketinfoconstants)

`MODE_LOTSIZE`、`MODE_DIGITS`、`MODE_STOPLEVEL`、`MODE_FREEZELEVEL`を独立再照合する。`MODE_STOPLEVEL=0`のときサーバー側**動的制限の可能性**が公式文書に明記されている。値0だけで注文SL安全保証としない。口座通貨と、MT4画面にある「証拠金通貨」は概念が違う。`MODE_BID`、`MODE_ASK`、`MODE_TIME`、`MODE_SPREAD`は経時変化するため、固定的な契約情報と混在させない。

## 3. 呼値（配信）と取引の時間帯は別物

MetaQuotesは`SymbolInfoSessionQuote`と`SymbolInfoSessionTrade`を別のAPIとして定義し、曜日とセッション番号ごとに開始・終了値を返す。

- [MQL4 SymbolInfoSessionQuote](https://docs.mql4.com/marketinformation/symbolinfosessionquote)
- [MQL4 SymbolInfoSessionTrade](https://docs.mql4.com/marketinformation/symbolinfosessiontrade)

v2の`trading_hours_display`は**「呼値(00:00-24:00) / 取引(01:00-23:55)」のような画面表示テキストをそのまま格納**する。ここから未来の発注許可時間、サーバーTZ、日本時間、NY17、DST、休日補正を**推定してはならない**。将来、設計承認済みの読取専用コンポーネントを検討する場合、呼値と取引を別レコードにし、複数セッション番号・エラー・時間帯とサーバー基準を確認する。

## 4. 読取専用機能の将来の承認条件

本PRは**MT4読取プログラムそのものを作成しない**。将来のMQL4`MarketInfo`・`SymbolInfoSession*`読取コードの開発/端末実行は、本人の別途の安全確認を要する。

予定要件（まだ設計案）：MT4でのシンボル正式名称（接尾辞含む）、口座通貨（口座番号を保存しない）、取得方法、取得時刻、価格配信時刻/PC受信時刻、端末再接続、許可通貨4ペア、値の妥当性、独立した損益換算との一致を照合する。不完全・不一致・レートの鮮度不明では**安全側に新規発注拒否**。単一の数値や`COMPARED_FIELDS_ONLY`を自動的な売買許可へ変換しない。

`specs/p0_01_mt4_readonly_observation_plan.json`に、5属性と追加の11照合条件、未取得時の12失敗ケース、呼値/取引の区別、全4シンボルの`PENDING`を記録する。原本取引仕様の出典・安全重要実装承認を偽装しない。

## 5. 本PR後の操作

元の`mt4_symbols_local.json`もv2も**修正・上書き・アップロード不要**。手元のFxルートで従来の読取検査だけ行う。

```powershell
python -m scripts.mt4_manual_symbol_v2 check --input $v2File
```

今後は各シンボルの5数値項目の`PENDING FIELDS`と、手動表示項目の`PENDING DISPLAY FIELDS`（未入力時）または`DISPLAY INPUT: ALL_RECORDED_NOT_VERIFIED`（入力欄すべて記録済み）が分かれて出力される。後者は本人がMT4画面の正確さを証明したものではない。

`FORM-01/03`は未決、`implementation_approved=false`、`human_safety_approval=false`、`owner_approved_for_safety=false`、`forward_trading_enabled=false`、PHASE-1 BLOCKED。
