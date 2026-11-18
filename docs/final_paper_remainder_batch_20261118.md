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


## 一括開発の追補：2026-11-18 後続工程

- 公式のBLSカレンダーは米国の一部の経済指標の発表予定であり、
  全てのFX主要イベント、ECB、日銀の予定や市場コンセンサスまで
  保証していない。research/final_paper_bls_event_archive.py は
  **保存済み**のBLS ICSをオフラインで厳格解析し、
  CPI・雇用統計・PPIなどの識別可能な米国イベントを、
  既存のUSD重要イベント停止用research JSONに変換する。
  不明な発表は勝手にCRITICALにしない。ネットアクセスなし。
- BLS公式カレンダー保存済みファイルの利用例
  （実際のファイルと実際の取得時刻がない場合は実行しない）：

      python -m research.final_paper_bls_event_archive \
        --ics-file <保存したBLSのICSパス> \
        --asof-utc <実際の原本保存日時をUTCで> \
        --days-forward 14 \
        --out <新規保存先のJSON>

  上記はPython用の説明例。PowerShellでの改行継続は
  バッククォートを使用すること。
- Q109の既存45件の保護対象・Q110の元の受入台帳は、
  **旧オフライン基準として固定されている**ため変更禁止。
  本スプリントの安全コード／テスト対応は
  specs/final_paper_q109_traceability_extension_20261118.json、
  TASK/MODULE/PHASEの未承認・保留情報は
  specs/final_paper_q110_acceptance_extension_20261118.json
  に別管理する。旧CIの基準値を書き換えて通過と見なさない。
- Linux/Windowsの全件CIと、合成3通貨・DD5・通信ラッチ・
  指標停止の新規テストを確認したうえで実機評価へ進む。
  自動マージ、通信ラッチ解除、有料AI追加利用は承認していない。


## FINAL-PAPER-87〜93：221回の観測監査後、MT4実測スプレッド・契約属性の保存

ユーザー実機が2026-11-18 16:00に報告した統合監査：
completed_cycles=221（153回から+68）、
latest_quote_age_seconds_pc_derived=16、FRESH、
price_feed_observation_viable_now=true、
historical_manual_stop_attested=true、
recent_continuity_review_sufficient=true。
しかしcommunication_latched=true、AI利用6/6（未承認の追加課金は禁止）、
保存済みUSD/EUR/JPY経済イベント0、calendar_sourceの独立照合なし、
MT4時計・取引コスト未検証、NO_GOのまま。

ローカルで既存の価格監視を**停止・再起動・変更せず**に、
MT4 MQL4/Filesの最近10件までの3ペアCSVを安全に読み取り、
スプレッドの最小・最大・平均、各ペアの契約属性の変化件数、
30〜90秒の観測間隔を記録する補助監査を追加：

    .\scripts\final_paper_quote_contract_audit_once.ps1 -Mt4FilesDirectory $mt4Files

また既存統合監査にも、オプションを追加した：

    .\scripts\final_paper_release_matrix_once.ps1 -Mt4FilesDirectory $mt4Files

上記いずれも**実際のMT4 Filesディレクトリ**を指定する。
スクリプトは最新の価格CSVだけを照合し、broker発注命令は出さない。
CSV内のbid/ask/口座IDの原文を監査出力に書かず、集計済みの
スプレッドpips・契約属性の出現件数と局所ハッシュ数のみ保存する。

重要：観測されたスプレッドは過去10件の記録に過ぎない。
**委託手数料、スリッページ分布、スワップ、約定価格、ブローカー時刻の
独立認証にはならない**。したがって、
TRANSACTION_COSTS_NOT_FULLY_ATTESTED
と INDEPENDENT_MT4_CLOCK_ATTESTATION_ABSENT は監査の後も残る。
上限6回の追加AI呼出しを許可せず、通信ラッチも解除しない。

対応コード：
research/final_paper_quote_contract_evidence.py、
scripts/final_paper_quote_contract_audit_once.ps1、
tests/test_final_paper_quote_contract_evidence.py。
Q109は既存の固定台帳を壊さず、
specs/final_paper_q109_traceability_extension_20261118.jsonへ追記。


## FINAL-PAPER-95〜97：244サイクル・70秒のLEVEL1警告とMT4生CSVの判定差

2026-11-18 16:24の実機監査：244サイクル（221から+23）、
最後の処理済みquote経過70秒、厳格な監視FRESH=false、
MT4生CSVのsample freshness=true、10件のUSD/JPY 0.5pips /
EUR/JPY 1.0pips / EUR/USD 0.5pips。通信停止ラッチtrue、
有料AI 6/6、MT4注文禁止、NO_GO。

実装上の境界は異なる：
- research/final_paper_status.py：journalの最終quote経過0〜59秒は
  FRESH、60〜599秒はLEVEL1、600秒以上はLEVEL2。
- research/final_paper_quote_contract_evidence.py：最近のMT4生CSVは
  120秒以内ならsample fresh。それを超えるとfalse。
- 読取時刻は一度の原子的なスナップショットではない。

従って70秒で journal LEVEL1 と MT4 raw fresh が同時に成立しうる。
これは自動的に通信障害再発やPythonの異常終了の証拠ではない。
60秒基準は120秒に緩めず、LAST_QUOTE_NOT_FRESHブロッカー、
通信停止ラッチ、AI課金停止、注文禁止を維持する。

統合監査に、journal warning level、明示的な60秒未満/
120秒以内の閾値、raw sample age、鮮度ラベル差異、
時計測定が非原子的・未証明であることを追加した。
テストは244件/70秒の実機と同型の合成データと、
生CSVの59、60、70、120、121秒の境界を確認する。

同じ状態が繰り返され、実機でproducer/consumerのどちらに
遅れがあるか確認したい場合は、監視用PowerShellを止めず
別のウィンドウで次の読取専用診断を実行する：

    .\scripts\final_paper_stream_diagnostic_once.ps1 -Mt4FilesDirectory $mt4Files

生CSVが一時的にjournalより新しいだけで、監視が停止したとは
断定しない。10分を超える新しい障害が確認される場合に限り、
Windows/Pythonログを追加調査し、安全停止を維持する。
