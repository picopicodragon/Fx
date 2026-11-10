# FWD-084：8周期の初回実データ監査で判明したUSDJPY円換算の誤警告

## 利用者による実機観測（2026-11-10）
既存の単一楽天MT4デモ口座の読み取り専用EAから取得したCSVを利用者が `out/mt4_timer_session_001` に保管し、FWD-083を実行。結果は24ファイル、8つの完結した3ペア周期、不完全周期0件。出力のblocking_reasonsに`EURUSD_USDJPY_CONVERSION_INCONSISTENT`が含まれた。他の3件（BROKER_TIME_NOT_INDEPENDENTLY_ATTESTED、DEMO_ACCOUNT_NOT_INDEPENDENTLY_VERIFIED、NO_TRADING_PERMISSION_FROM_CSV_EVIDENCE）は想定した安全上の保留であり削除しない。

**原因特定：** v2パーサは価格を数学的精度維持のため10進数の文字列で返す。FWD-083の監査では同周期のUSDJPY.bidとEURUSD.quote_to_jpy_research_onlyをPythonの文字列同士で比較していたため、例として`157.940`と`157.94000`でも不一致と誤判定した。MQL4ではUSDJPY Bidは通常3桁、一方USDJPY換算値は固定5桁で書き出す。

**修正：** 両者を`Decimal`に戻して厳密な数値比較。ゼロ埋め、小数桁数の違いだけなら不一致としない。値が真に違う場合は従来どおり警告を維持。浮動小数点の許容誤差（epsilon）で真の不一致を隠さない。

**注意：** 利用者の24件のCSVバイト列はこの会話にアップロードされていないため、8周期すべて実際に数値一致したとはまだ断定しない。合成テストはユーザーの実データの代わりにならない。元CSVの修正・再生成は禁止。

## GitHubマージ後のWindows再監査手順（一括）
PR #259 をマージ後、PowerShellで次の順に実行。今回はMT4 EAを変更しないためMetaEditorの再コンパイルやEAの再アタッチは不要。

```powershell
cd C:\Users\Suzuki\Documents\ChatGPT\Fx
git switch main
git pull --ff-only origin main
$asof = [DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ"); python -m research.forward_mt4_timer_capture_audit --directory "out/mt4_timer_session_001" --asof-utc $asof --out "out/mt4_timer_audit_fix084_$(Get-Date -Format yyyyMMdd_HHmmss).json"
```

`out/mt4_timer_session_001`に同じ24件が保持されている場合、出力の`files=24`、`complete_cycles=8`、`incomplete_cycles=0`を再確認する。`EURUSD_USDJPY_CONVERSION_INCONSISTENT`が消えたか判断する。消えなければ、監査JSONから警告が残ることだけ確認し、元のペア別CSVを保全して実値を照合する。結果を作り変えない。

元CSVは操作しない、Python監査だけを再実行する。ユーザーMT4の実機状態・PC時計・ブローカー提供レートの独立証明ではない。

引き続き `NO_GO` / `safety_hold_latched=true` / `real_orders_permitted=false`。実注文・デモ注文の許可なし。
