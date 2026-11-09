# FX-BT-008: 分析AIのHTTP400 input拒否に対する互換化と診断

## 事実
ユーザーWindows上で価格・ニュース資料のpreflight成功、APIキーSET、両モデルGET /v1/models成功、gpt-6-lunaの簡易Responses API `input`テキストとJSON出力が200 / completed。一方2025Q1の実マクロ分析は`failure_stage=AI_GENERATION`, `ai_role=ANALYST`, `api_error_param=input`, `api_error_code=UNKNOWN`でHTTP400。この情報だけでは拒否した理由・原因を確定できない。

## 対処
公式Responses APIの構造化メッセージ入力形式`input:[{role:"user",content:[{type:"input_text",text:"..."}]}]`に変更した。資料は公表時点までのマクロデータだけをJSON文字列として渡し、解析指示は従来どおり独立した`instructions`で指定。50KB超の入力は外部送信前に拒否。**構造化形式がHTTP400を必ず解消するわけではない。**

APIが400を返す場合は、プロバイダーのエラーメッセージ原文は出力せず、特定の文言だけを照合した`api_message_category`を出力する。例えば`INPUT_SCHEMA_REJECTED`、`INPUT_TOO_LONG`、`UNSUPPORTED_OPTION`、`CONTENT_POLICY_RESTRICTION`、`UNCLASSIFIED_INPUT_ERROR`。原文やAPIキー、ユーザー資料全文、口座情報は出力しない。モデルに見えるプロンプトや判断ロジックは変えない。

## Windowsテスト（外部API従量課金あり）

```powershell
cd C:\Users\Suzuki\Documents\ChatGPT\Fx
git fetch origin
git switch --detach origin/fix/macro-ai-structured-input-safe-message-v1
python -m research.q1_macro_pipeline `
  --prices-dir data/raw/dukascopy_h1 `
  --analyst-model gpt-6-luna `
  --reviewer-model gpt-6.1-sol `
  --max-decisions 1 `
  --allow-external-api
```

研究用バックテストのみ。NO_GO、safety_hold_latched=trueを維持。入力由来のAPI400が続く場合、新しい`api_message_category`で次工程を切り分ける。実AI API試験と価格CSVはGitHub CIでは扱わない。

関連仕様: FX-BT-004〜008、Q26〜30、Q109、FX-SAF。個人の承認なしにmainへマージしない。
