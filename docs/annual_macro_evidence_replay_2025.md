# FX-BT-011: 2025年通年・3ペア AIマクロ研究（公式一次資料の限定シード）

## 状況

- 公式対象は **USD/JPY、EUR/JPY、EUR/USD** の3ペアのみ。実口座/デモ/MT4注文は禁止（`NO_GO`）。
- 2025Q1の公的資料10件をそのまま残し、2025Q2〜Q4の一次資料15件を追加した**計25イベント**を `research/datasets/official_2025_macro_evidence_seed.json` に収録。内訳は、米CPI、米GDP（advance）、FOMC声明、旧資料の米雇用統計・日銀政策決定等。
- **完全なニュース網羅ではない**。特にQ4の政府閉鎖の影響で未公表の米統計を推測で補完していない。会合当日の投票・見通しの説明など発表文の抜粋を短く要約して収録。金融記事の全文転載をしない。
- 新規15件の`market_expectation`は全件空文字（当時の予想値の厳密なアーカイブ確証なし）。旧10件の既存値は変更していないが、旧6件のコンセンサスの公表前タイムスタンプは未立証（`official_2025q1_consensus_provenance.json`参照）。従って予想差・織り込みはAIに捏造させずHOLD可能。
- 新規15件の`available_at_utc`は公式リリースの掲載時刻/解禁時刻を採用した**仮定値**であり、秒単位の配信遅延は未立証。これ以上の安全性を保証しない。

## 一次資料の出典

- FOMC 2025全8会合: https://www.federalreserve.gov/newsevents/pressreleases/2025-press-fomc.htm
- CPI過去リリース: https://www.bls.gov/bls/news-release/cpi.htm （2025年米CPIの月別公開資料）
- CPIリリース予定時刻の照合: https://www.bls.gov/schedule/news_release/cpi.htm
- 2025年9月5日雇用統計（8月分）: https://www.bls.gov/news.release/archives/empsit_09052025.htm
- 2025年10月24日CPI（政府閉鎖に伴う9月分延期公表）: https://www.bls.gov/news.release/archives/cpi_10242025.htm
- BEA 2025-04-30 Q1 GDP速報: https://www.bea.gov/news/2025/gross-domestic-product-1st-quarter-2025-advance-estimate
- ISM PMI、PCE、米金利や経済予測、日銀の他の政策発表等は**収集候補**。出典の公表日時と対象期間が一次資料で検証できるまでは自動追加しない。

## 通年価格データ

ローカル `data/raw/dukascopy_h1` に以下のCSV計6本（**2025-01-01 00:00 UTC〜2026-01-01 00:00 UTC** の期間を含むH1）を準備する必要がある。既存2025Q1の6本とは別ファイルであり、自動ダウンロードや連結・価格生成はしない。

```text
usdjpy-h1-bid-2025-01-01-2026-01-01.csv
usdjpy-h1-ask-2025-01-01-2026-01-01.csv
eurjpy-h1-bid-2025-01-01-2026-01-01.csv
eurjpy-h1-ask-2025-01-01-2026-01-01.csv
eurusd-h1-bid-2025-01-01-2026-01-01.csv
eurusd-h1-ask-2025-01-01-2026-01-01.csv
```

CSV仕様は従来同様`timestamp,open,high,low,close`（Unixミリ秒、UTC、昇順、H1）。取引休日の不均一性・為替会社固有の証拠金契約・スリッページ等は未検証。通年プリフライトは年初・年末・最小5,500 aligned H1バー/ペア・96時間超の内部欠損・イベント時刻に対応するクローズ足の有無を検査し、欠陥時は中断する。合成価格を実際のパフォーマンスとして表示しない。

## オフラインプリフライト（API料金0円・注文なし）

```powershell
cd C:\Users\Suzuki\Documents\ChatGPT\Fx
git fetch origin
git switch --detach origin/feat/macro-2025-annual-evidence-replay
python -m research.annual_macro_pipeline `
  --prices-dir data/raw/dukascopy_h1
```

正常なら `ANNUAL_PRECHECK_RESEARCH_ONLY_NO_GO`。年間の候補判断数、コンセンサス不足数、6価格ファイルハッシュ、アライン済みバー数を表示。**プリフライト成功はAI生成・バックテスト成功を意味しない。**

## 有料AI生成：厳格な課金上限

デフォルトは無課金。明示的に `--allow-external-api` と`--max-api-calls`を指定する。上限は実際の予定最大回数で、各判断につき分析・独立レビューの**2呼び出し**。一次資料25イベントが別時刻なら3ペア合計75判断、最大150呼び出し。料金はモデルのトークン量・価格次第で不明。十分な残高・予算を事前に確認する。

まず1判断だけの有料試験例：

```powershell
python -m research.annual_macro_pipeline `
  --prices-dir data/raw/dukascopy_h1 `
  --analyst-model gpt-6-luna `
  --reviewer-model gpt-6.1-sol `
  --max-decisions 1 `
  --max-api-calls 2 `
  --journal-out out/macro_ai_decisions_2025_1.json `
  --report-out out/macro_ai_report_2025_1.json `
  --allow-external-api
```

全75件を実施する場合の指定例（**上限150回**、料金発生）：

```powershell
python -m research.annual_macro_pipeline `
  --prices-dir data/raw/dukascopy_h1 `
  --analyst-model gpt-6-luna `
  --reviewer-model gpt-6.1-sol `
  --max-decisions 75 `
  --max-api-calls 150 `
  --journal-out out/macro_ai_decisions_2025_75.json `
  --report-out out/macro_ai_report_2025_75.json `
  --allow-external-api
```

一度生成したJSON決定ジャーナルを**API再実行なし**でリプレイするには：

```powershell
python -m research.annual_macro_pipeline `
  --prices-dir data/raw/dukascopy_h1 `
  --decisions out/macro_ai_decisions_2025_75.json `
  --report-out out/macro_ai_report_2025_75_replay.json
```

ジャーナル・レポートは上書き禁止。Q1と通年は入力資料の範囲が異なるため、**Q1の既存30判断と通年の再生成30判断の成績が一致する保証はない**。新しい年次シードの先頭10イベントはQ1旧資料と同じ内容。

## 年間・四半期別評価

- `annual_macro_research.quarterly_realized_exit_attribution` に、各四半期のAI判断件数・売買承認件数・終了した取引数・終了四半期に帰属した確定損益を出力。**四半期DD・四半期リターン率と誤認しない**。
- 全年のtrade_count / net_pnl / max_drawdown / リスク拒否内訳は既存オフラインバックテストエンジンが計算。直近情報だけで推論するようソース候補は当時利用可能な最新30件に制限し、未来記事を配信しない。
- Q1〜Q3を探索、Q4を参考の時間順ホールドアウトと位置付けるが、学習済みAIに未来の知識が含まれるため**厳密な当時時点の取引判断・独立した真のOOSテストではない**。利益を立証しない。
- 収集対象を増やしたことで3ペアの金融政策仮説が改善したかは**未検証**。実ローカル通年CSVと実際の有料AI結果を使ったバックテストを未実施。研究開始時点から `NO_GO` は不変。

関連仕様：FX-BT-004〜011、FX-SAF、RISK-3P-28、Q26〜30。mainへのマージは従来の本人最終承認規定どおり。
