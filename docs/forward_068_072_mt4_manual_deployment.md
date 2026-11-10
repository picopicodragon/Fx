# FWD-068〜072：楽天MT4 DEMOの手動読み取り専用実機検証キット

## 今回完成した部分
正式3ペアは **USD/JPY・EUR/JPY・EUR/USD**。実機では既存の単一楽天デモMT4、単一セッションのみを使用し、別デモ口座・並列端末は作らない。

| 工程 | 実装 | このPRで未実施 |
|---|---|---|
| FWD-068 | `FxForwardReadOnlyQuoteV3.mq4`：未配備の1回実行読み取り専用MT4スクリプト。DEMO/接続確認、3ペア厳格制限、最終ティック相対時刻のチェック、ペア別＋時刻入りCSVファイル生成 | MetaEditorコンパイル・実機操作 |
| FWD-069 | 端末ローカル `MQL4/Files` 内だけにCSVを作成。既存同名ファイルがあれば上書きせず中止 | OS/端末のファイル実動作 |
| FWD-070 | `research.forward_mt4_v3_source_review`：注文API、外部通信、共通フォルダー、削除・移動、対象外シンボルを静的検査 | MetaEditorでのバイナリ検査 |
| FWD-071 | `scripts/prepare_mt4_v3_manual_install_plan.ps1`：利用者指定の既存データフォルダーから、手動配置計画とソースSHAを記録。**MQL4フォルダーには書き込まない** | MT4へのソースコピー |
| FWD-072 | v3静的・安全ガード・CSV10列のv2受入互換性・Windows計画の回帰試験 | 実レートの配信確認 |

## 読み取り専用ソースのPC側レビュー

まずWindowsのGit作業ツリーを最新版に更新し、既存MT4が**デモ口座のみ**であることを確認する。AutoTradingをOFFに保つ。MACD Sampleなど他のEAの起動・設定は不明な場合があるため、チャート上の不要なEAの停止状態と未約定注文・建玉を目視確認する。不要なスクリプトの自動実行はしない。

コマンド例：

```powershell
python -m research.forward_mt4_v3_source_review `
  --source research/mt4_readonly/FxForwardReadOnlyQuoteV3.mq4 `
  --out out/mt4_v3_source_preflight_001.json
```

MT4の**ファイル → データフォルダを開く**で実際の端末データフォルダーを目視確認した後、そのパスを`-Mt4DataDirectory`へ渡す。プラン生成スクリプトは**端末に何もコピーしない**：

```powershell
.\scripts\prepare_mt4_v3_manual_install_plan.ps1 `
  -Mql4Source research/mt4_readonly/FxForwardReadOnlyQuoteV3.mq4 `
  -Mt4DataDirectory "C:\Path\To\Your\Existing\MT4\Data" `
  -PlanOutput out/mt4_v3_install_plan_001.json
```

## 実機側で行う単発確認（本工程では未実行）

1. 元MQL4ソースのSHA、3ペア、注文API未使用、出力先が端末ローカル`MQL4/Files`のみであることを目視確認する。
2. 既存の単一デモMT4端末でのみ、`MQL4/Scripts`へソースを**手動コピー**してMetaEditorで開き、コンパイル結果の**エラー数・警告数**を記録する。MetaEditorによるコンパイルはMQL4の動作を保証せず、実行権限の承認とは別である。
3. デモ口座・チャート3ペア・AutoTrading OFF・既存注文なし等の安全条件を再確認して、手動で**1回だけ読み取り専用スクリプトを実行**するか判断する。未確認なら実行せず終了する。
4. 成功時は各チャートの`MQL4/Files/FxFwdV3_<SYMBOL>_<PC_UTC_SECOND>.csv`を確認し、該当CSVを別のローカル証拠フォルダーに手動保存する。名前のUTC時刻とサーバー内ティック時刻が一致する意味ではない。
5. 出力したCSVを下記の既存受入検査に掛け、`NO_GO`であることを確認する。

```powershell
python -m research.forward_mt4_v2_quote `
  --csv "out/mt4_v3_manual_USDJPY.csv" `
  --asof-utc "2026-11-10T13:20:00Z" `
  --out out/mt4_v3_quote_validation_001.json
```

上記の日時は**形式例**。実際の実行時に観測時刻に合わせて入力する。新しいv3スクリプトはファイル名を変更しただけではなく、デモ確認、時刻、元データの状態を検査する。出力CSVの列と`origin`はv2パーサと同一なので、v2受入検査を再利用する。

## 絶対に完了扱いしないこと
- この会話からユーザーのローカルWindows/MetaEditor/楽天MT4端末を操作する権限や接続がない。ここでは実機のコンパイル、MQL4設置、スクリプト実行、価格観測を**実施していない**。
- MT4の`TimeCurrent()`と`MODE_TIME`が両方止まる場合は、相対ティック時間差が小さくても配信鮮度の保証ができない。`TimeGMT()`は端末PC時計由来、独立NTP保証なし。
- MQL4の静的テストはMetaEditorによる構文・コンパイル検証の代わりにならない。
- 既存デモ口座の契約属性、G1〜G9、FX-SAF、正式損失上限への適合、24時間フォワード観測は未認定。

デモ・本番注文は常に無効、`runtime_go_no_go=NO_GO`、`safety_hold_latched=true`、`real_orders_permitted=false`を維持する。
