# Offline research backtest v1 (FX-BT-001, RISK-3P-283〜300)

**実行可能な範囲：合成または利用者が合法的に取得したOHLC CSVから、3ペアの研究用バックテストを実行する。** これはP05/G1の実証、AIマクロ戦略の有効性、MT4/EA注文の安全性、本人の実取引承認のいずれも意味しない。

## 変更を1PRへ集約

- `research/offline_backtest.py`: Python標準ライブラリのみ、ネットワーク・楽天MT4・EA・証券会社API・ブローカー認証不要。取引APIは存在しない。読み取るのはコマンドで明示されたローカルCSVだけ。
- `research/fixtures/synthetic_three_pair_bars.csv`: **完全な人工価格と人工シグナル**18行。相場記録でも利益予測でもない。
- `tests/test_offline_backtest.py`: CSV形式、次足約定、損切り先行、スプレッド、手数料、JPY換算、ストップ窓開け、同時リスク、NY17 DST、安全停止を検証。

## Windows PowerShellで実行

リポジトリのルートで：

```powershell
python -m unittest discover -s tests -p "test*.py"
python -m research.offline_backtest --csv research/fixtures/synthetic_three_pair_bars.csv
```

結果は標準出力のJSONであり、注文は一切送信しない。正常終了でも `status=RESEARCH_ONLY_NO_GO`、`runtime_go_no_go=NO_GO`、`safety_hold_latched=true`。入力が不正なら終了コード2、固定 `FAIL_CLOSED` と `INVALID_OFFLINE_INPUT` のみを出力する。ローカルファイルパスやCSV内容をエラーに反射しない。

任意の研究用CSVには以下の列を**指定順・正確なスペル**で用意する：

```csv
time_utc,pair,open,high,low,close,spread_pips,quote_to_jpy,signal
2026-10-05T00:00:00Z,USD/JPY,150,150.1,149.9,150,1,1,LONG
2026-10-05T01:00:00Z,USD/JPY,150,150.5,150,150.3,1,1,HOLD
```

- `time_utc`: UTCのみ、末尾 `Z` のISO 8601。各ペアの足を時刻昇順に並べ、複数ペア使用時は**同一時刻グリッド**が必須。欠落足・重複足を拒否。
- `pair`: `USD/JPY`、`EUR/JPY`、`EUR/USD` のみ。価格OHLCは**仲値（mid）の入力**とみなす。
- `spread_pips`: その足のスプレッドをpipsで明示。値は口座から自動取得しない。JPYペアの1pipは0.01、EUR/USDは0.0001。
- `quote_to_jpy`: **当該足で1単位の決済通貨が何円か**を指定。JPY建ては厳密に1、EUR/USDはUSD→JPYの外部算定済み・同時刻データが必要。入力源・真偽・時刻の真正性は本エンジンでは証明できない。
- `signal`: `LONG`、`SHORT`、`HOLD`、`FLAT`。**足が閉じた時点で確定していたシグナル**であることが前提。売買判断AIの生成・独立反証・改ざん検証は未実装で、この列を研究入力として扱うだけ。
- 使用可能な足は10万件まで、CSVは4MBまで。初期資金は既定10万円、固定SL距離20pips、仮の利確2R、1注文数量刻み1,000通貨（**楽天MT4の認証済み仕様ではない**）。

研究用の引数：

```powershell
python -m research.offline_backtest --csv research/fixtures/synthetic_three_pair_bars.csv --starting-jpy 100000 --stop-pips 20 --reward-r 2 --commission-jpy-per-1000-roundtrip 0
```

## 約定モデル・リスクの扱い

1. 時刻tの終値で確定した`LONG/SHORT/FLAT`を次の足t+1の始値で処理。未来の高値・安値・終値を使ったエントリー価格決定を避ける。
2. LONGは始値+半スプレッドで買い、売値（bid）で手仕舞い。SHORTは始値-半スプレッドで売り、買値（ask）で手仕舞う。指値・SLに同一足内で双方到達すれば**損切り先行**。
3. SLが足の始値ですでに飛び越された場合は、SL価格より不利な始値で決済し `STOP_GAP` と記録。想定初期リスク超過件数も記録する。**上限リスクが保証されるという意味ではない**。
4. 合成のサイズ計算は取引あたり最大純資産0.5%、同時初期SL想定リスク合計1.0%以内、手数料込で下方向に整数数量を切り捨てる。最小数量を満たさない場合、またはスプレッドがSL幅以上ならエントリー拒否。
5. NY17:00（America/New_York、夏時間自動）で日次基準を区切り、時点の概算純資産から日次1.5%の停止を模擬。DD4%で新規停止をラッチ（自動解除しない）、DD5%は保有を決済して新規を停止。*OHLC終値のサンプルで測ったDDのみ*であり、ティック間のリスクやギャップの許容性を証明しない。
6. 最終足で未決済建玉は `END_OF_DATA` として清算し、研究結果を確定する。将来の価格を補完しない。

## 限界と未実装

**本番注文・デモ注文・EAテストではない。** MT4契約サイズ・証拠金必要額・ロスカット・ストップレベル・スリッページ・約定拒否・レイテンシ・スワップ・調達コスト・休日・実際の変動スプレッド・証拠金維持率・未約定注文・複数建玉、通貨別ネット/グロス集中度と相関ストレスは十分にモデル化していない。既存の三角通貨リスク設計を実装済みと解釈しない。時刻ごとのFX換算入力やOHLCの品質・利用許諾も別途検証が必要。

特に本プロジェクトの**正式な売買ロジックは、AIマクロ仮説＋独立反証**である。研究エンジンは外部CSVに明記された過去の確定シグナルのみ実行し、その正式戦略のヒストリカル成績ではない。実価格データが無くても人工データでバックテストの機械的動作を検証できる、という段階を目標とする。

## 安全・受入

`P05=0/8 BLOCKED`、`G1=0/15`、`FX-SAF原議=0/15`、`FORM承認=0/43`、`PHASE-1 BLOCKED`、`NO_GO`、安全停止ラッチ、本番未承認を変更しない。Q109既存の固定45安全ソースの登録内容は変更しない。これは`research/`配下に隔離された未認証の試験実装であり、承認済みの注文リスクコードに転用してはならない。

次の段階で必要なのは、適法に取得できる**実際の履歴OHLC、同時刻換算レート、スプレッド、確定時点での戦略シグナル**である。これらなしに実績、期待収益、勝率、最大DD、実注文可能性を評価してはならない。

## 変更の検証

```powershell
python -m unittest tests.test_offline_backtest -v
python -m unittest discover -s tests -p "test*.py"
```

GitHubのWindows Python 3.13 / IANA time zonesとRepository checksをPRの最終headに対して確認する。mainへの最終マージは本人のみ。合成の約定成功は実運用承認ではない。
