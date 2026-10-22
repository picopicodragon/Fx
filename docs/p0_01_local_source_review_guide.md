# P0-01：Q5～Q14原議候補のローカル照合

記録日：2026-10-22。範囲：Q115/P0-01（FX-SAF-001～006）。
状態：本人原議照合未完了、安全実装・本番取引未承認。

元会話はユーザー確認済み「FXシステム仕様策定」（ID 6aceda54-1388-83e8-ad0a-6edfc39ad11d）。

## ユーザーによるローカル抽出結果

元JSONと候補ファイルのSHA-256照合は SourceMatches=True。明示回答候補94件、未割当ユーザー発言34件、重複Q番号0件、Q1～115の明示抽出未該当番号21件。候補数であって原議の正式照合や安全承認ではない。

| Q | 明示番号回答 | 先行assistant文脈ヒント |
| --- | ---: | ---: |
| Q5 | 0 | 1 |
| Q6 | 0 | 2 |
| Q7 | 0 | 2 |
| Q8 | 0 | 2 |
| Q9 | 1 | 0 |
| Q10 | 1 | 0 |
| Q11 | 1 | 1 |
| Q12 | 1 | 0 |
| Q13 | 1 | 1 |
| Q14 | 0 | 2 |

複数の設問ヒントが一つの未割当回答を参照し得る。Q11/Q13の明示候補と未割当候補は後続の修正/追補かもしれないため原議を要確認。

## ローカルPowerShellのコマンド

GitHubのPRを本人が手動マージした後、作業フォルダー C:\Users\Suzuki\Documents\ChatGPT\Fx で実行。未コミット変更があれば切替前に中断する。

    git status
    git switch main
    git pull --ff-only origin main

次のコマンドは1行で実行する。

    python -m scripts.build_p0_01_review_worksheet --input "C:\Users\Suzuki\Documents\ChatGPT\FxSourceArchive\originals\conversations.json" --conversation-id "6aceda54-1388-83e8-ad0a-6edfc39ad11d" --out-dir "C:\Users\Suzuki\Documents\ChatGPT\FxSourceArchive\candidates\p0_01_review_20261022"

出力：C:\Users\Suzuki\Documents\ChatGPT\FxSourceArchive\candidates\p0_01_review_20261022\p0_01_worksheet.json

既存ファイルは上書きせず終了するため、再実行は新たなフォルダーを選ぶ。作業はローカル・オフラインのみで原本を変更しない。出力JSONにはプライベートなユーザー・アシスタント原文が含まれうるため、全文をChatGPTやGitHubに送らない。

## 本人の照合手順

1. Q9～Q13の明示回答は、直前の質問/選択肢/後続修正を人間が原議と照合する。ユーザー発言にQ番号があるだけでは原議と仕様の内容一致を証明しない。
2. Q5～Q8とQ14は先行assistantからの番号ヒントを手動確認する。ヒントは割当済み回答ではない。
3. Q11とQ13の未割当候補は、明示的回答の追補/修正/無関係な応答かを判断する。長文に複数Q番号があれば自動割当しない。
4. Q116以降の後続決定を含めて最終的な要件を確認する。元エクスポートの作成日以降の発言が欠ける可能性を保持する。
5. 照合済みの必要最小限の抜粋、機密審査、仕様への反映、本人の実装承認をそれぞれ別に記録する。

照合表の全項目はOWNER_CONTEXT_REVIEW_REQUIRED、選択メッセージはnull、安全承認はfalse。Git管理外に保存した原議とローカル照合表をGitHubへ登録しない。

本PRはオフライン用スクリプト、合成データによるテスト、本ガイドのみ。specs/source_evidence.json、specs/reconciliation_registry.json、specs/acceptance_registry.jsonの承認値を変更しない。P1-01/PHASE-1のBLOCKEDを維持する。

forward_trading_enabled=false
implementation_approved=false
human_safety_approval=false
owner_approved_for_safety=false

Q171の隔離失敗時本人承認必須ラッチ、Q195～199の結果不明時の無確認再送禁止を維持。MT4接続・注文・EA・復旧のコード実装は含まない。

## 2026-10-22追記：Q9～Q13は本人申告MATCH（設問単位のみ）

ユーザーがローカル照合表を生成後、「Q9: MATCH」「Q10: MATCH」「Q11: MATCH」「Q12: MATCH」「Q13: MATCH」と回答した。GitHubには**本人による設問単位の照合申告**として、`specs/p0_01_owner_question_matches.json`に記録し、該当するFX-SAF-001/003/004/005の`partial_owner_question_matches`に対応付ける。

**これは5設問に対する本人の比較結果であり、元の会話原文や選択肢、ローカルの完全な照合表をChatGPTが確認できたことを意味しない。** 原文抜粋のGitHub登録、原議全体の独立検証、実装算式の確定、Q116以降の改訂との整合、承認を示すものではない。

Q11とQ13には明示番号候補に加え未割当の文脈ヒントが各1件あるため、それらの追補・修正・無関係性の**個別解決は未確認**として保持する。Q5～Q8・Q14の人間確認も未完了。

要件単位の`source_kind`、`comparison_status`、`implementation_approved=false`、`owner_approval=null`と、`specs/source_review_priority.json`の`PENDING_ORIGINAL`を維持。安全重要MODULE/PHASEのBLOCKED状態と、本番売買禁止を解除しない。

## 2026-10-22追記2：Q5～Q8はMATCH、Q14はUNCLEAR

本人によるローカル照合結果は **Q5、Q6、Q7、Q8 = MATCH**、**Q14 = UNCLEAR**。追加の部分照合記録は `specs/p0_01_owner_question_reviews_round2.json`、安全要件台帳への参照は `specs/reconciliation_registry.json` に登録した。

Q14についてユーザーが確認した原文候補は、**ニューヨーク市場17:00が日本時間で何時かを尋ねる質問**であり、NY17:00基準を採用した原議の直接証拠ではない。その質問に対する採用回答を確認できるまで、Q14の原議比較はUNCLEARを維持する。Q14の別の文脈ヒント・後続決定も照合未了。

時刻換算の参考：America/New_Yorkの17:00は日本の翌日06:00（米国夏時間EDT）または07:00（米国標準時間EST）。これは設計上の換算説明であり、当時の**採用の意思表示**の代わりにはならない。現行`MASTER_SPEC.md`のQ14設計はこのレビューだけでは変更しない。

Q5～Q13の9設問の本人申告MATCHは**設問単位の部分照合**。Q11/Q13の追加文脈候補、Q116以降の改訂、FX-SAF-001～006各要件の未確定実装条件や安全承認は引き続き未解決。要件単位の`source_kind`、`comparison_status`、承認フラグ、PHASE-1 BLOCKEDおよび本番取引禁止を維持する。
