# FX-BT-002 | 実際の過去相場CSVを使うオフラインH1バックテスト

## 実行できる範囲

**USD/JPY、EUR/JPY、EUR/USDの過去1時間足のbid/ask CSVを6ファイル用意すれば、実価格に基づく研究用バックテストをWindowsで実行できる。** データ取得や認証のためにMT4、楽天証券、EAには接続しない。Pythonコード自体にネットワーク取得処理はない。

履歴データは実在するDukascopyの過去価格。**今回の研究用シグナルはSMA(10/30)クロスの例示であり、本来の金融政策・ニュース因果・独立AI反証による売買判断ではない。** 結果を正式な自動売買システムの利益実績と呼ばない。

## 0. 必要なもの

- Windows PowerShell、Python 3.13、既存リポジトリの`main`最新版。
- `tzdata`: `python -m pip install -r requirements-dev.txt`
- 過去H1価格CSV、3ペア×bid/askの計6ファイル。
- 相場データの利用規約を確認し、適法に利用できるものをユーザー自身のローカルPCに保存する。**生データ・個人ログイン情報をGitHubにコミットしない**。

Dukascopyの正式な履歴ダウンロード案内: https://www.dukascopy.jp/marketwatch/historical/ 。取得手段によってデモログインなどが必要。CLIを利用する場合は第三者OSS `dukascopy-node` (https://www.dukascopy-node.app/config/cli) の利用条件、提供元の利用規約を各自確認する。Dukascopy公式とは別主体のツールである。CLIのH1、UTC、bid/ask、CSV、Unixミリ秒形式の仕様は同サイトの説明に基づく。**認証情報はコード/PR/CIへ投入しない。**

## 1. 履歴ファイルを準備（例：2025年1月〜3月）

以下は、ユーザーが提供元の規約を確認し、第三者CLIを使用する場合のPowerShell例。Node.js/npm環境が必要。公式サイトから同等形式のデータをダウンロードしてもよいが、列名とタイムスタンプ形式を合わせること。

```powershell
cd C:\Users\Suzuki\Documents\ChatGPT\Fx
New-Item -ItemType Directory -Force data\raw\dukascopy_h1 | Out-Null
npx dukascopy-node -i usdjpy -from 2025-01-01 -to 2025-04-01 -t h1 -p bid -f csv -dir data/raw/dukascopy_h1 --retries 3 --cache
npx dukascopy-node -i usdjpy -from 2025-01-01 -to 2025-04-01 -t h1 -p ask -f csv -dir data/raw/dukascopy_h1 --retries 3 --cache
npx dukascopy-node -i eurjpy -from 2025-01-01 -to 2025-04-01 -t h1 -p bid -f csv -dir data/raw/dukascopy_h1 --retries 3 --cache
npx dukascopy-node -i eurjpy -from 2025-01-01 -to 2025-04-01 -t h1 -p ask -f csv -dir data/raw/dukascopy_h1 --retries 3 --cache
npx dukascopy-node -i eurusd -from 2025-01-01 -to 2025-04-01 -t h1 -p bid -f csv -dir data/raw/dukascopy_h1 --retries 3 --cache
npx dukascopy-node -i eurusd -from 2025-01-01 -to 2025-04-01 -t h1 -p ask -f csv -dir data/raw/dukascopy_h1 --retries 3 --cache
```

生成されるCSVファイル名の例は `usdjpy-h1-bid-2025-01-01-2025-04-01.csv`。指定日付の`-to`は終了日を**含まない**。2025年1月〜3月分を使用する。

```csv
timestamp,open,high,low,close
1735689600000,156.5,156.6,156.4,156.55
```

上は**CSV形式を示す架空の1行**であり、実際の2025年1月1日の価格ではない。実履歴は自分で取得した6ファイルを利用すること。

## 2. バックテスト実行

取得ファイルが上記の名前である場合：

