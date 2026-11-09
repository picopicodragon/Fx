# FX-BT-007: HTTP 400の安全な切り分け

2025Q1 AIマクロ研究処理で、ユーザーWindowsにて履歴データのpreflight成功、APIキーSET、両モデルのGET /v1/models成功、gpt-6-lunaを使った単純なResponses APIリクエスト成功を確認した。一方、実際の`research.q1_macro_pipeline`（max-decisions=1）は繰り返しAI_GENERATION/HTTP_400で拒否された。この事実だけではモデルごとの推論可否・APIの不正パラメータは確定しない。

`research/macro_ai_generate.py`のAPI失敗を、拒否理由の固定分類に加えて、**ANALYSTかREVIEWERか**、およびOpenAI HTTPエラーJSONの`param`と`code`のうち**既知の固定文字列として許可したものだけ**記録する。

出力JSON例：

```json
{
  "status": "FAIL_CLOSED",
  "runtime_go_no_go": "NO_GO",
  "safety_hold_latched": true,
  "failure_stage": "AI_GENERATION",
  "failure_reason": "HTTP_400_INVALID_REQUEST_OR_MODEL_OPTIONS",
  "ai_role": "REVIEWER",
  "api_error_param": "text.format",
  "api_error_code": "unsupported_value"
}
```

**例は架空の組み合わせであり、今回の実際の原因を表すものではない。**

## 実行

```powershell
cd C:\Users\Suzuki\Documents\ChatGPT\Fx
git fetch origin
git switch --detach origin/fix/macro-ai-http400-param-role-diagnostics
python -m research.q1_macro_pipeline `
  --prices-dir data/raw/dukascopy_h1 `
  --analyst-model gpt-6-luna `
  --reviewer-model gpt-6.1-sol `
  --max-decisions 1 `
  --allow-external-api
```

実際の推論APIへの従量課金が起こり得る。APIキー・エラーメッセージ・本文・発表資料の内容はエラーログに出さない。出力ファイルが既にあれば上書きしない。NO_GOと安全停止は維持する。

- `ANALYST`なら初段の問題、`REVIEWER`なら初段成功後の問題
- `api_error_param`の値に応じて互換性を修正（UNKNOWNなら次の切り分けを検討）
- モデル名が有効でも指定リクエスト条件が利用可能とは限らない
- 有効なJSONが返っても仮説が正しい・過去の学習漏洩がない・実取引許可を意味しない

関連仕様: FX-BT-004〜007、Q26〜30、Q109。独立レビュー、損失/DD上限、MT4連携、本番発注・承認には変更を加えない。
