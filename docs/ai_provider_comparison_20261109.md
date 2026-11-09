# FX-AI-ARCH-002: OpenAI Responses / TypeSafe Jev / OpenAI Decisions API 研究用比較実装

## 出発点と厳密な役割分担

本人が2026-10-21に採択した `FX-AI-ARCH-001` は、「主推論・独立反証をOpenAI推論APIで先行し、**補助的な構造化判断**をJev（第一比較候補）とDecisions API（対抗候補）で比較する」方針。**Decisions APIそのものを売買判断・資金管理・注文可否の主エンジンに確定採用した記録はない**。

今回の `research/ai_provider_comparison.py` はこの範囲に限定して3アダプターを同じ内部業務契約へ統一したもの。既存の長文マクロ仮説構築・独立反証 `research/macro_ai_generate.py` の機構を変更せず、相互代替の本番ルーティングは行わない。

- OpenAI **Responses API**：既存JSON推論呼び出しを利用する**比較用の分類基準器**（構造化JSONを返すが、統計的なconfidenceを持つとは仮定しない）。長文仮説生成との混同を避ける。
- TypeSafe AI **Jev**：`POST https://api.typesafe.ai/v1/systemone`、`state`と`questions`オブジェクト、各`type=choice`と`criteria`選択肢、`answers`オブジェクト。
- OpenAI **Decisions API**：`POST https://api.openai.com/v1/decisions`、固定配列`questions`、`type=choice`と`choices`、`answers`配列。2026-11の公開ドキュメントでは`gpt-6-luna`のみサポート。

一次技術資料（照合日2026-11-09）：
- https://developers.openai.com/api/docs/guides/decisions
- https://developers.openai.com/api/reference/resources/decisions/methods/create
- https://docs.typesafe.ai/
- https://docs.typesafe.ai/api
- https://api.typesafe.ai/redoc

公式仕様が変更された場合はアダプターを再検証する。**Jevへのアクセス契約・APIキー所持・利用価格は現地環境で未確認**。Jev第三者ホスト上の互換サービスは公式TypeSafeエンドポイントと同一とは扱わない。

## 統一された二つの補助判断

過去イベントと通貨ペアを共有し、次の固定選択だけを比較する。

1. `priority` : `HIGH` / `MEDIUM` / `LOW` / `UNKNOWN`。マクロイベントの重要度。
2. `reanalysis` : `YES` / `NO` / `UNKNOWN`。追加分析が必要かどうか。

3候補で質問文を可能な範囲でそろえる。Jev/Decisionsの`confidence`は数値の範囲を検証して格納するが、**取引成功率・リスク制御上の承認とみなさない**。Responsesにはconfidenceを捏造せず`null`。未知の選択肢、欠測、refusal、タイムアウト、不正な値・モデルは`FAIL_CLOSED`。複数プロバイダーが不一致でも自動で主エンジンや注文実行へ昇格させず、API障害時の無断フォールバックはしない。

各プロバイダーは同一イベントの公開時刻で固定した資料パケットを受け取る。記録するのはprovider/model、質問規約版、ソースID、as-of、入力SHA-256、所要時間と分類結果。APIキーおよび口座秘密情報をレポートに書かない。料金は実測していないので推測した数値を記録しない。

## 安全な比較手順

**既定ではプリフライトだけ。ネットワーク・API料金・ブローカーアクセスはゼロ。**

```powershell
cd C:\Users\Suzuki\Documents\ChatGPT\Fx
git fetch origin
git switch --detach origin/feat/ai-three-provider-offline-comparison

python -m unittest discover -s tests -p "test*.py"

python -m research.ai_provider_comparison `
  --evidence research/datasets/official_2025_macro_evidence_seed.json `
  --providers responses jev decisions `
  --pair USD/JPY `
  --max-events 1 `
  --out out/ai_triage_compare_2025_1.json
```

正常時：`PROVIDER_COMPARISON_PREFLIGHT_ONLY_NO_GO`、`planned_requests=3`、`api_called=false`、**ファイル出力はしない**。

### 外部API実呼び出し（課金を伴うオプトイン）

実行PCの環境変数 `OPENAI_API_KEY` と公式TypeSafeから取得した `TYPESAFE_API_KEY` が必要。**チャット、Git、スクリプト引数へキーを貼らない**。指定した全プロバイダーが1イベントについて1リクエストずつ呼び出される（合計3回）。`--max-api-calls`は明示的な**回数上限であり料金上限ではない**。比較はまずイベント1件を推奨。

```powershell
python -m research.ai_provider_comparison `
  --evidence research/datasets/official_2025_macro_evidence_seed.json `
  --providers responses jev decisions `
  --pair USD/JPY `
  --max-events 1 `
  --max-api-calls 3 `
  --out out/ai_triage_compare_2025_1.json `
  --allow-external-api
```

**最大25件の過去イベント×同一1ペア×3アダプター＝75呼び出し**まで許容する研究ツール。3ペアの全面比較は別工程で予算・公表時点・事例ラベルとAPIコストを評価してから設計。価格CSV・MT4接続・発注は実施しない。出力先が存在する場合は上書き拒否。

## 何を実証したか / していないか

- **実証した対象（モック単体テスト）**：両社の異なるAPI要求/回答形式、同一固定イベントでの3アダプターの内部結果整合、選択肢範囲、拒否・タイムアウトの安全停止、料金フラグ/事前回数上限、資格情報なし時の送信禁止。
- **未実証**：本人の実APIキーでのJev/Decisions動作、リアルAPI応答の品質、API間の費用/応答速度の優劣、確率較正、比較対象25事例の人的正解ラベル、2025年75仮説への成績影響。合格閾値も未決。
- 今回のオフライン疑似値を実際のモデル性能とは呼ばない。モデル採用は `Q92〜98/Q107` の本人審査と独立した安全検証が残る。
- 既存 `NO_GO`、`safety_hold_latched=true`、`forward_trading_enabled=false`、1取引0.5%、同時1%、日次1.5%、DD5%等は不変。PR作成やユニットテストの成功も本番承認ではない。

## 次の安全な実測評価の条件

将来の比較レポートには、同一事例に対する人的ラベル、マクロ重大事象の見落とし率、UNKNOWN件数、回答の不一致、応答遅延、トークンの実使用量と公式請求単価に基づく円換算費用、失敗率、文言揺らぎへの感度を追加する。採用閾値は推測しない。変更は専用PR・CI・本人レビューで管理。
