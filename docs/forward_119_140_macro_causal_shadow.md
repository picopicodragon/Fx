# FWD-119〜140：時刻帯別観測・マクロ仮説二段階契約・因果的シャドー評価

## 実際の到達点（2026-11-10）

楽天MT4単一デモ口座からコピーされたCSVが2セッション114件（38完全周期）、3ペアの欠損0、スプレッド実測はUSD/JPY 0.5pip、EUR/JPY 1.0pip、EUR/USD 0.5pipであることを**利用者側のオフライン監査出力として報告済み**。利用者は現行読み取り専用EAのExpertsログに`FXFWD_OBSERVER: 30-cycle safety cap reached; timer stopped.`が存在すると報告。ログの原本と実行中のEAバイナリはこのGitHub変更から検証できない。**30周期上限に達した後の停止メッセージが実機に存在するとの本人確認として扱うが、独立認証済みとはしない。**

本フェーズは、ユーザーの`マクロ主導・テクニカル検証`を進めるための**オフライン研究基盤**の実装であり、認証済みのAIマクロ判断、実物約定、利益見込みの確立ではない。

## FWD-119〜125：時間帯品質の研究

`research/forward_shadow_time_regimes.py`：

- FWD-104の厳格な入力検査を引き継ぎ、各ペアを**観測PCのTimeGMT値由来のUTC時（00〜23）**でグループ化する。
- 各時間帯の観測数、スプレッド最小・p95・最大、サーバー相対ティック遅延最大を記録する。各セッションの観測時刻帯も別々に記録する。
- UTC時間帯3種類未満では`INSUFFICIENT_TIME_OF_DAY_COVERAGE`を記録する。数十分の観測データからロンドン/NY/東京の全市場を評価したと主張しない。
- PC由来の時計の真正性とブローカー時刻のオフセットは未認証。**イベント発表の直前直後かは断定しない**。

## FWD-126〜132：マクロ仮説の二段階研究契約

`research/forward_shadow_macro_contract.py`：

- **出典の公表時刻≤取得時刻≤仮説生成時刻≤レビュー時刻≤判断時刻≤評価asof**を厳格に確認。未来に公表されたニュースから過去の売買判断を捏造するのを禁止。
- ソースはラベル・UTC公開日時・取得日時・内容SHA-256文字列で識別する。**ハッシュ形式チェックは元文書の存在・真実性の照合ではない**。実際の元文書や外部URLはこのコードでは取得しない。
- builder/reviewerは異なる識別子を必須とする。形式的分離だけを検査するため、実際に別AIが審査したとは認定しない。
- APPROVED/REVISION/REJECTED/PENDINGの研究用判定を保存する。APPROVEDは**入力文書にそう書いてある**という意味しかなく、実行権限の承認ではない。
- 金融政策・経済指標の予想差・織込・反証・失効条件の検証を本当に行うAI API呼び出しは未実装。入力文書の構造だけを受ける。信頼できる仮説がなくても仮の利益を自動計上しない。

## FWD-133〜140：スナップショット限定の因果的仮想評価

`research/forward_shadow_causal_replay.py`：

- セッションを明示的に選択。判断時刻より**厳密に後の**最初の120秒以内の観測スナップショットだけを仮想エントリー候補とする。同じ時刻・判断前の価格を使用しない。
- ユーザー入力の`evaluation_end_at_utc`までの**同一セッション**内だけを検査。評価終了時刻は判断時刻より後、評価asof以前に限定する。事前指定した仮説が実際に当時存在したとは立証しないため、任意に過去価格を見てから時刻を選ぶ事後選択バイアスは残る。
- LONGはAskで買い、Bidで評価。SHORTはBidで売り、Askで評価。両側に**不利な想定スリッページ**を加える。EUR/USDはそのスナップショットに含まれるUSDJPYを損失時ASK・利益時BIDで円換算する。
- **ストップ**は1分刻みのサンプルから初めて確認できた時刻の価格でしか評価しない。途中の価格経路や実スリッページ、注文成否は推定できない。ストップ価格をまたいだ場合は予約リスクを超える仮の損失があり得るので明記。
- 取引リスクは純資産0.5%、合計1%、日次1.5%、DD4%新規停止、DD5%人間承認待ちでVETO判定。DD2/3%警告も別に記録。スプレッドと両側想定スリッページを損失予約額に含む。
- CSV欠損、セッション跨ぎ、75秒超の途中欠落、入力時系列破綻、偽のソースハッシュ形式、マクロ判定がAPPROVED以外、リスク上限超過なら**仮想損益も生成しない**。
- `hypothetical_mark_ledger`は価格スナップショットを使った研究上の**仮定計算**。FXの実際の取引許可、約定実績、戦略収益の証拠ではない。1件のシナリオのみ、ポートフォリオEAでもマクロ自動生成でもない。

## Windows側への反映

PR #263をmainへ取り込んだ後、既存のクリーンCSV114件を対象にする。MT4/MetaEditor再コンパイルは不要。

```powershell
cd C:\Users\Suzuki\Documents\ChatGPT\Fx
git switch main
git pull --ff-only origin main
```

**実データを使って直ちに動かせるのは時間帯品質集計：**

```powershell
$asof = [DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ"); python -m research.forward_shadow_time_regimes --session "s001=out/mt4_timer_clean_001" --session "s002=out/mt4_timer_clean_002" --asof-utc $asof --out "out/mt4_shadow_time_regimes_$(Get-Date -Format yyyyMMdd_HHmmss).json"
```

マクロ仮説・シャドー評価は、**出典とそれぞれの時刻を持つ実在のユーザー管理研究入力が用意できたときだけ**実行する。今回の114件のデータからそれらを捏造して自動的に売買シグナルを作らない。仮説ソースがないなら`PENDING`として扱う。

仮説入力を作成した場合のCLI（パスは例）：

```powershell
$asof = [DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ"); python -m research.forward_shadow_macro_contract --hypothesis "out/research_hypothesis.json" --asof-utc $asof --out "out/research_macro_contract_$(Get-Date -Format yyyyMMdd_HHmmss).json"
```

シナリオを明示的に事前保存した場合のCLI：

```powershell
$asof = [DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ"); python -m research.forward_shadow_causal_replay --session "s001=out/mt4_timer_clean_001" --session "s002=out/mt4_timer_clean_002" --hypothesis "out/research_hypothesis.json" --scenario "out/research_scenario.json" --asof-utc $asof --out "out/research_shadow_replay_$(Get-Date -Format yyyyMMdd_HHmmss).json"
```

実ファイルが存在しない場合は作業をスキップし、承認済み仮説を架空で作成して代用しない。出典文書とCSV原本は変更しない。レポートはセッション外に新しい名前で保存しGitにコミットしない。

## 未完了と安全ゲート

30周期停止ログの実機存在はユーザーが確認したが、独立検証、デモ口座真正性、時刻、3ペア×5属性、トレード費用・取引約定・証拠金、マクロAI APIと真の別AIレビュワー、リスク・イベント停止の統合、長期シャドー性能評価は未完。

**常に** `NO_GO`、`safety_hold_latched=true`、`real_orders_permitted=false`、デモ/本番発注0。単一既存Rakuten DEMO MT4以外の口座や並行ログインを要求しない。