```powershell
python -m research.historical_replay `
  --usdjpy-bid data/raw/dukascopy_h1/usdjpy-h1-bid-2025-01-01-2025-04-01.csv `
  --usdjpy-ask data/raw/dukascopy_h1/usdjpy-h1-ask-2025-01-01-2025-04-01.csv `
  --eurjpy-bid data/raw/dukascopy_h1/eurjpy-h1-bid-2025-01-01-2025-04-01.csv `
  --eurjpy-ask data/raw/dukascopy_h1/eurjpy-h1-ask-2025-01-01-2025-04-01.csv `
  --eurusd-bid data/raw/dukascopy_h1/eurusd-h1-bid-2025-01-01-2025-04-01.csv `
  --eurusd-ask data/raw/dukascopy_h1/eurusd-h1-ask-2025-01-01-2025-04-01.csv `
  --fast 10 --slow 30 --stop-pips 20 --reward-r 2 `
  --commission-jpy-per-1000-roundtrip 0 > out/historical_backtest_2025Q1.json
```

出力先`out`はGit管理対象外。事前に`New-Item -ItemType Directory -Force out | Out-Null`で作成する。

終了コード0ならJSONの`historical_research`に入力6ファイルのSHA256、期間、整列後の足数、欠損に伴う除外時刻数、SMAシグナル件数が記録される。成績は`trade_count`、`net_pnl_jpy`、`ending_jpy`、`max_drawdown_observed_pct`、`trades`等に表示。

終了コード2は`FAIL_CLOSED`。ファイル欠損/契約外形式/35,000足超/8MB超/UTC時刻不正/逆転OHLC/逆鞘/未整列時刻過多/30足未満などでは固定エラーのみ出力してバックテストしない。秘密パスやCSV内容を例外文に反射しない。

## 3. 実装の考え方と誤解防止

- UTCのH1足`timestamp`は足の**開始時刻**。シグナルは足の確定後のSMA終値情報から計算し、**次のH1足の始値**でのみ模擬エントリーする。
- Bid/AskそれぞれのOHLCを算術平均した`mid` OHLCと、始値/終値の観測スプレッドの大きいほうを1足固定の研究用スプレッドとしてv1エンジンへ渡す。**実際のティック約定・スプレッド曲線は再現していない**。
- USD/JPYとEUR/JPYの`quote_to_jpy`は1。EUR/USDのJPY換算は当該足始値時点で未来を参照しないため、**前の整列済みUSD/JPY足の終値**を使用。変動中レートの正確な換算ではない。
- 3ペア×bid/ask 6系列のUTC時刻の共通部分のみ使用する。欠損時刻を勝手に補完せず、最大2%の除外まで明示し、それ以上は拒否する。週末は元データに無ければ補間しない。
- SMAは10/30本の単純移動平均線クロスで、**売買例示のための研究用ダミー戦略**。正式なAIマクロシステムの意思決定ではない。変更する場合は`--fast`/`--slow`オプションで指定可能。
- 既存研究用エンジンの初期資金10万円、1回0.5%、同時1%、日次NY17:00、DD4%新規停止・DD5%決済の機械的模擬を維持。本番のリスク・承認ゲートやG1を通したことにはならない。
- 手数料既定0円、スワップ・必要証拠金・レバレッジ・発注拒否・滑り・指標発表・実MT4ストップレベル・H1内bid/ask約定順は未実装。評価結果は収益保証ではない。
- **重大な制約**：H1の両側OHLC平均による価格形成は、同時刻のbid/askティックを復元しない。実注文可能な精度・正確なDD・損益を主張しない。
- 現行CSV出力のSHA256は転送後のファイル同一性確認用であり、市場データの出所の独立した真正性証明ではない。第三者データの欠落・検出不能な改変は別途監査対象。

## 4. 開発/受入境界

```powershell
python -m unittest tests.test_historical_replay -v
python -m unittest discover -s tests -p "test*.py"
```

新規テストは**実データに見せかけない合成bid/askのH1 CSV**だけを使う。CIの成功は実際のDukascopy履歴6ファイルを取得して試験した意味ではない。実価格による成績数値を捏造しない。

P05 0/8 BLOCKED、G1 0/15、FX-SAF原議 0/15、FORM 0/43、PHASE-1 BLOCKED、`runtime_go_no_go=NO_GO`、`safety_hold_latched=true`。本人承認のない実取引・demo取引・EA/MT4操作・main自動マージを実施しない。Q109原議安全登録と既存の本人承認要件を変更しない。今後の正式なAIマクロバックテストには、過去の判断時点で得られた情報だけのマクロ履歴、ニュースの公表時刻、予想差、独立AI反証ログが追加で必要。
