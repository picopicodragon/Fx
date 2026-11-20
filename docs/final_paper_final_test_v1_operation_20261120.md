# FINAL TEST V1：一括起動判定（無注文・無課金・観測運用）

## 運用の範囲（2026-11-20）

既にWindows上で稼働する楽天MT4 DEMO読み取り専用EAとPython supervisorを
**停止・起動せずに利用**し、最終テスト版の「観測・安全試験」フェーズへ移行する。
ユーザーの長時間観測を尊重し、複数PRの枝分かれを増やすことなく1コマンドで検証する。

仮想新規建玉を伴う完全なAI自動売買の本番テストではない。
通信停止ラッチ、独立マクロ/予測/時計/コスト、AI課金6/6という
本質的な不足を無視して運用GOにはしない。

## ワンコマンドで検証するもの

- Windows上のPython監視が1プロセス、MT4が1プロセスであることを2時点で観測。
- 両時点で同じPython PID/開始時刻、75秒経過、3通貨の実価格更新を確認。
- 安全ジャーナル全件ハッシュと連続追記、実AI台帳6/6一致、通信ラッチ残存を確認。
- 保存済みBLS/FOMC/ECB/BOJ/楽天2件の公式6原本SHA256とmanifestを照合。
- 最新MT4実CSVの元SHAと契約・bid/ask・時刻整合を検査。
- 3ペアの合成APPROVEDシグナルを**隔離メモリ内だけ**で使用し、
  実行エンジンが通信停止中の建玉を拒否し、別の純粋シミュレーションで
  仮想リスク0.5%以下または最小ロット拒否を守ることを検証。
- 報告書は新しいJSON1件のみ。運用中のPython/MT4、state、lock、journal、
  AI台帳、保存価格原本、EAコンパイル/起動プロセスは変更しない。

## 操作するWindows PowerShell

既に稼働中の監視を起動した元のworktreeを切り替えない。新worktreeを作る：

    cd C:\Users\Suzuki\Documents\ChatGPT\Fx-PAPER-CLOCK-REVIEW-20261120
    git fetch origin
    if ($LASTEXITCODE -ne 0) { throw 'Git fetch failed' }
    $tree=Join-Path $env:USERPROFILE 'Documents\ChatGPT\Fx-PAPER-FINAL-TEST-REVIEW-20261120'
    if (Test-Path -LiteralPath $tree) { throw 'Target worktree already exists' }
    git worktree add --detach $tree origin/feat/final-paper-operator-single-command-20261120
    if ($LASTEXITCODE -ne 0) { throw 'Git worktree failed' }
    Set-Location $tree
    .\scripts\final_paper_start_final_test_v1_once.ps1 -Mt4FilesDirectory $mt4Files

PowerShellを新しく開いた場合は、MT4 GUIの「ファイル→データフォルダを開く」で
実際の `MQL4\Files` を確認し、その絶対パスを `$mt4Files` に再設定する。
コマンドの `-OfficialArchiveDirectory` は、2026-11-20に保存した
`official_public_capture_20261120_113041_303` を既定で参照する。
別フォルダで保存したときだけ明示する。

## 結果の解釈

成功時の報告status：FINAL_TEST_V1_OBSERVATION_RUNNING_TRADING_HOLD_NO_GO。
これは新しいサービスの起動ではなく、既存の観測系が継続稼働している証拠。
新しい運用journalの仮想建玉0、AI paid calls6/6、通信ラッチ維持。
別メモリの合成APPROVEDは実AIシグナルではなく成績/エントリー実績に集計しない。
失敗時はFINAL_TEST_V1_EVIDENCE_INCOMPLETE_FAIL_CLOSED_NO_GO。
ロック削除、Python二重起動、EAの手動差替えは行わない。

## 残る完全版の必須条件

- 時計競合修正版EA V2はGitHub候補ソースのみ。現場MetaEditorでの
  無注文コンパイルと旧EA停止/新EA単独稼働は未実施。
- これまでの3,020原本、時刻逆転4件は修復・無視しない。
- 重要イベントのUSD/EUR/JPY網羅、発表前コンセンサスの時点証明、
  独立時計、滑り/スワップ含む取引コスト検証は未完了。
- 長時間通信停止のラッチは未解除。ユーザーによる特定の有人承認が必要。
- AI予算は6/6であり、新たな請求・モデル利用は未承認。
- 新規仮想建玉とデモ/本番口座注文はすべてNO_GO。
- mainマージは人間承認のみ。

本コマンドは「最終テスト版・価格観測と安全動作検証」の開始判定であり、
正式な「戦略AI全自動仮想売買テスト」の開始を宣言するものではない。