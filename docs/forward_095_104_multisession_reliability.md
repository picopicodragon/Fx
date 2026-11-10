# FWD-095〜104：楽天MT4デモ・複数観測セッションの連続性と安全保留を統合監査

## 今回の根拠と目的

既存の楽天MT4単一DEMO端末で、利用者がセッション001に8完全周期（24 CSV）、セッション002に30完全周期（90 CSV）を報告。FWD-084/094による単一セッションの整合検査は成功。ただし**30周期停止のExpertsログは未提出**であり、停止の実証と長期稼働の認定はしていない。

- **FWD-095：** セッションラベル付きの複数CSVフォルダーを、FWD-094の厳格な監査を再利用して一括検査する。
- **FWD-096：** 各セッションの完全3ペア周期数、欠損周期、ファイル数とSHA-256マニフェストを記録する。
- **FWD-097：** 期間順のセッション間の空白と観測窓の重複を検出する。**セッション間の空白を通信断だと決めつけない**。操作者が意図して停止していた可能性があるため、`is_expected_collection_gap=null`を維持する。
- **FWD-098：** 異なるセッション間で同じCSVバイト列が再利用された場合、SHA-256からリプレイを検出する。
- **FWD-099：** それぞれのセッションに任意のExperts・MetaEditorコンパイルログを紐づける。自己申告ログに過ぎず、MT4端末ID・時刻の第三者認証とはみなさない。
- **FWD-100：** 30周期超過・周期異常・欠損の検出と全セッションの安全保留を集約。CSVが揃っても自動停止を独立に確認したとは扱わない。
- **FWD-101〜104：** Linux/Windows向け全件テスト・異常系回帰・一行PowerShell・再現可能な証拠バンドル手順を追加。

## 既存2セッション114ファイルのWindows一括監査

PR #261を本人がマージした後：

```powershell
cd C:\Users\Suzuki\Documents\ChatGPT\Fx
git switch main
git pull --ff-only origin main
```

次の**一行**をそのまま実行する。

```powershell
$asof = [DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ"); python -m research.forward_mt4_multisession_reliability --session "s001=out/mt4_timer_session_001" --session "s002=out/mt4_timer_session_002" --asof-utc $asof --out "out/mt4_multisession_$(Get-Date -Format yyyyMMdd_HHmmss).json"
```

今回の報告どおりのファイルが存在する場合、期待される観測件数は`session_count=2`、`files=114`、`complete_cycles=38`、`incomplete_cycles=0`。**セッションの時間帯が重複している、フォルダーに別のCSVが混ざっている場合は期待結果にならない**。異常は原因を調べ、証拠を改変して取り繕わない。

30周期停止ログのコピーが実際に存在する場合は、そのセッションの専門家ログを別に追加して監査できる。

```powershell
$asof = [DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ"); python -m research.forward_mt4_multisession_reliability --session "s001=out/mt4_timer_session_001" --session "s002=out/mt4_timer_session_002" --experts "s002=out/mt4_timer_session_002_experts.txt" --asof-utc $asof --out "out/mt4_multisession_with_log_$(Get-Date -Format yyyyMMdd_HHmmss).json"
```

既存ログがなければ`--experts`は付けない。虚偽のログ作成はしない。コンパイルのテキスト証拠が実際に存在する場合に限り`--compile "s002=..." `で指定可能。

## 次の長期観測ゲート

観測セッションの再実行、無人監視、再起動自動化はこのPRでは実装・実行しない。各セッションは既存の60秒・最大30周期の読み取り専用EAと単一デモ端末だけを使う。新しいセッションはセッション別の空フォルダーにCSVを手動コピーし、前回分を混ぜない。予期せぬ口座状態変更、AutoTrading ON、既存EA競合、価格・通信断、ファイルエラーがあれば中止し、元ログを保管する。

**確認すべきこと：** 30周期停止ログ、3ペア全周期の欠損状況、通信停止時の挙動、MT4端末と口座が単一デモである証拠、MetaEditorの0 warnings、コンピューター/ブローカー時刻の整合、証拠の保全と複数セッション間の重複排除。これらを徐々に揃えるまで長期自動稼働の許可はない。

## 安全条件

`runtime_go_no_go=NO_GO`、`safety_hold_latched=true`、`real_orders_permitted=false`、`demo_orders_permitted=false`。リスク上限、イベント停止、G1〜G9、契約属性3×5=15、MT4単一デモ口座の制約は維持。PythonからMT4を制御しない。GitHub CI成功は実端末の運用認定ではない。

## PRチェック・補足

GitHub ActionsのRepository checksはPR本文に`関連仕様ID`、`変更概要`、`リスク影響`、`テスト結果`、`本人確認`の見出しがあることを要求する。本文を整えた後のCIでコードも検証する。最終的な実機認定はこのCIに含まれない。
