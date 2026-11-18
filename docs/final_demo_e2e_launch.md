# DEMO-SPRINT: Rakuten MT4 最終テスト版の統合実行手順

## 目標と実装境界
公式ニュース/マクロイベント → 構築AI → 独立レビューAI → デモ注文意図 → MT4側H1 EMA/ATR・安全判定 → 楽天MT4デモ限定の注文・決済。実口座注文は含まない。AIがHOLD、証拠が不足、口座/安全条件が不正なら発注しない。

今回の実装は「統合候補コード」。一括実行CLIとデモ専用EAを実装したが、MetaEditorの実コンパイル、楽天MT4デモの実約定、連続無人運用、独立時計/口座確認は未完了であり、最終テスト版の運用合格とは呼ばない。

## Windowsの一括入口（発注禁止のまま確認）
以前の別worktreeを継続使用。変更がある場合は上書き・強制リセットせず停止する。

    cd C:\Users\Suzuki\Documents\ChatGPT\Fx-MACRO-FWD-20261113
    if (@(git status --porcelain).Count -gt 0) { throw "作業ツリーに変更があります" }
    git fetch origin
    if ($LASTEXITCODE -ne 0) { throw "fetch失敗" }
    git switch --detach origin/feat/mt4-demo-final-e2e-20261117
    if ($LASTEXITCODE -ne 0) { throw "切替失敗" }
    python -m unittest discover -s tests -p "test_final_demo*.py"

デモ口座番号をローカル画面で入力し、利用可能なAPIモデル名2つをそれぞれ設定する。口座番号/鍵をチャットやGitHubに貼り付けないこと。

    $account = [int](Read-Host 'Rakuten MT4 DEMO口座番号')
    $analyst = '<利用できるAPIモデルID: 仮説構築>'
    $reviewer = '<別のAPIモデルID: 独立レビュー>'
    .\scripts\final_demo_once.ps1 -ExpectedDemoAccount $account -AnalystModel $analyst -ReviewerModel $reviewer -AllowOfficialFeedNetwork

このコマンドはFRB/BLSの公式3系列を1回取得し、最新実イベントと既存AI台帳を検証する。初期設定はAI API課金0、発注意図0、MT4操作0。新しい実イベントがないならNO_SIGNAL/HOLDが正しい。出力データを捏造して進めない。

## 2モデルAIのオプトイン
OpenAI APIの課金を伴う処理は、実在の最新マクロイベントがあり、ローカル環境にOPENAI_API_KEYが設定され、スイッチ -AllowPaidAi を明示したときだけ行う。1実行あたり最大2回、NY17日付で最大3イベントを上限とする。送信後の不明なpendingを自動再送しない。

## MT4での実注文前に必須の実機確認
候補EA：mt4/demo/FxFinalTestDemoExecutor.mq4。既定EnableDemoOrders=false。

1. 一台の楽天MT4デモ・一つのUSDJPYチャートだけ。DEMO口座タイプ、口座番号、JPY口座通貨を本人確認し、別EA・手動建玉・未約定注文と混在しない。
2. 手動でMetaEditorコンパイル（0 errors）。警告・EAソース・取引APIを目視確認する。GitHub CIはMQL4コンパイルの代わりにならない。
3. 日次NY17時点の口座純資産、UTC epoch、高水準の純資産を原本証拠付きで確認し、それぞれVerifiedNy17StartEquityJPY、VerifiedNy17StartEpochUtc、VerifiedPeakEquityJPYに設定する。未検証の数字を仮置きしない。
4. 最低ロット、LotStep、tick size/value、ストップレベル、注文拒否、リスク0.5%/合算1%/日次1.5%/DD4%・5%停止、障害時の建玉決済と停止状態をデモ実機で試験する。これらに未合格ならEnableDemoOrdersをfalseのまま保持する。
5. すべてが検証された場合に限り、ユーザーが明示的にDEMOのEAとAutoTradingを有効化する。Python側の指示出力も別途 -AllowPaidAi -EnableDemoIntent -Mt4FilesDir <当該MT4のMQL4\Files実パス> を指定したときだけ有効。90秒の短い期限と口座番号・イベントSHAを再照合し、消費済みマーカーを先に保存する。
6. デモでの約定・手仕舞い・R到達後のATR追従・損失停止・再起動・回線断の結果を確認してから、無人連続運用へ進む。

**注意：** このEAのリスク監視は初期段階で本人が正しいNY17基準/ピーク値を提供する前提。自動日次切替や連続稼働の実証は未完。技術実装が存在しても運用合格を意味しない。

## リリースの現状
実口座注文は禁止。現在の口座観測ジャーナルは実イベント0件であることがユーザーのログから確認されている。今後新しいニュースを収集しても、独立AIレビュー、テクニカル、リスクのすべてを通るまでデモ注文指示は生成されない。main最終マージ、EAの実機導入、デモでの発注許可は別途本人が決定する。


## 2026-11-17 実機MetaEditor警告への即応 (DEMO-SPRINT-19〜20)

利用者の楽天MT4 MetaEditorから、FxFinalTestDemoExecutor.mq4の313行目に「check operator precedence for possible error; use parentheses to clarify precedence」と表示され、コンパイルは0 errors / 1 warningsだった。

対象は既存ポジションのトレーリング管理で「自EA以外のmagic番号である」または「注文がBUYでもSELLでもない」を拒否する条件。既存の論理意味は変えず、AND条件とOR条件の括弧を明示した。今後の回帰テストはソースで明示的な括弧を確認する。

Windowsでは必ず最新版PRブランチをfetchしてから、古いEAソースのバックアップを保存し、MT4の一台だけの該当デモ端末に手動配備してMetaEditor F7を再実行する。**0 errors、0 warnings**を現地で確認するまでは、取引許可をONにしない。たとえ0 warningsになっても、リスク/日次境界/実約定検証は別途残るため、EnableDemoOrders=falseを維持する。
