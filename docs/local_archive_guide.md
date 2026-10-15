# Windowsでの設計原議保存・抽出手順（Q114）

> 状態：**実行手順と初期ツールを用意した段階**。ユーザーPCでの保存、実際のエクスポートを使った結合試験、原議の全面照合は**未実施**。
> ChatGPTのデータエクスポート形式やUIが変更される可能性があるため、必要に応じて動作確認・形式対応を行う。

## 方式

第114問は**C：ハイブリッド型**。必要な設計対話を直接保存する方法と、ChatGPTアカウントのエクスポートを取得して対象会話を抽出する方法を併用する。抽出はPythonの標準ライブラリだけで実施し、**抽出結果はすべてレビュー前の候補扱い**。GitHubへの自動書込み・自動承認・本番注文は行わない。

## Windowsのローカル保存先（例）

以下は推奨されるフォルダの一例。ユーザーのPC上で実際に作成する必要がある。

```text
C:\FxSourceArchive\
  originals\           # 原本の会話コピー、エクスポートZIP/JSON（Git管理外）
  candidates\          # Pythonが生成した決定文候補（Git管理外）
  checked\             # 本人が検証した抜粋の作業ファイル（Git管理外）
```

**Fx Gitリポジトリの外**に保存する。原本ZIPや `conversations.json` は、他の会話・個人情報を含む可能性があるため、そのままGitHubへ登録しない。共有PC環境ではローカルフォルダへのアクセス権とWindowsの暗号化を検討する。第60問で決めたローカル保存方針と混同せず、原本の誤消去リスクを管理する。

## 方法A：必要なユーザーの発言を個別保存

元会話のユーザー発言を、そのままUTF-8テキストとして `C:\FxSourceArchive\originals\q114_user.txt` に保存。**AIによる要約やアシスタント発言を原文の代わりに保存しない**。短い「CでOK」だけでは設問番号が分からない場合、原文と前後の質問の参照位置を手動で補う。

```powershell
cd C:\path\to\Fx
py -3 scripts\extract_original_decisions.py --input "C:\FxSourceArchive\originals\q114_user.txt" --format manual --question Q114 --out-dir "C:\FxSourceArchive\candidates\q114"
```

`--question` は**人間が元の対話を確認して指定する**。これによって原議との一致が自動的に認証されるわけではない。

## 方法B：ChatGPTのエクスポートを利用する

ChatGPTからデータをリクエストする場合は、対応しているアカウントで「設定 → データ管理（Data controls）→ データのエクスポート」を利用できる。エクスポートを解凍し、`conversations.json`（または分割された該当JSON）を探す。サービス側の形式や案内は変更される可能性がある。

OpenAI公式案内：https://help.openai.com/ja-jp/articles/7260999-how-do-i-export-my-chatgpt-history-and-data

まず対象会話のIDをローカルの一覧から探す。

```powershell
cd C:\path\to\Fx
py -3 scripts\list_export_conversations.py --input "C:\FxSourceArchive\originals\conversations.json" --filter "FX"
```

該当する会話IDを確認してから、**1つの会話のみ**を選択して抽出する。

```powershell
py -3 scripts\extract_original_decisions.py --input "C:\FxSourceArchive\originals\conversations.json" --format export --conversation-id "ここに実際の会話ID" --out-dir "C:\FxSourceArchive\candidates\fx_design"
```

抽出後、`candidate_decisions.json` を確認する。この初期ツールは、冒頭に「第114問は」「Q114：」など**明示的な設問番号があるユーザー発言**だけを候補として拾う。単なる「CでOK」や編集履歴による重複は、人間が文脈を確認して補正する。相違があれば抽出結果を無条件で正としない。

### 現段階の機能制限

- 対応するエクスポート構造：一般的な `conversations.json` の会話配列、各会話の `id` と `mapping`、ユーザー発言 `message.author.role == user` と `content.parts`。**実際のユーザーのファイルに対しては未検証**。
- 添付画像・音声・外部ファイル等の非テキストコンテンツは抽出しない。
- 特定の会話IDが分からない場合、自動で全会話を抽出・アップロードすることはしない。
- ファイルのSHA-256を候補JSONへ記録。ただしハッシュだけで発言内容の真正性や元サービスとの一致を保証できない。
- 自動の機密情報検出・伏せ字処理は未実装。GitHubへ入れる前に本人が原文と照合し、個人情報や鍵等を除去・確認する。
- 同じQ番号が複数出現した場合は候補を残し、`duplicate_question_ids` で知らせる。最終決定は人間が原議文脈に沿って判断する。

## GitHubへ登録する前の確認

1. `candidate_decisions.json` の `user_text` を元の会話原本と照合する。
2. 仕様IDの重複、未確定の設問、後から変更された決定がないか確認する。
3. 氏名、認証情報、メールアドレス、口座情報、不要な会話が含まれないようにする。
4. **照合済みの必要な発言だけ** `specs/source_excerpts/Qxxx.md` へ転記する。伏せ字が必要な場合はその旨を記録する。
5. `specs/source_evidence.json` へ原議所在、確認状況、抽出状態を記録。安全重要仕様の本人承認は `specs/reconciliation_registry.json` 側で**別途**管理する。
6. CodexがPRへ追加し、GitHub Actionsの検証後、本人が差分を見て手動マージする。

**このツールの生成した候補を自動で`ORIGINAL`や`MATCH`や`implementation_approved=true`に昇格させない。**

## 今回の到達点

ツールとテストをGitHub作業ブランチへ配置しただけであり、ChatGPTデータの一括エクスポートの請求・取得、原議全文のWindows保存、Q1〜112の根拠抜粋・照合は実行していない。
