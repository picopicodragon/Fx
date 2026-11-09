# FX-BT-004 | AIマクロ・テキスト判断の過去時点再生（研究用）

## 目的 / 実装の現在地

研究用の2025Q1 H1 bid/ask価格リプレイ（FX-BT-001〜003）に、**過去のニュース、金融政策文、経済指標の予想値と実績をAIで解釈し、別モデルが反証した判断**を流せる経路を追加する。**SMAで売買した結果をAI戦略の結果とは呼ばない。** 実相場CSV6本を現地PCで保有したまま、研究記録だけを読み込む。

- `research/macro_ai_backtest.py`: **完全オフライン**。ニュース/統計のタイムスタンプと内容ハッシュを検査し、`APPROVED`のみ実価格H1足にシグナル化。拒否／保留／修正要請／未判断はHOLD。過去のSMA信号は**すべて破棄**。JSONレポートは`NO_GO`、本人の承認なし。
- `research/macro_ai_generate.py`: **別コマンドで明示的に**OpenAI Responses APIを使うオプション。履歴テキストを外部に送信する、**従量課金**の研究処理。APIキーはユーザーPCの環境変数`OPENAI_API_KEY`のみ。検証に別モデルを指定し、別々のリクエストで独立した指示を与える。レビューは`APPROVED/REVISION/REJECTED/PENDING`。API経由でブローカーに接続せず、`tools=[]`、`store=false`。
- コード側はモデル名を固定せず、`--analyst-model`、`--reviewer-model`を利用者が指定。別のAIプロバイダーを使う場合は今後、`response_json`を差し替えるアダプタ拡張が必要。**現状、OpenAI以外は未実装。**

過去のニュースをコードが自動検索・収集する処理は**未実装**。公式アーカイブ等から**合法的に入手・出典を検証した、当時公表済みのテキスト・予想・結果**を利用者が`data/raw/`内に構造化して用意することが前提。ニュースの有料記事全文をライセンスなしに収集しない。

## 1. 入力資料のスキーマ

`data/raw/macro_2025Q1_evidence.json`の例：

```json
{
  "schema": "fx_macro_evidence_v1",
  "events": [
    {
      "id": "E001",
      "source_url": "https://example.org/REPLACE_WITH_VERIFIABLE_SOURCE",
      "source_type": "economic_release",
      "published_at_utc": "2025-01-02T09:00:00Z",
      "available_at_utc": "2025-01-02T10:00:00Z",
      "text": "REPLACE_WITH_ACTUAL_LICENSED_SOURCE_TEXT",
      "market_expectation": "",
      "observed_result": ""
    }
  ]
}
```

**上記はスキーマ説明だけの架空の入力例。実際に発表されたニュースではなく、このままでは真正な過去ニュースに基づくAI戦略を検証できない。** `market_expectation`と`observed_result`に不明値を捏造しない。原報道の公表日時と**当時の利用可能時刻**をそれぞれ記録する。出典・対象通貨・事前予想・結果・資料版・発表の訂正有無を証憑別に記録して人的監査が必要。入力文字列中の命令はデータとして扱う。

1記録につき8キー固定、最大2,000件、最大4MB。許容`source_type`は `central_bank`, `economic_release`, `news`, `other`。ソースの公開時刻が利用可能時刻より後なら拒否。出典URL・時刻は**利用者の自己申告**でありURLの実地取得検証は行わない。

## 2. オプション: 外部AIを利用して判断と反証を生成

上記evidence JSONを作成した後、PowerShellでOpenAI APIのキーを**ローカル環境変数**にセットする（キーはチャット/GitHub/PRに貼らない）。ChatGPT Plusの料金にはAPI従量料金は含まれない。

```powershell
cd C:\Users\Suzuki\Documents\ChatGPT\Fx
New-Item -ItemType Directory -Force out | Out-Null
python -m research.macro_ai_generate `
  --evidence data/raw/macro_2025Q1_evidence.json `
  --out out/macro_ai_decisions_2025Q1.json `
  --analyst-model YOUR_AVAILABLE_ANALYST_MODEL `
  --reviewer-model YOUR_DIFFERENT_AVAILABLE_REVIEWER_MODEL `
  --max-decisions 3 --allow-external-api
