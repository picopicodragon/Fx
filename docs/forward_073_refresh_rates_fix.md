# FWD-073：MT4実機で発見されたRefreshRates誤判定の修正（2026-11-10）

## 実機ログによる再現
既存の単一楽天MT4デモ口座上で、USDJPY/H1に読み取り専用`FxForwardReadOnlyQuoteV3`を起動したところ、利用者から次のログが報告された：

```text
2026.11.10 14:11:21.572 Script FxForwardReadOnlyQuoteV3 USDJPY,H1: removed
2026.11.10 14:11:21.570 FxForwardReadOnlyQuoteV3 USDJPY,H1: uninit reason 0
2026.11.10 14:11:21.570 FxForwardReadOnlyQuoteV3 USDJPY,H1: FXFWD_V3: price refresh unavailable; no file.
2026.11.10 14:11:21.570 FxForwardReadOnlyQuoteV3 USDJPY,H1: initialized
2026.11.10 14:11:21.497 Script FxForwardReadOnlyQuoteV3 USDJPY,H1: loaded successfully
```

これはユーザーが提供した実行ログであり、こちらがMT4操作を実施したものではない。CSVは生成されていない。エラー内容は発注実行の証拠ではない。

## 原因・修正
MQL4公式`RefreshRates()`仕様：**trueならコピーした価格データが更新された、falseなら更新しなかった（すでに現在のデータである場合がある）**。従来のv3では`if(!RefreshRates()){return;}`としてしまい、十分に更新済みのデータをエラー扱いしていた。

**修正済み：** `RefreshRates();`を呼び出すが、bool戻り値は発注・出力可否の判断に使わない。後続の`IsDemo()/IsConnected()`、Bid/Ask正常性、`MODE_TIME`、サーバー内相対ティック経過秒<=90、EURUSDのUSDJPY換算ティック鮮度、厳密3ペア限定、衝突時ファイル上書き拒否、NO_GOはすべて維持。

引用元：<https://docs.mql4.com/series/refreshrates>

## 実機への修正適用（ユーザーの単一既存デモMT4のみ）
1. このPRがmainへマージされてから、**Windows側**で`git switch main`、`git pull --ff-only origin main`を実行する。マージ前にはローカルmainへこの修正は取り込まれない。
2. `python -m research.forward_mt4_v3_source_review --source research/mt4_readonly/FxForwardReadOnlyQuoteV3.mq4 --out out/mt4_v3_source_preflight_003.json`。出力ファイルが存在する場合は別の未使用名を指定する。
3. 元ソースを作業用Gitから、**実際に稼働中のデモMT4**の「ファイル→データフォルダを開く→MQL4→Scripts」へ、ファイル名とSHAを確認しながら手動コピー。MT4内の旧版MQL4は確認後に安全に差し替え、意図しない旧EX4の再利用を避ける。
4. MT4のMetaEditorで`FxForwardReadOnlyQuoteV3.mq4`を開いてF7コンパイル、0 errorsを確認。コンパイル結果を確認するまでチャート実行は禁止。自動売買はOFFのまま。
5. USDJPY/H1のデモチャートで単発実行し、Expertsログと`MQL4/Files/FxFwdV3_USDJPY_<UTC秒>.csv`を確認。ここでCSVがまだ無い場合は新しいExpertsログを取得して原因を追う。**CSV生成後も価格源の独立認証や取引許可にはならない**。
6. ファイルが生成されればCSVを研究用v2パーサに通し、その後EURJPY、EURUSDの順に検証。初回はUSDJPYだけで検証する。

## 状態
CIは**静的ソース監査と合成CSV回帰テスト**でありMetaEditor実コンパイルではない。`runtime_go_no_go=NO_GO`、`safety_hold_latched=true`、`real_orders_permitted=false`、デモ注文無効は維持。口座を再開設せず、別MT4を同時稼働させない。
