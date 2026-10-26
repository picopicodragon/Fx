# MetaEditor MQL4コンパイルだけを確認する手順（2026-10-26）

**承認の記録：** 2026-10-26に本人から「MetaEditorでのコンパイル確認を承認する」との明示承認あり。この承認で許されるのは**MetaEditorでのMQ4コンパイル、エラー・警告の確認**まで。MT4のチャートでスクリプトを起動する、データを取りに行く、本人ローカル口座の情報をGitHubへ送る、FXの売買を行うことは未承認。

## 1. 何を検証できるか

コンパイルできることはMQL4言語の構文とそのコンパイラへの適合についての手掛かりだが、`MarketInfo`の返す値の真正性や、円換算、注文失敗時処理を保証しない。GitHub CIのPythonテストもMQL4コンパイルではない。コンパイルが成功しても本番運用許可ではない。

コンパイル対象はGitHubメインにマージ済みの`mt4/read_only/P0_01_ManualSymbolSnapshot_ReadOnly.mq4`**1ファイルだけ**。初期設定の`InpExplicitReadApproval=false`は変更しない。対象銘柄は4ペア、取得対象は`MODE_MINLOT`、`MODE_LOTSTEP`、`MODE_POINT`、`MODE_TICKSIZE`、`MODE_TICKVALUE`。

**重要：** スクリプト本体は`OnStart`を持つため、コンパイルで作られる`.ex4`は実行可能なファイルである。**絶対にMT4のナビゲーターから起動したり、チャートへドラッグしたりしない。** 読取実行の承認は別途必要。

## 2. Windowsでの安全な隔離とコンパイル

1. PRを本人が確認・手動マージし、Fxのルートフォルダーで`git pull --ff-only origin main`を実施。未コミットの変更があれば先に別途確認して中断する。
2. MQL4ソースの静的監査と、コンパイル専用フォルダーへのコピーだけを行う。コピー元のGit管理ファイルは一切変更しない。

```powershell
python scripts/audit_mt4_readonly_source.py
python -m unittest discover -s tests -p "test*.py"

$compileDir = Join-Path $env:USERPROFILE "Documents\FxLocalReview\CompileOnly"
python -m scripts.stage_mt4_compile_only --output-dir $compileDir

$sourceToCompile = Join-Path $compileDir "P0_01_ManualSymbolSnapshot_ReadOnly.mq4"
Test-Path $sourceToCompile
```

`stage_mt4_compile_only`は、**Gitリポジトリの中・MT4のMQL4実行フォルダー・MetaQuotes端末データフォルダーを出力先に指定したら拒否**する。出力が存在すれば上書きせず失敗。MetaEditorやMT4は起動しない。

3. Windows上で**MetaEditorを開く**。可能ならMT4本体のチャートを操作せず、インストール済みのMetaEditor単独起動を使う。MetaEditorの「ファイル → 開く」で上記`$sourceToCompile`に相当する**隔離コピー**を選ぶ。リポジトリ側の原本を開かない。
4. MetaEditorで表示されるソースが`P0_01_ManualSymbolSnapshot_ReadOnly.mq4`か、`InpExplicitReadApproval = false`のままかを確認し、**F7（コンパイル）のみ**を1回押す。F5（デバッグ）、実行、ナビゲータのダブルクリック、チャートへのドラッグ、Experts/Script配下へのファイル移動は禁止。
5. 下部の「ツールボックス → エラー」欄に表示される**errors/warningsの件数と診断内容（行番号、エラー本文）**を確認する。成功しても警告は精査する。MetaQuotes公式によれば`.ex4`はメインのMQ4ソースと同じフォルダーに生成されるので、`CompileOnly`内に留める。

コンパイル後、FxルートのPowerShellでは次の**存在確認だけ**ができる。

```powershell
$compiled = Join-Path $compileDir "P0_01_ManualSymbolSnapshot_ReadOnly.ex4"
Test-Path $compiled
```

`True`はEX4の存在を意味するだけで、最新コンパイルの成否や警告0を保証しない。**MetaEditorのエラー/警告件数を最優先**する。古い`.ex4`の有無を誤認しないよう、専用フォルダーには既存の成果物がないことも事前確認する。

## 3. コンパイル結果の記録

本人が次の**結果だけ**をチャットへ共有し、発注や取得値・アカウント情報は共有しない。
- MetaEditorで対象ファイルを開けたか
- errors: 0 / N、warnings: 0 / N
- エラーまたは警告があれば、**MQL4ソースの行番号と診断文のみ**（口座番号・シンボルの実値・端末ログ全文は不要）
- コンパイル専用フォルダーにEX4が作られたか（`True`/`False`）

**GitHubへ`.ex4`、`mq4`に追記した個人情報、端末ログやスクリーンショットをコミットしない。** リポジトリの`.gitignore`へ`*.ex4`を追加し、誤ってバイナリが混入する可能性を下げる。

## 4. 今回の対象外

- MT4実端末へ実行配置、Scripts/Expertsフォルダーでの起動
- 売買（注文送信・変更・決済）、EA稼働・Python/EA通信
- ユーザーの`mt4_symbols_local.v2.json`へのAPI値の自動追記
- MQL4からのライブ口座/気配値・証拠金情報の実取得
- FORM-01/03の真正性・計算式承認、PHASE-1解除

**安全状態：** `implementation_approved=false`、`human_safety_approval=false`、`owner_approved_for_safety=false`、`forward_trading_enabled=false`、PHASE-1 BLOCKED。

## 公式参考

- [MetaQuotes MetaEditorのコンパイル（F7、EX4出力先）](https://www.metatrader5.com/ja/metaeditor/help/development/compile)
- [MetaQuotes MetaEditorのファイルメニュー](https://www.metatrader5.com/en/metaeditor/help/main_menu/main_menu_file)
- [MQL4コンパイルエラー](https://docs.mql4.com/constants/errorswarnings/errorscompile)
- [MQL4 OnStartのスクリプト実行定義](https://docs.mql4.com/basis/function/events)
