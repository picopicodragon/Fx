# FINAL-PAPER-126〜131：Windows実機・外部原本の安全な接続

対象は**楽天MT4 DEMOからの読み取り専用価格観測**と10万円の内部仮想ポートフォリオ。
本書は実機・外部証拠の取り込み手順であり、自動的な注文許可やAI課金許可ではない。

## 接続レベル

- 現在のChatGPT GitHub接続では、ユーザーPCのWindowsプロセス、MT4のGUI、
  MQL4/Files、OpenAI組織管理画面を直接開けない。
- GitHub PR上のコード実装とCIは直接実行できる。
- Windows実機プロセスの診断はユーザーが**別PowerShell**からコマンドを
  1回実行する必要がある。現在のMT4やPython監視ウィンドウは触らない。
- Win+Lによるロックだけなら通常監視は継続。スリープは停止要因。
- 人間の以前の「通信ラッチ解除」承認は#106→#107のみ。実機のラッチ解除は
  #291手順の安全条件と停止操作を別途満たすまで実行されない。

## Step 1: 監視中のプロセスを変更せず別のGit作業ツリーを更新

PowerShell（監視しているウィンドウとは別）で次を実行する。
当該Git作業ツリーに未保存変更があれば決して切り替えない。

    cd C:\Users\Suzuki\Documents\ChatGPT\Fx-PAPER-REVIEW-20261118
    if (@(git status --porcelain).Count -gt 0) { throw 'Worktree dirty. NO_GO' }
    git fetch origin
    if ($LASTEXITCODE -ne 0) { throw 'Fetch failed. NO_GO' }
    git switch --detach origin/feat/final-paper-windows-evidence-handoff-20261120
    if ($LASTEXITCODE -ne 0) { throw 'Switch failed. NO_GO' }
    python -m unittest discover -s tests -p "test_final_paper*.py"
    if ($LASTEXITCODE -ne 0) { throw 'Safety tests failed. NO_GO' }

この操作はレビュー作業ツリーだけで行い、稼働中監視のフォルダは切り替えない。

## Step 2: 外部ネットワークなしでWindows実機診断

以前と同じ $mt4Files が対象の実 DEMO MQL4/Files を指しているなら:

    .\scripts\final_paper_collect_external_evidence_once.ps1 -Mt4FilesDirectory $mt4Files

このコマンドはWindowsプロセス数、過去3件のMT4価格CSVのハッシュ、
最新ジャーナルの数とハッシュ、Expertsの過去の起動ログの有無、
Windows時刻同期サービスのコマンド成否を収集。
別ウィンドウのPython監視を止めない。鍵・口座番号・bid/askは出力しない。

**少なくとも60秒以上あけて2回実行**し、２つの JSON の
journal_file_count、最新quote filename/hashが増加していることを照合。
単一時点のプロセスの存在は「稼働継続」の証明ではない。
結果を持ち込む際にフルパスや秘密情報の転送は不要。

## Step 3: 公式Web原本を読み取り専用で保存（明示ネットワーク許可）

    .\scripts\final_paper_collect_external_evidence_once.ps1 -Mt4FilesDirectory $mt4Files -AllowPublicNetwork

収集先はユーザーのFXForwardEvidence/final_virtual_paper/official_public_capture_*
フォルダ。各ページの取得時刻とSHA256を保存し、全ページ未取得なら
失敗/一部欠損と明示。リダイレクト・大容量・非HTTPS等は拒否。
対象：
- BLS公式ICS（米ドルの指標予定の一部）
- FRB/FOMC会合予定（USD）
- ECB政策理事会の予定（EUR）
- 日銀公表予定（JPY）
- 楽天MT4取引ルール（取引手数料等）
- 楽天MT4スワップ・スプレッド

原本のハッシュ保存は公式の全重要イベント網羅性や**発表前**
市場コンセンサスの存在を保証しない。局所PC時計は独立時刻ではない。
重要イベント前後15分の停止は引き続き未検証であれば新規entry不可。

## Step 4: OpenAIの実請求額の参照（任意）

OpenAI API組織管理権限がある場合は、OpenAIの**Admin API Keyを
PCの環境変数 OPENAI_ADMIN_KEY だけに設定**し、その値をチャットやGitに
一切入力しない。さらに:

    .\scripts\final_paper_collect_external_evidence_once.ps1 -Mt4FilesDirectory $mt4Files -AllowPublicNetwork -ReadOpenAICosts

公式の /v1/organization/costs に一回、GETする。推論やPOSTは0回。
月初UTCから現在までの**組織全体のUSD**費用を取り込み、管理者鍵を
ローカル外へ保存/表示しない。
- 組織の全費用は本FXシステムだけのコストとは限らない。
- USD値だけでは厳格な「月3000円」判定は完成しない。
- Costs APIのアクセス権がなければOpenAIの Analytics > Usage から
  実請求額を本人が確認・安全に転記する。
- 古いAI予算6/6は維持し、無断で増額・更新・呼出ししない。

## Step 5: 外部費用・時刻・マクロ証拠の受入

楽天証券の公開資料では取引手数料は無料だが、滑り・
スワップ・実行可能価格の分布をこのPCのquoteから証明できない。
独立時刻、過去/将来のUSD/EUR/JPY重要発表全件、発表前consensus原本、
外部請求の円換算証拠が揃わない限り、paper entry GOは出さない。

**コードの実装とGitHub CI PASSは実機証拠ではない。**
本スクリプトは安全ラッチ解除、live新規仮想売買の許可、MT4発注、
追加有料APIをどれも実行しない。
