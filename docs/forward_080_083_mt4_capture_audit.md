# FX-FWD-080〜083: MT4デモタイマー観測の実CSV受入監査

## 実機実績と未確認事項
2026-11-10、既存楽天MT4デモ端末で修正版`FxForwardDemoTimerObserver.mq4`によるファイル生成に成功した旨、利用者が報告。**生成したファイル数・周期数・MetaEditor警告ゼロ・実稼働時間・タイマー停止はまだ独立に確認していない。** 過去の単発v3で取得した3ペアと区別する。

## 開発工程
- **FWD-080:** コピー済みローカルCSV専用`research.forward_mt4_timer_capture_audit`。MT4/ブローカーやWindowsのシステム設定へアクセスしない。
- **FWD-081:** 3ペアの時刻一致（CSV観測UTC対ファイル名UTC秒）、完全な3ペア一周期、通貨ペア・10列フォーマット・テスト用CSV重複/再利用を検出。
- **FWD-082:** 周期間隔60±15秒の逸脱、3ペアの一部欠落、30周期を超えるフォルダについて明示的にブロック。EURUSD円換算のUSDJPY同周期Bidとの一致も診断。60秒間隔は**観測ログの概略検査であり、タイマー機構の完全検証ではない**。
- **FWD-083:** 上記の異常系と上書き禁止のテストを追加。

## PRマージ後のWindows・MT4一括受入手順

まず既存楽天MT4デモ端末で「ファイル→データフォルダを開く→MQL4→Files」を開く。EAによる`FxFwdV3_*.csv`を確認。**元ファイルは削除・移動しない**。今回のEAの観測セッションに属するCSVだけを、新しい空のローカルフォルダーへコピーして分析する。別セッションや単発v3 CSVが混ざると、30周期超えや時刻欠損の原因になる。

PowerShellで最新コードを取得：

```powershell
cd C:\Users\Suzuki\Documents\ChatGPT\Fx
git switch main
git pull --ff-only origin main
```

コピー先フォルダーをセッションごとに新規作成する。下記は例：

```powershell
New-Item -ItemType Directory -Path "out\mt4_timer_session_001" -ErrorAction Stop
```

MT4の`MQL4/Files`から**今回のEAのCSVのみ**をそのフォルダーに手動コピー。ファイル名は`FxFwdV3_USDJPY_YYYYMMDD_HHMMSS.csv`、`FxFwdV3_EURJPY_...`、`FxFwdV3_EURUSD_...`。**この監査はCSV以外を含むディレクトリーを拒否する。**

Python監査は必ず以下のように**1行で実行**する（複数行PowerShellのバッククォート連結事故防止）。

```powershell
$asof = [DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ"); python -m research.forward_mt4_timer_capture_audit --directory "out/mt4_timer_session_001" --asof-utc $asof --out "out/mt4_timer_audit_$(Get-Date -Format yyyyMMdd_HHmmss).json"
```

正常な構造のCSVなら`status=DEMO_TIMER_CAPTURE_OFFLINE_NO_GO`、`complete_cycles`と`incomplete_cycles`、`blocking_reasons`が出力される。**`STALE`は歴史的観測の欠陥とは見なさない**。60秒間隔や完全な3ペアを確認できれば、その範囲についてのみ監査結果が分かる。監査エラー（`FAIL_CLOSED`）が発生したら元CSV/Expertsログを保存して再調査する。CSV修正・偽造をしない。

出力監査レポートは`out`内でGitへコミットしない。取引ロジックの許可・経済指標や相場分析の承認を意味しない。

## 引き続き未検証
MetaEditorの再コンパイル0 warnings、タイマー60秒発火、停止時のログ、注文/建玉状態、ブローカー提供レートの独立認証、PCのTimeGMT真正性、3×5=15の契約属性、G1〜G9、FX-SAF。観測の長期運用開始前にこれらを別々に検査する。

`runtime_go_no_go=NO_GO`、`safety_hold_latched=true`、`real_orders_permitted=false`、デモ・本番発注禁止。
