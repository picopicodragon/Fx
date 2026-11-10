# FWD-079：楽天MT4 MetaEditorの未初期化警告6件への対応

2026-11-10、ユーザーが既存楽天MT4デモ端末のMetaEditorで `FxForwardDemoTimerObserver.mq4` をコンパイルし、`0 errors, 6 warnings` を報告した。警告は `bids`（2件）、`digits`、`asks`、`ticks`、`ages` の「possible use of uninitialized variable」。**コンパイル成功≠警告ゼロ≠実機の安全性認定**。

## 修正
`OnTimer`で二段階処理（3ペア一括検証→3ファイル出力）に利用する固定長配列を、宣言時に3要素ともゼロ等で明示的に初期化する。これで、コンパイラが検証ループから書き出しループへの代入完了を証明できない場合でも、読み出し値が未初期化にならない。

- `bids/asks` : `{0.0, 0.0, 0.0}`
- `digits/ages/ticks` : `{0, 0, 0}`
- `filenames` : `{"", "", ""}`
- 既存のDEMO/接続判定、全3ペア同時検証、Bid/Ask/最終ティック経過、最大30タイマー周期、衝突時の書込み拒否、注文APIなしを維持
- 静的ソース監査に6配列の初期化パターンの点検を追加し、回帰テストで欠落を検出

## GitHubマージからWindows・MT4実機までの一体手順

PR #257をユーザーがマージした後、PowerShellで以下を実行する。作業ツリーの未追跡データは削除しない。

```powershell
cd C:\Users\Suzuki\Documents\ChatGPT\Fx
git switch main
git pull --ff-only origin main
python -m research.forward_mt4_timer_observer_review --source research/mt4_readonly/FxForwardDemoTimerObserver.mq4 --out out/mt4_timer_observer_source_review_002.json
```

出力先が既存なら別の未使用ファイル名にする。 `static_preflight_passed=true` を確認する。

MT4の「ファイル→データフォルダを開く→MQL4→Experts」で対象EAをチャートから外して実行を停止し、**このファイルと同名の旧ソース**を保全しながら、新しいソースに手動で差し替える。MetaEditorでそのファイルを開きF7コンパイル。**`0 errors, 0 warnings`を目標**とする。警告が1件でも残れば、実行せず警告全文を報告する。既存のMT4デモ・1端末・1チャート・AutoTrading OFFを維持。EAは未検証のため、警告ゼロの前に動かさない。

警告ゼロを確認できてから、既存のUSDJPYデモチャート1枚だけに読み取り専用EAを手動アタッチし、数分のExpertsログ・3ペアの個別CSV生成・停止動作を確認する。他のチャートに同じEAを付けず、自動売買許可をONにしない。

## 制限
GitHub ActionsはPythonの静的・構造テストで、MetaEditor実コンパイルではない。警告6件が解消したことは、このPRのCIだけでは独立に証明できない。デモ注文無効、`NO_GO`、`safety_hold_latched=true`、`real_orders_permitted=false`は変更なし。
