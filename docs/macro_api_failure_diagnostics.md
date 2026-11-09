# FX-BT-006: API障害の安全な診断

## 実際の報告

2026年11月、価格とマクロイベントの`PRECHECK_RESEARCH_ONLY_NO_GO`は成功し、環境変数`OPENAI_API_KEY`はSETだったが、AI判断と結果レポートが未作成のまま`FAIL_CLOSED`で終了。利用者から**OpenAI APIが未チャージ**だったとの報告があった。

`OPENAI_API_KEY`が設定済みでも、API利用残高・請求設定・割当上限・モデル利用権は証明されない。APIキーPermission=ALLや7日間の有効期限も残高の代わりにならない。利用可能残高不足は多くの場合`HTTP_429_RATE_OR_QUOTA_LIMIT`に分類されるが、実際のHTTP応答を取得するまでは原因を断定しない。

## 実施手順

1. ユーザーがOpenAI APIプラットフォームの請求・利用残高・上限を確認する。支払い情報やキーはチャット/GitHubへ貼らない。
2. `python -m research.q1_macro_pipeline --prices-dir data/raw/dukascopy_h1` で無料のローカル事前チェックが成功することを確認。
3. 明示的に有料外部APIを呼ぶ場合のみ既存の`--allow-external-api`を指定。`--max-decisions 1`のように小規模にして上限・利用コストを確認。
4. 失敗時は`failure_stage`と`failure_reason`の**固定値だけ**報告する。キー、リクエスト本文、HTTPエラー本文、口座番号は報告しない。
5. `AI_GENERATION`、`HTTP_429_RATE_OR_QUOTA_LIMIT`ならAPIの利用残高・支払い設定・rate limitを確認。401ならキー認証、403なら権限、404ならモデル名・権限、400ならリクエスト/モデルオプションを再検証。

発注・MT4接続・本番Go/No-Goは変更せず、研究用NO_GOおよびsafety_hold_latched=trueを維持。CIのモックテストでは実際の課金APIを呼ばない。
