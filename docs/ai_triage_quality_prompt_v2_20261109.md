# FX-AI-ARCH-004：AI補助判断の判定品質・質問設計v2研究（2026-11-09）

## 研究目的と既存の実測ベースライン

25イベント×3系統の2025年実API比較では、**21/25イベントの完全一致、4/25の不一致**が得られている。提示された本人ローカル監査レポートでは、Responses/Jev/Decisionsの重要度HIGH件数は25/25、25/25、24/25、追加分析YESは22/25、23/25、25/25。Jevの平均応答時間223.41 ms、Decisions 505.8 ms、Responses 2403.41 ms。これは同一25イベントの観測であり、**正解率・投資利益・永続的な速度差の証明ではない**。25件にLOW/MEDIUMが少なく、重要度分類能力は測定できない。観測済み不一致は3件の米雇用統計の再分析要否と1件の米CPIの重要度UNKNOWN。

この問題を切り分けるため、**別の16件の人工的なラベル付き事例**を固定し、従来v1質問と改善v2質問を同じ事例・同じ3 APIで対比較する研究専用ツールを追加した。

## v2質問の変更点

- **重要度は「そのニュースの面白さ」ではなく「指定した通貨ペアへのマクロ因果伝播の強さ」で判定**する。HIGH=主要金融政策/全国マクロ統計、MEDIUM=間接的な地域・部門統計、LOW=FXと無関係/極めて軽微、UNKNOWN=国・指標・出典そのものが判別不能。
- **再分析は不足資料の量だけでなく「指定ペアへの意思決定上の重要性」で判定**する。YES=重要データの予想値欠落/同時点の信用できる数値衝突/単位不明/後日改訂値混入、NO=資料十分またはFXと無関係な小さな資料不足、UNKNOWN=出典不明等で再分析必要性すら判断できない。
- **プロンプトインジェクション**を疑う非信頼ソースはデータとしてのみ扱う。
- `fx-bounded-macro-triage-v1`は従来のまま保持、v2は`fx-bounded-macro-triage-v2`と明示バージョニング。3社の異なるJSONペイロードにそれぞれ同じv2指針を変換。

### 人工データの評価上の限界

`research/datasets/triage_synthetic_quality_cases_v1.json`の16事例はすべて**合成・教育的・テスト用シナリオ**であり、`example.invalid`の架空参照を用いる。HIGH/MEDIUM/LOW/UNKNOWN、YES/NO/UNKNOWNのラベルは**設計者が書いた規約上の期待値**。モデルが生成したラベルを後から正解に変更することはしない。これらは独立した専門家の実歴史データラベルでも、2025年相場の実態でもない。v2質問文は合成シナリオを意識しているため、**このテストの成功を未知事例への一般化性能とはみなさない**。比較は対照入力の妥当性・判定偏りの検出という目的に限定する。

含む16事例には政策決定、重要雇用統計、軽微な地域指標、FX無関係なスポーツ情報、コンセンサス欠落、改訂値混入、信頼できない発信源、悪意ある指示文の混入を含む。原ラベルはAPIへ送信する入力パケットから除外する。**公開済みの合成データであることは契約上も出力でも明示し、本番注文の材料にしない。**

## モデル・評価指標

同じ16合成事例 × 3プロバイダー × 2質問版 = **最大96リクエスト**（有料API）。モデル実環境の契約/料金は未検証。プログラムは**一度の実行につき24回まで**しか許可しない。既定の初期化・結果検査は0回であり、費用額の上限を提供しない。

`variant_provider_metrics`に、回答の重要度・再分析要否別分布、人工ラベルとの一致件数、両方の一致件数、混同行列、平均応答時間を分けて記録。`paired_prompt_changes`に、同じ事例/同じプロバイダーでv1→v2により判定が変化したか、人工ラベルとの一致が変わったかを記録する。`case_level_discrepancies`には人工期待値と異なる判断のみを記録。正答率を本番評価と偽らないため`historical_model_quality_established=false`、`ground_truth_status=SYNTHETIC_RUBRIC_ONLY_NOT_HUMAN_VALIDATED`。

## Windows実行手順

### 1. ブランチ・全テストと無料の初期化

```powershell
cd C:\Users\Suzuki\Documents\ChatGPT\Fx
git fetch origin
git switch --detach origin/feat/ai-triage-quality-rubric-prompt-v2
python -m unittest discover -s tests -p "test*.py"

python -m research.ai_triage_quality_trial `
  --journal out/ai_triage_quality_v1v2_journal.json `
  --report out/ai_triage_quality_initial.json
```

出力は`SYNTHETIC_TRIAGE_QUALITY_PARTIAL_NO_GO`、`completed_requests=0`。以前の2025年実APIジャーナルや不一致結果を上書き・変更しない。

### 2. 実APIを使った比較（任意の有料段階）

**両サービスの公式請求画面で月間開発用AI予算3,000円（Q100）の残額を確認してから**行う。OpenAIとTypeSafeのAPIキーはWindows環境変数 `OPENAI_API_KEY` / `TYPESAFE_API_KEY` から取得し、Gitやチャットへ出さない。

初回の同一事例に対する3プロバイダー×v1/v2の6呼び出し：

```powershell
python -m research.ai_triage_quality_trial `
  --journal out/ai_triage_quality_v1v2_journal.json `
  --resume `
  --max-api-calls 6 `
  --allow-external-api
```

以降は月額予算と実費に応じて、`--max-api-calls 6`、`12`、`24`などで再実行。16事例すべての比較をするには合計96呼び出しが必要。**一括96回実行不可**。各リクエスト前にpendingを原子的に保存し、応答成否不明なら次回の自動再送を禁止する。これは支払いのExactly Onceを保証しない。

### 3. 課金なしで評価レポートを作成

```powershell
python -m research.ai_triage_quality_trial `
  --journal out/ai_triage_quality_v1v2_journal.json `
  --audit-only `
  --report out/ai_triage_quality_v1v2_report.json
```

```powershell
$r = Get-Content out/ai_triage_quality_v1v2_report.json -Raw | ConvertFrom-Json
$r | Select-Object status, synthetic_cases, completed_requests, ground_truth_status
$r.variant_provider_metrics | ConvertTo-Json -Depth 12
$r.paired_prompt_changes | ConvertTo-Json -Depth 12
```

既存ファイルを削除・上書きしないため`--report`は一度だけ使用。追加監査のときは別の新しい名前を指定する。

## 次の本格的な品質評価に必須の条件

- 2025年25件とは**別の**未使用の公開・取得時刻検証済み歴史事例（実際にLOW/MEDIUMも含む）を集める。
- 事例ごとに独立した人間の複数ラベル・判断規約・不一致解消の記録を得る。合意がないケースはUNKNOWNや未判定に分類する。
- 高重要度の見落とし、未検証なYES全件偏り、時点遅延・改訂データ混入、プロンプト攻撃、モデル版変更時回帰、費用・遅延・可用性を測る。
- 事前に**合格基準、コストと安全性のトレードオフ**を決定する。人工ラベル一致、ベンダーconfidence、多数決は実売買許可の代替にならない。

`NO_GO`、`safety_hold_latched=true`、`real_orders_permitted=false`のまま。Q92〜98/Q107の実プロバイダー採用承認、G1〜G9、FX-SAF、PHASE-1の安全審査は未完了。
