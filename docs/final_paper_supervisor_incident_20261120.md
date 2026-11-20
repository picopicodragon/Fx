# FINAL-PAPER-132〜136: 2026-11-20 Python監視停止と残留ロックの実機診断

## 監査された事実 (2026-11-20 11:30〜11:32 JST)

- Rakuten MT4 terminal.exe = 1、observerの3通貨価格CSVは
  FxPaperQuote_20261120_022956.csv → ...023156.csvと2分間で更新。
- Windowsの paper supervisor Python実行プロセス = 0。
- journal_file_count = 550で変わらず。
- journal最新価格 capture_epoch=1795004931
  （2026-11-18 21:28:51 JST）。
- MT4最新価格 capture_epoch=1795141796
  （2026-11-20 11:29:56 JST）、差136,865秒、約38時間。
- 2026-11-20 11:30時点 PC由来最終処理経過136,906秒、LEVEL2。
- .single_operator.lock 残存。これは可能性として**残留ロック**だが、
  異常終了・Windows再起動・手動操作のどれが根本原因か未確定。
- 過去の #106→#107 手動停止と今回の38時間途絶は別の事象。
  古い通信ラッチ解除承認を今回へ拡張しない。
- 当該5ゲートは0/5、建玉0、追加有料AI6/6上限消費。
- BLS/FOMC/ECB/BOJ/Rakuten計6件の公開原本が2026-11-20
  取得成功。ただし完全な経済イベント、発表前consensus、独立時計、
  全実コストの独立証明ではない。

## 本PRの改修

- research/final_paper_supervisor_incident.py：
  現行journal全件ハッシュのロード・二回ヘッド一致、AI台帳の6/6一致、
  MT4生価格と処理済quoteの断絶差分、通信/DDラッチ、
  残留ロックのファイル長・SHA256・mtimeを読み取り専用で保存。
- scripts/final_paper_supervisor_incident_once.ps1：
  Win32_ProcessでPython 0件かを確認。プロセスコマンドラインやキーは
  出力しない。判定は事実「POSSIBLE_ORPHAN_LOCK」であり原因断定ではない。
- scripts/final_paper_collect_external_evidence_once.ps1：
  先のログで表示された
  "A child command set a nonzero exit" は、PowerShell子スクリプト後に
  残った古い $LASTEXITCODE を参照して発生する**誤警告**だった。
  その不要な警告条件のみを削除。stop/restart/lock変更多しなし。
- 回帰テストではjournal race・危険なロックをfail closed、
  ロックの有無に関係なく自動復旧させないことを確認。

## Windows現場での次の安全な一回診断

**現在のロックや監視ウィンドウを削除・変更しないこと。**
新しい作業ツリー/ブランチを取り込み、
以前と同じ $mt4Files がRakuten DEMO MQL4/Filesを指す状態で：

    .\scripts\final_paper_supervisor_incident_once.ps1 -Mt4FilesDirectory $mt4Files

保存される supervisor_incident_*.json の
- journal_cycles / journal_head_sha256_local_only
- unconsumed_quote_gap_seconds_pc_derived
- runtime_lock_sha256_local_only / runtime_lock_last_write_utc_pc_unattested
- journal_communication_latched / other_risk_latches
- paid_calls_journal / paid_calls_completed_ledgers
を確認する。ログに秘密情報やIDを出力しない。

Python停止の原因について、直前の**Python監視PowerShell**の最後の
「PAPER_RUNTIME_FAIL_CLOSED_REVIEW_LOCK_AND_LEDGER」などの表示、
Windowsのイベントビューアー Application / System の
2026-11-18 21:28 JST以降の異常終了・更新・停電履歴を照合する。
端末がロック中にスリープ・更新再起動したかは未証明。

## 復旧境界

この時点では paper_supervisor_process_count=0 であると同時に
.single_operator.lock=true なので、通常のstartスクリプトは拒否する。
**ロックを手動削除しない、同じローカルjournalを別環境で起動しない、
古い通信解除permitを再利用しない。**

原因と既存ジャーナル・外部台帳の整合を確定した上で、
別途監査済み**一度限りの有人復旧操作**を設計する。
有人復旧ができても他リスク停止と新規仮想売買ゲートは残る。
月3,000円予算の課金確認・独立時刻・マクロ原本網羅は未完。

新規有料AI0件、MT4デモ/実注文0件、mainマージなし。

## 追加：一度限りの有人・無課金価格観測リカバリ（新規仮想売買ではない）

Python監視ウィンドウ末尾・Windowsイベントログを確認し、今回の停止理由を
可能な範囲で調査した後、**本人が無料観測だけの復旧を明示選択**する場合に限り、
安全ロックを削除せず、原本のまま別名アーカイブする機構を追加した。

この回復操作は対象を**journalが550サイクル、最終quote epochが1795004931**
である今回の停止1件に限定する。次のいずれかでは拒否：
- Python監視が1件でも存続、またはプロセスCommandLineが見えず確認不能
- 最新MT4価格が120秒を超過、PCとbrokerの時刻が不整合
- journalやAI台帳のハッシュ・6/6照合不一致、元のjournalが550から変化
- 仮想建玉またはpending signalが存在、DD・日次損失の他停止あり
- 古い通信解除許可ファイルが存在、リカバリ済みの証拠が存在
- 原本ロック内容が期待と異なる、ファイルリンク/パスが不適切

**安全な最初の操作**は、読み取り専用の調査のみ：

    .\scripts\final_paper_supervisor_incident_once.ps1 -Mt4FilesDirectory $mt4Files

今回の停止履歴・OSエラーを確認し、本人が無課金観測だけの再開を
明示選択した場合の**別の操作**：

    .\scripts\final_paper_manual_observation_recovery_once.ps1 -Mt4FilesDirectory $mt4Files -ApproveObservationOnlyRecovery

原本ロックは削除せず
`manual_observation_lock_20261120.archived`
として同じstate rootに保存し、journal SHAを含む一回限りのreceiptを記録。
このコマンドは**Python監視の起動も通信停止ラッチ解除もしない**。
解除されたのは「異常終了で残った監督の排他ファイル」という
ローカル運用ブロッカーだけであり、金融リスクを許可していない。

その後、free preflightがPASSした場合のみ別PowerShellから
（AutoTrading OFF、追加API指定なし）無料価格観測を人間が起動：

    .\scripts\start_final_paper_virtual.ps1 -Mt4FilesDirectory $mt4Files

この呼び出しはCtrl+Cまで継続。新規仮想建玉は安全停止を維持し、
6/6 AI再利用は不可、ブローカーへの注文は0。
新しい38時間の通信停止ラッチは**人間からの別の明示解除承認と
独立安全確認が整うまで停止**する。
