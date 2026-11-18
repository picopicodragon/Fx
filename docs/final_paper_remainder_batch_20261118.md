# FINAL-PAPER-57〜73 残工程一括開発：価格監視を止めずに安全性を前進

日付：2026-11-18 / ブランチ：feat/mt4-demo-final-e2e-20261117 /
PR #290。適用先はFX内部仮想テストに限定し、楽天MT4デモ/実口座には
OrderSendなどの売買命令を発しない。MT4 AutoTradingはOFF。

## 現在の実測事実（2026-11-18に利用者が報告）

- 最後に提示された運用台帳：153サイクル、現金・評価額各10万円、
  仮想取引・建玉0、AI推論累計6/6、追加課金許可なし。
- 停止区間106→107の3420秒（57分）は、利用者本人申告で
  **OPERATOR_ATTESTED_INTENTIONAL_STOP** と運用分類を確定。
  WER1001をPythonの異常終了と断定しない。
- 正常な手動停止でも、約57分のquote観測空白に対して
  **communication_latched=true** と記録され、以後は安全停止中。
  本人は停止理由を説明したが、**通信ラッチ解除やAPI予算増額を
  承認したわけではない**。
- 最後の復旧審査は138サイクルの時点で10件連続観測に合格。
  以後の監視継続はstatus報告から確認できるが、独立した
  ブローカー時計・今後の全重要イベント・コストは未認証。

## 一括開発の実装分と安全境界

| 工程 | 実装・テスト | 実運用での扱い |
| --- | --- | --- |
| 通信ラッチ解除前審査 | final_paper_reentry_review.pyで本人申告とjournal復旧条件を照合 | **レビューのみ**。ラッチ解除関数は既存運用に接続しない |
| 月額AI費用 | final_paper_budget_readiness.pyでJPY3,000円と、二モデル1回分（2コール）の予約枠を比較 | 請求額は人間の入力のみ。独立請求認証なし、6回上限維持、追加API呼出し不可 |
| 重要イベント | final_paper_event_coverage_audit.pyでUSD/EUR/JPYのローカル公式リンク候補・イベント数・欠落通貨を照合 | 既知イベント前後±900秒停止は維持。完全網羅やconsensus事前保存は未認証 |
| 新規仮想エントリー | final_paper_engine.pyに明示的entry_evidence_ready引数を追加 | ライブラリ単体の合成試験ではTrueにして模擬売買可能。**実行supervisorは未認証なら必ずFalse** |
| 有料二段階AI | final_paper_runtime.pyの初回推論前ゲートを強化。通信/DD/日次停止、観測ギャップ>600秒、イベント、独立認証不備で停止 | AutoTrading、Jev、実/デモ口座アクセスなし。現状AI6/6で追加課金不可 |
| 統合監査 | final_paper_release_matrix.pyとWindows用read-onlyスクリプト | 価格の継続観測可否と完全仮想自動売買の未達を分けて一覧化 |
| 結合・障害注入 | tests/test_final_paper_* に3ペア、注文禁止、二件リスク、DD5全決済、手動停止ギャップ、重要発表などの合成ケース | CI PASSはローカルMT4稼働や収益性の証明ではない |

重要：カレンダーの公式リンクが正しいとしても、原本の時刻・カバレッジが
独立に証明されたわけではない。OpenAIの料金計算もAPI回数から日本円に
換算できるわけではない。実機稼働中の旧Python監視プロセスは
今回のGitHubソース追加を**自動では読み込まない**。

## 監視を止めない確認手順

**稼働中のPowerShellをそのまま維持**し、別の安全なGit作業ツリー
Fx-PAPER-REVIEW-20261118 で、手元の未保存変更がないことを確認後：

    cd C:\Users\Suzuki\Documents\ChatGPT\Fx-PAPER-REVIEW-20261118
    if (@(git status --porcelain).Count -gt 0) { throw '作業ツリーがdirty' }
    git fetch origin
    if ($LASTEXITCODE -ne 0) { throw 'fetch失敗' }
    git switch --detach origin/feat/mt4-demo-final-e2e-20261117
    if ($LASTEXITCODE -ne 0) { throw '切替失敗' }
    python -m unittest discover -s tests -p 'test_final_paper*.py'
    if ($LASTEXITCODE -ne 0) { throw '単体テスト失敗' }
    .\scripts\final_paper_release_matrix_once.ps1

任意のローカル保存済み経済イベントファイルがある場合：
    
    .\scripts\final_paper_release_matrix_once.ps1 -EventCalendar $eventFile

請求額を提供する場合は、本人がOpenAIのBillingを確認した上で、
機密情報を含まない別の**Git管理外**JSONファイルを作る。
先に独立照合・課金許可なしの予備審査として扱い、
BillingStatementオプションは内容を審査してから使う。
既存AI利用6回のカウントをリセット・削除しない。

## 依然として完了していない、技術以外の受入条件

1. **通信停止ラッチの実解除に対する本人の明示的承認**、
   原子性・単一運用・journal追記設計とその実機安全検証。
   現在のプログラムは過去の正常停止の分類だけを採用済み。
2. **実際のOpenAI請求額**、JPY換算と二モデル次回費用の
   事前確保、未確定APIディスパッチの扱い、月額3,000円の
   厳格上限の実装と新規有料推論の明示的承認。
3. **USD/EUR/JPY全ての公式経済発表日時**と市場コンセンサスの
   公表前アーカイブ、発表前後15分のBlackout、独立ブローカー時計。
4. **楽天MT4実機での次の開始試験**、保有・決済・損益・取引
   コストの実測。取引数0の状態から収益性は評価できない。
5. Q109/Q110の安全コードトレーサビリティとフェーズ承認。
   自動テスト成功は本人による完成版承認とは異なる。

今後も、実デモ/本番発注・Jev・未承認の追加AI利用は許可しない。
