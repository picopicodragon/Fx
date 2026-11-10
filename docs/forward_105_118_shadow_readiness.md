# FWD-105〜118: 実測価格の品質集計と発注禁止シャドー候補リスク評価

## 対象と達成範囲

既存の楽天MT4単一デモ口座から手動コピーされた2観測セッションの合計114CSV、38完全周期の成功を受け、**MT4に接続しないオフライン研究**として拡張。現状のデータだけでは、マクロ仮説を作成・承認する根拠、独立ブローカー時刻・レートの認証、約定シミュレーションの妥当性はない。したがって自動売買・デモ注文・紙上約定の実施を装わない。

## 実装内容

- **FWD-105〜111:** `research.forward_shadow_quote_quality`。FWD-104の厳格な複数セッション監査を再利用し、USD/JPY、EUR/JPY、EUR/USDの観測回数、最小/中央値/p95/最大スプレッド（pip）、ブローカーサーバー相対ティック経過秒の最大値を算出。スプレッドの5 pip超を**研究上の注意**として表示するだけで取引可否の閾値には用いない。
- **FWD-112〜118:** `research.forward_shadow_candidate_veto`。利用者が別途用意する研究候補JSONを厳密に検査し、想定損失額、対純資産比、取引0.5%、総額1%、日次1.5%、DD4%の新規停止、DD5%人間承認待ちを表示。EUR/USD円換算はコピーされたUSDJPYの観測ASK最大を研究上の保守的値として使用。**FXの実際の約定コストや将来のリスク保証にはならない。**
- どの候補でも`NO_VERIFIED_MACRO_HYPOTHESIS`、`CANDIDATE_IS_NOT_AN_EXECUTABLE_ORDER`、`HUMAN_APPROVAL_OR_REAL_TRADE_NOT_GRANTED`を保持して**無条件に執行禁止**。実注文数0、シミュレート約定数0。今段階で仮の利益を作り出さない。
- **テスト:** 正常データ・大きなスプレッド・2セッション集計・異常な数量・限度超過・ログ欠落・上書き禁止・発注禁止を含む回帰テストを追加。

## Windows操作（PR #262がmainにマージされた後）

```powershell
cd C:\Users\Suzuki\Documents\ChatGPT\Fx
git switch main
git pull --ff-only origin main
```

セッション内に他のファイルがある場合は監査を拒否するため、前工程で検証したクリーンフォルダーを使用する。**観測原本は変更しない。**

品質集計：

```powershell
$asof = [DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ"); python -m research.forward_shadow_quote_quality --session "s001=out/mt4_timer_clean_001" --session "s002=out/mt4_timer_clean_002" --asof-utc $asof --out "out/mt4_shadow_quality_$(Get-Date -Format yyyyMMdd_HHmmss).json"
```

実リスク候補ではなく**説明用の架空の研究シナリオ**を作成するには、PowerShellで`out/shadow_scenario_research_only.json`に以下を保存。既存ファイルが存在する場合は上書きしない。

```powershell
@'
{
  "pair": "USD/JPY",
  "side": "LONG",
  "equity_jpy": "100000",
  "units": "1000",
  "stop_distance_pips": "20",
  "current_total_risk_jpy": "0",
  "daily_loss_jpy": "0",
  "drawdown_percent": "0",
  "scenario_label": "synthetic-no-orders"
}
'@ | Set-Content -Path "out/shadow_scenario_research_only.json" -Encoding UTF8 -NoNewline
```

これは手動で再実行する場合のみの参考値。シナリオの作成は必要時だけで良い。作成後のリスク監査：

```powershell
$asof = [DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ"); python -m research.forward_shadow_candidate_veto --session "s001=out/mt4_timer_clean_001" --session "s002=out/mt4_timer_clean_002" --candidate "out/shadow_scenario_research_only.json" --asof-utc $asof --out "out/shadow_candidate_veto_$(Get-Date -Format yyyyMMdd_HHmmss).json"
```

候補JSONの数値は実在する注文・口座・約定を示さない。実口座情報・APIキーは入れない。スプレッドの品質評価は`SHADOW_DATA_QUALITY_RESEARCH_NO_GO`、架空候補の検査は`SHADOW_CANDIDATE_RESEARCH_VETO_NO_GO`。

## 未解決ゲート

MetaEditor実コンパイル、30周期自動停止ログ、口座/サーバー時刻独立認証、実ブローカーの約定仕様（3ペア×5属性）、人間承認、ニュース・イベントデータ、構築AI→検証AIのマクロ仮説などは未完。収益評価や戦略有効性は**まだ判定できない**。サンプル38周期は約38分相当の観測点であり、連続した38分間の無停止稼働を意味しない。

`runtime_go_no_go=NO_GO`、`safety_hold_latched=true`、`real_orders_permitted=false`、`demo_orders_permitted=false`。MT4も注文も動かさない。
