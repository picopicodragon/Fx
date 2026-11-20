# FINAL-PAPER-156: 2026-11-20 13:28 JST 複数日検査の失敗原因の特定

## 観測された状況

Windows PowerShellから実行したPR #297の
final_paper_multiday_macro_integrity_once.ps1 は第一検査で
MULTIDAY_QUOTE_STRESS_FAIL_CLOSED_NO_GOとなり停止した。
二番目の公式6原本SHA256検査は未実行。

すでに別コマンドによる240周期の3ペア価格品質検査は成功している。
一方、最大10080周期まで対象を広げたため、直近240より古いCSVに
不正な内容や形式/時刻不整合があった可能性はあるが、現時点では
**具体的な失敗理由・不正ファイルは未確定**である。

## 改修

- research/final_paper_multiday_quote_stress.py:
  - 元CSVの処理順番号、ファイルbasename、失敗フェーズ、
    完全に検証できた枚数、秘密を含まない事前定義理由コードを
    fail-closedのstdout JSONへ追加。
  - 外部ファイルの中身、MT4口座番号、ローカル絶対パス、
    生のbid/ask・APIキーなどは診断出力へ含めない。
  - 不正ファイルの削除・暗黙のスキップは行わず全セットNO_GO。
- scripts/final_paper_multiday_macro_integrity_once.ps1:
  - 第1の長期価格監査が失敗しても、**独立した**第2の公式6原本
    SHA256監査を実行する。
  - どちらか一つでも失敗なら最終終了はNO_GO。
  - 公式原本の成功を価格検査の成功と混同しない。
- tests/test_final_paper_multiday_failure_diagnostic.py:
  - 3枚中2枚目の改変、異常ファイル名、成功でもNO_GO、
    公式監査の独立実行、禁止API/ファイル操作を検証。

## Windows 実行

既存のPython監視や別のGit作業ツリーは触らない。
最新の修正PR #298を、新しいレビュー作業ツリーに取得する。

    cd C:\Users\Suzuki\Documents\ChatGPT\Fx-PAPER-MULTIDAY-REVIEW-20261120
    git fetch origin
    if ($LASTEXITCODE -ne 0) { throw 'fetch error' }
    $tree=Join-Path $env:USERPROFILE 'Documents\ChatGPT\Fx-PAPER-MULTIDAY-FIX-REVIEW-20261120'
    if (Test-Path -LiteralPath $tree) { throw 'Destination already exists' }
    git worktree add --detach $tree origin/fix/final-paper-multiday-failclosed-diagnostic-20261120
    if ($LASTEXITCODE -ne 0) { throw 'Worktree error' }
    Set-Location $tree
    $official=Join-Path $env:USERPROFILE 'Documents\FXForwardEvidence\final_virtual_paper\official_public_capture_20261120_113041_303'
    .\scripts\final_paper_multiday_macro_integrity_once.ps1 -Mt4FilesDirectory $mt4Files -OfficialArchiveDirectory $official

失敗時は表示される
diagnostic_reason_code / diagnostic_phase /
source_file_ordinal / source_file_basename /
original_complete_files_verified_before_failure
を確認する。上記には原本そのものの内容は含めない。
エラーの原因が古い原本の不正であっても、ファイルを削除して
強引に合格させない。直近240件だけの検査合格を複数日GOへ昇格しない。

対象全体の証拠が十分でも、通信ラッチ、独立時計、重要イベントの
完全網羅、事前コンセンサス、取引コスト、AI追加料金6/6などの
条件は未達であり、新規仮想売買・MT4発注・追加有料AIは許可しない。
