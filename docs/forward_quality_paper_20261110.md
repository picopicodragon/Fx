# FX-FWD-002〜005：フォワード研究のデータ品質・AI監査・仮想売買

## 今回のスコープ

FWD-01のローカル時点記録ジャーナルを起点に、**FWD-02/03のデータ品質検査、FWD-04の既存独立AI審査の記録照合、FWD-05の完全オフラインな仮想約定・損益再生**を研究専用で実装した。2025年バックテストの延長ではなく、新しく受領する情報を次回に再現可能なデータ契約へ落とし込む。

**重要：このフェーズは未だ自動リアルタイム収集・自動ニュースAI判断・MT4デモ稼働を開始しない。** 本プロジェクトの実際の配信元、データ取得API、契約、公式ニュース入手経路、運用費用、MT4デモ読取専用口座確認が確認されていないので、未検証の外部通信を接続しない。記録したローカルデータは `USER_SUPPLIED_UNVERIFIED` と区別したまま。採用可否・実発注の判断に使わない。

## 実装

- `research/forward_quality.py`：FWD-01を全件SHA-256連鎖・時系列・参照検査したうえで読み込む。見積の最新観測時刻と現在時刻との差分（研究上の90秒）、ソース別時刻逆行、受領遅延300秒超、経済発表の既に受信したニュースに対する±15分の時間帯、事前コンセンサス欠落を検出。引用の欠落、古い価格を可視化するだけで**取引可能とは認定しない**。90秒と300秒は仮の研究用検出閾値であり、実装レベルの正式リスク限度にはしない。
- `research/forward_paper.py`：明示的な研究シナリオの下、同じ通貨ペアに属するマクロイベント→仮説→別モデルIDの独立レビューをリンクし、APPROVED時に**以後の2時点の見積**から最初の気配で仮想エントリー、後続の気配で仮想SL/TPまたは未決済MTMを計算。サンドボックスの最大エクスポージャーは1ポジション、想定リスクは初期10万円×0.5%=500円以下、仮の1000通貨単位で丸める。Bid/Ask sideを用いる。これは本番ロット・証拠金制約・スリッページ・手数料・日次損失・DD・指標停止・当日口座状態を再現するわけではなく、明示的に未認証フラグを出す。
- `tests/test_forward_quality_paper.py`：価格鮮度/欠落予想、マクロイベント→独立審査→仮想利確/損切、審査なしの不成立、同一モデルIDの審査拒否、研究資金・リスク上限、ローカルCLIエラー。
- 研究コードは**urllib等のネットワーク取得、AIへのAPIリクエスト、MT4コマンド、デモ注文に一切触れない**。

## Windowsでの準備と検証

```powershell
cd C:\Users\Suzuki\Documents\ChatGPT\Fx
git fetch origin
git switch --detach origin/feat/forward-observation-quality-paper-pipeline
python -m unittest discover -s tests -p "test*.py"
```

FWD-01で作成済みのセッション `out/forward_observation_20261109` がある場合、全件の検査済み時点 `asof` を明示する。現在日時とは別の過去時点を指定すれば、同時点までに記録済みの証拠のみで評価する。

```powershell
$asofUtc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")

python -m research.forward_quality `
  --store out/forward_observation_20261109 `
  --asof-utc $asofUtc `
  --out out/forward_quality_20261110.json
```

監査レポートは必ず**新しい出力先**を使う。既存ファイルは上書きしない。

完全オフライン仮想シナリオファイルを作成する。

```powershell
@{
  schema = "fx_forward_paper_scenario_v1"
  hypothetical_only = $true
  starting_jpy = "100000"
  stop_pips = "20"
  reward_multiple = "1.5"
  max_simulated_positions = 1
  commission_jpy = "0"
} | ConvertTo-Json -Depth 5 |
  Set-Content -Path out/paper_plan_20261110.json -Encoding UTF8

python -m research.forward_paper `
  --store out/forward_observation_20261109 `
  --scenario out/paper_plan_20261110.json `
  --asof-utc $asofUtc `
  --out out/forward_paper_20261110.json
```

AI仮説・レビュー・その後の2時点の見積がなければ、`hypothetical_position=null`で成功する。これは売買戦略が機能したことではなく、証拠がそろわない限りシミュレーションすら開始しない設計である。

実市場での損益やブローカー約定は未検証。スプレッドのみBid/Askによって反映、リアルのスリッページ、執行拒否、成行価格時点の配信遅延、証拠金・レバレッジ・通貨数量仕様、休日と市場停止、発表前の未来カレンダー停止は**未確認**。日次1.5%、DD5%、継続ポジション管理は本番安全モジュールとは独立・未認証。仮想ストップはギャップで損失が500円を超えうる。

## 本フェーズの達成/未達

| ゲート | 範囲 | 状態 |
|---|---|---|
| FWD-01 | ローカル証拠記録と連鎖監査 | 実装済、研究コードのみ |
| FWD-02 | 最新気配とニュース受領の検査 | **ローカル観測に対する準備済**。実配信API未接続 |
| FWD-03 | 情報欠落、配信遅延、既知イベント直後の停止判定 | **研究用検知実装**。将来の経済カレンダー/改訂追跡は未実装 |
| FWD-04 | 既存仮説と独立審査の時系列・ID監査 | **ローカル監査実装**。ライブAI推論は未接続 |
| FWD-05 | 単一仮想ポジションの価格side・SL/TP/MTM | **限定モデル実装**。本番と同等の執行・資金管理は未実装 |
| FWD-06 | 楽天MT4デモ読み取り専用照合 | 未実装 |
| FWD-07 | MT4デモ注文 | NOT AUTHORIZED |
| FWD-08 | 本番採用、MODULE/PHASE受入 | 未承認 |

運用費用（API従量料金）を意図しないよう、FWD-02〜05研究CLIはローカルのみで0回の外部API呼び出しに限定した。最新の2025年バックテスト研究結果や人工期待値を本番許可条件として扱わない。

固定安全状態：`runtime_go_no_go=NO_GO`、`safety_hold_latched=true`、`real_orders_permitted=false`、`demo_order_execution_enabled=false`。