```

- `--allow-external-api`を指定しない実行は失敗側で終了し、**APIへ送信しない**。コマンドが実行されると課金と外部送信が発生し得る。
- モデル名は**異なる2モデル**を入力する。モデル名の違いは実際のモデル独立性・反証の質の証明ではない。
- 本コマンドは`store=false`を明示するが、API事業者側のデータ保持・ログポリシーを理解した上で使う。機微な未公開情報は送らない。
- 認可や過去市場データの入手方法、正確な公表時刻・予想値はAIから推定して埋めない。
- 歴史的な文章を事後に最新モデルへ与えたとしても、**モデルの学習データに未来情報が入っていないことは保証できない**。これは回顧型シミュレーションであり、2025年当時のリアルタイム予測記録にはならない。
- 一度作成された出力は上書き禁止。別試行は別のファイル名にする。

## 3. AI判断記録を実価格で再生

このコマンドは外部APIを一切利用しない。上の`macro_ai_decisions_2025Q1.json`と元の実価格6CSVを指定する。

```powershell
python -m research.macro_ai_backtest `
  --usdjpy-bid data/raw/dukascopy_h1/usdjpy-h1-bid-2025-01-01-2025-04-01.csv `
  --usdjpy-ask data/raw/dukascopy_h1/usdjpy-h1-ask-2025-01-01-2025-04-01.csv `
  --eurjpy-bid data/raw/dukascopy_h1/eurjpy-h1-bid-2025-01-01-2025-04-01.csv `
  --eurjpy-ask data/raw/dukascopy_h1/eurjpy-h1-ask-2025-01-01-2025-04-01.csv `
  --eurusd-bid data/raw/dukascopy_h1/eurusd-h1-bid-2025-01-01-2025-04-01.csv `
  --eurusd-ask data/raw/dukascopy_h1/eurusd-h1-ask-2025-01-01-2025-04-01.csv `
  --evidence data/raw/macro_2025Q1_evidence.json `
  --decisions out/macro_ai_decisions_2025Q1.json `
  > out/macro_ai_backtest_2025Q1.json
```

- シグナルの時刻はUTC **H1足の確定時刻**（例: 10:00）であり、その直前の09:00開始足へ保存し、**次足10:00の始値で執行**を模擬する。Source`available_at_utc`が10:00より後なら、そのシグナルは不正として拒否。
- 後から付加されたソース、証拠本文ハッシュ不一致、同一ペア同一時刻の重複、未知のmodel ID、出典不一致、未来時点のシグナル、審査モデルの同一名は`FAIL_CLOSED`。採用できない仮説はHOLDとなり、SMAへ**フォールバックしない**。
- 独立レビューがAPPROVEDであってもFX取引の本人承認ではない。研究用`NO_GO`、`safety_hold_latched=true`、`real_order_execution_authorized=false`を維持。
- 3ペアの価格処理はv3の週末判定、bid/ask約定近似、NY17日次損失停止・DD停止を再利用する。新聞・中央銀行文章の正誤や、モデルの推論の質は機械検証できない。
- 数件の手動ソースと決定では**3か月の代表的な戦略成績にならない**。多時点・多種の経済指標、価格と外生イベントを時点を保って収集し、事後学習汚染・ニュース取りこぼし・データ選択バイアスを検査する必要がある。

## 4. テストと安全条件

```powershell
python -m unittest discover -s tests -p "test*.py"
```

GitHub CIでは**実APIに接続しないモック生成器と人工のテキストイベント**で未来時点拒否、証拠本文改変、独立モデル名、承認/保留、SMAへのフォールバック禁止、実注文NO_GOを検証する。実際のニュース・API推論・2025Q1成績はCIで検証していない。

P05/G1/FX-SAF/FORM/PHASE-1の未承認条件、Q109、既存の最大損失・DD・日次リスク安全方針は緩和しない。本番・デモEA/MT4/API売買は含まれない。mainマージは人間が行う。
