# FX-BT-005: 2025Q1の一次資料を用いたAIマクロ・バックテスト実行ガイド

## 到達点とデータの由来

`research/datasets/official_2025q1_macro_evidence.json`に、当時の公表日時が公的アーカイブで確認できた**10件**の経済・政策イベントを、出典URLとともに保存。米国BLS雇用統計3回、CPI3回、米連邦準備制度FOMC2回、日本銀行金融政策決定2回。文章は公的発表の**短い要約**であって、全文転載・未来の修正値ではない。研究用の一次資料に限った小規模サンプルで、全市場ニュース網羅ではない。

- 2025-01-10T13:30Z: BLS December employment (+256k, 4.1%): https://www.bls.gov/news.release/archives/empsit_01102025.htm
- 2025-01-15T13:30Z: BLS December CPI (0.4% monthly, 2.9% annual): https://www.bls.gov/news.release/archives/cpi_01152025.htm
- 2025-01-24T03:23Z: BOJ raised policy target to around 0.5%; local release **12:23 JST**: https://www.boj.or.jp/en/mopo/mpmdeci/state_2025/k250124a.htm
- 2025-01-29T19:00Z: FOMC retained 4.25-4.50%: https://www.federalreserve.gov/newsevents/pressreleases/monetary20250129a.htm
- 2025-02-07T13:30Z: BLS January employment (+143k, 4.0%): https://www.bls.gov/news.release/archives/empsit_02072025.htm
- 2025-02-12T13:30Z: BLS January CPI (+0.5% monthly, 3.0% annual): https://www.bls.gov/news.release/archives/cpi_02122025.htm
- 2025-03-07T13:30Z: BLS February employment (+151k, 4.1%): https://www.bls.gov/news.release/archives/empsit_03072025.htm
- 2025-03-12T12:30Z: BLS February CPI (+0.2% monthly, 2.8% annual): https://www.bls.gov/news.release/archives/cpi_03122025.htm
- 2025-03-19T02:25Z: BOJ maintained around 0.5%; local release **11:25 JST**: https://www.boj.or.jp/en/mopo/mpmdeci/state_2025/k250319a.htm
- 2025-03-19T18:00Z: FOMC retained 4.25-4.50% and announced Treasury runoff slowdown: https://www.federalreserve.gov/newsevents/pressreleases/monetary20250319a.htm

**重大な留保：**米雇用統計3件・米CPI3件については、CME/Econoday・Reutersの「発表前コンセンサス」として記載された数値を第二次資料で照合し、`market_expectation`に追加した。**予想値の事前配信時刻が当時のアーカイブで厳密に立証されたわけではない。** 6件の出典URL・確証不足を`research/datasets/official_2025q1_consensus_provenance.json`に別記し、全件`verified_asof_snapshot=false`とした。残りFOMC2件・BOJ2件の市場期待値は引き続き未確認の空文字。実績や後から判明した情報で偽の予想値を作成しない。公表・利用可能時刻は一次資料の明記時刻に基づくが、ミリ秒単位のマーケット受信遅延までは検証できない。短い要約だけでは、事前織り込みを正確に推定できない。**ニュースや当時のインフレ/金利予想の網羅性・実際のAI予測精度は保証しない。**

## Windows実行手順（3ペアの2025Q1 bid/ask CSV6本を既に取得済みの場合）

ユーザーのローカル作業コピーにPRを取り込み、`main`へ手動マージするか研究ブランチだけ取得してから行う。

```powershell
cd C:\Users\Suzuki\Documents\ChatGPT\Fx
git fetch origin
git switch --detach origin/feat/2025q1-official-macro-evidence-runner
New-Item -ItemType Directory -Force out | Out-Null
python -m unittest discover -s tests -p "test*.py"
```

### 1) **外部AIに一切送信しない**検証

```powershell
python -m research.q1_macro_pipeline --prices-dir data/raw/dukascopy_h1
```

- 入力となる実履歴6CSV、原始SHA256、10件の公式イベント、時刻・週末・bid/ask価格の妥当性を確認
- `PRECHECK_RESEARCH_ONLY_NO_GO`を表示
- `ai_api_called=false`、`ai_backtest_executed=false`と表示
- 価格CSVがWindowsに存在しない、形式が違う、欠落しているなら`FAIL_CLOSED`
- **この段階ではAI分析もバックテストも行っていない**

### 2) AI分析と独立AI反証を実際に呼び、価格バックテストまで連続実行（任意、有料）

ローカルPowerShellでAPIキーを安全な方法で`OPENAI_API_KEY`環境変数に設定する。APIキーは画面のスクリーンショット・チャット・GitHubに貼らない。**ChatGPT PlusとAPI利用料金は別**。実際に利用可能な異なる2モデルを利用者が指定する（現在のモデル名称やAPI利用権はモデル一覧から確認し、推測しない）。

```powershell
python -m research.q1_macro_pipeline `
  --prices-dir data/raw/dukascopy_h1 `
  --analyst-model YOUR_AVAILABLE_ANALYST_MODEL `
  --reviewer-model YOUR_DIFFERENT_AVAILABLE_REVIEWER_MODEL `
  --max-decisions 30 `
  --allow-external-api
```

このコマンドは10イベント×3ペアの**最大30件**、分析と独立レビューで最大60件程度の外部APIリクエストが発生し得るため、料金に注意。事前に小規模`--max-decisions 3`でAPI疎通確認するとよい。失敗しても利用済みAPIリクエストの課金は取消されない。バッチの原子性・API失敗時の再実行コスト管理は将来の改修課題。

成功時だけ次のファイルを保存：
- `out/macro_ai_decisions_2025Q1.json`：各時点、対象ペア、分析モデル、仮説、反証、検証モデルの判定、証拠ハッシュ
- `out/macro_ai_backtest_2025Q1.json`：AI仮説に基づく研究用の売買件数、損益、DD、拒否理由

異常/拒否/保留ならHOLD、SMAへ自動的に戻らない。外部AIに送るのは**10件の短いマクロ記事要約**であり、CSV価格データ/FX口座情報/MT4への接続はない。モデルが後日のニュースをすでに学習していた場合の汚染は**この方法では完全には防止できない**。モデルの違いだけでは真の独立性を証明できない。

## 本作業の実行可否と未達条件

GitHub CIはモックAIと人工為替データによるオフライン結合テストのみで、真の外部APIリクエストと実履歴の損益算定は行わない。ユーザーの実履歴CSV6本はWindowsの`data/raw/`にあり、GitHub環境にはない。APIキーも外部から読む機能は実行していない。

**従って本PRの完了が意味するのは「公的資料10件のデータセットと1コマンド実行経路を整備した」ということ**。実際の2モデルによるバックテスト結果を提供したことではない。

過去のAI予測・検証モデルの学習済み将来知識、当時の事前コンセンサスが全件欠損、10件という限定サンプル、価格コスト・OHLC精度・休日異常・後日の市場データ変更、統計的検出力の不足が解消するまで、実運用の収益性を結論づけない。

安全状態は`NO_GO`、`safety_hold_latched=true`、P05 0/8、G1 0/15、FX-SAF 0/15、FORM 0/43、PHASE-1 BLOCKEDを維持。自動的な`main`マージ、MT4/EA/実口座/デモ取引、broker APIは禁止。
