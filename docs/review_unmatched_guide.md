# 未抽出のFX設計回答を原議文脈で確認する（Q115追補）

> **重要**：このPython補助ツールは、抽出対象にならなかったユーザー発言と、**その会話枝で直前に遡れるアシスタント発言**をローカルに並べるだけです。設問番号の確定、原議との正式照合、安全重要仕様の承認を自動実施しません。

## 利用する環境

- Python 3.13.11、起動コマンド：`python`
- Fxローカルリポジトリ：`%USERPROFILE%\Documents\ChatGPT\Fx`
- エクスポート原本：`%USERPROFILE%\Documents\ChatGPT\FxSourceArchive\originals\conversations.json`
- ローカル抽出結果：`%USERPROFILE%\Documents\ChatGPT\FxSourceArchive\candidates`
- **すべてコマンドプロンプト（cmd）で実行**。原本・未検証候補はGitHubにアップロードしない。

## 1. 作業ブランチのコードを使えるようにする

このツールはPRが `main` にマージされるまで `main` からは起動できません。ユーザーがGitHub上のPRを確認して手動マージした後、以下を実行します。

```cmd
cd /d "%USERPROFILE%\Documents\ChatGPT\Fx"
git switch main
git pull --ff-only
python scripts\review_unmatched_decisions.py --help
```

## 2. 既に特定したFX設計会話IDを指定して抽出

`ここに会話ID` は `scripts/list_export_conversations.py` で確認した**実際の会話ID**に置き換える。

```cmd
python scripts\review_unmatched_decisions.py --input "%USERPROFILE%\Documents\ChatGPT\FxSourceArchive\originals\conversations.json" --conversation-id "ここに会話ID" --max-question 115 --out-dir "%USERPROFILE%\Documents\ChatGPT\FxSourceArchive\candidates\review_unmatched"
```

出力先：`...\FxSourceArchive\candidates\review_unmatched\unmatched_review.json`

**既に同名の出力ファイルが存在すると上書きせず終了**します。再試行時は新しい出力フォルダ名を指定するか、ファイルを別名でローカル退避します。

## 3. 結果をローカルで閲覧

```cmd
notepad "%USERPROFILE%\Documents\ChatGPT\FxSourceArchive\candidates\review_unmatched\unmatched_review.json"
```

各未抽出発言に次の情報を記録する。

- `user_text`：設問番号のないユーザー発言原文（例：「Cを採用」）
- `preceding_assistant_text`：同じ会話の**親メッセージを遡って見つかった**先行アシスタント発言
- `possible_question_ids_from_assistant`：アシスタント側に登場した設問番号。**候補ヒントであり確定番号ではない**
- `assigned_question_id`：常に `null`、本人が原議文脈を確認する前に自動割り当てしない
- `review_status`：`UNASSIGNED_REQUIRES_HUMAN_CONTEXT_REVIEW`
- `missing_question_ids_in_this_conversation`：**この会話の明示的な番号付きユーザー発言**を基準にした未抽出番号。他の会話の決定が含まれる可能性がある

アシスタントの設問文が直前でない場合、会話枝の履歴を辿ります。会話の分岐/編集があれば複数候補が現れます。元JSONの形式により親参照を辿れないときは、**誤った番号を推定せずヒント無し**とします。

## 4. Q115の安全優先レビュー

最初はQ6、Q7、Q8、Q14（資金管理・NY日次区切り）を確認。その後Q28、Q60、Q102、Q106〜108など関連する原議も取り扱います。Q1〜8やQ51〜54は**別会話**にしかない可能性もあるため、`list_export_conversations.py` から対象会話を追加で特定して確認してください。

**留意事項**：34件の未抽出ユーザー発言と21件の欠けている設問番号が1対1で対応するとは限らない。AIの要約・アシスタントによる質問は「ユーザーが承認した原議」にしないこと。

このファイルにはユーザーの私的な会話が含まれる可能性があります。ChatGPTに全文を貼ったりGitHubにコピーしたりせず、必要なら番号・メッセージIDだけを共有してください。
