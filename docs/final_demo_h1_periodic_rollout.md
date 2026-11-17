# DEMO-SPRINT-22〜35：イベント待ちを解消するH1×公式ニュース研究

重要マクロイベントが発表されない日でも、MT4デモ口座の3ペア×確定済みH1足120本、保存済みの公式ニュースを用いて定期AI研究の入力を作成する。明示した有料APIオプトインがあれば構築AIと独立検証AIを最大2コール/ペア実行する。これは研究でありデモ注文に自動昇格しない。

## Windowsで最新版取得

    cd C:\Users\Suzuki\Documents\ChatGPT\Fx-MACRO-FWD-20261113
    if (@(git status --porcelain).Count -gt 0) { throw "変更あり、停止" }
    git fetch origin
    if ($LASTEXITCODE -ne 0) { throw "fetch失敗" }
    git switch --detach origin/feat/mt4-demo-final-e2e-20261117
    if ($LASTEXITCODE -ne 0) { throw "切替失敗" }
    python -m unittest discover -s tests -p "test_final_demo*.py"

## MT4側の一度だけの読み取り専用作業

1. 既存のRakutenデモMT4一台のUSDJPYチャート、DEMO口座、接続、注文の有無を確認。AutoTrading OFFを維持。既存のデモ執行EAを同じチャートから外す。
2. 新しい読み取り専用の「スクリプト」mt4/read_only/FxFinalTestH1Export.mq4 をMT4の MQL4/Scripts フォルダーへ手動コピー。同名ファイルがあれば保存してから更新。MetaEditor F7で0 errors、0 warningsを確認。確認前は実行しない。
3. USDJPYチャート1枚でスクリプトを1回だけ実行。Expertsログで FXDEMO_H1: 3 pairs x 120 CLOSED H1 bars saved を確認し、MQL4/Filesの同一時刻サフィックスの3CSVだけを端末外フォルダーへコピー。CSVが3つ揃わなければ中止。

PowerShellコピー用：

    $root = "$env:USERPROFILE\Documents\FXForwardEvidence"
    $mt4Files = Read-Host 'MT4のMQL4\Filesの実パス'
    if (-not (Test-Path -LiteralPath $mt4Files -PathType Container)) { throw 'Filesなし' }
    $latest = Get-ChildItem -LiteralPath $mt4Files -File -Filter 'FxDemoH1_USDJPY_*.csv' |
      Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($null -eq $latest) { throw 'USDJPY CSVなし' }
    $suffix = $latest.BaseName.Substring('FxDemoH1_USDJPY_'.Length)
    $dst = Join-Path $root ("h1_copy_" + (Get-Date -Format 'yyyyMMdd_HHmmss_fff'))
    New-Item -ItemType Directory -Path $dst -ErrorAction Stop | Out-Null
    foreach ($symbol in @('USDJPY','EURJPY','EURUSD')) {
      $name = 'FxDemoH1_' + $symbol + '_' + $suffix + '.csv'
      $src = Join-Path $mt4Files $name
      if (-not (Test-Path -LiteralPath $src -PathType Leaf)) { throw "欠損: $name" }
      Copy-Item -LiteralPath $src -Destination (Join-Path $dst $name) -ErrorAction Stop
    }
    Write-Host "コピー先: $dst"

## 既存公式ニュース原本と3ペア分析（無料・注文0）

各ニュース保存先のmanifest.jsonが存在するfeedフォルダーのみを渡す。

    $bundles = @(
      (Join-Path $root 'demo_feed_20261117_151818_005\fed_policy'),
      (Join-Path $root 'demo_feed_20261117_151818_005\bls_cpi'),
      (Join-Path $root 'demo_feed_20261117_151818_005\bls_empsit'),
      (Join-Path $root 'ecb_local_verified_20261117_142653_689\ecb_press')
    ) | Where-Object { Test-Path -LiteralPath $_ -PathType Container }
    .\scripts\final_demo_periodic_once.ps1 -H1CopiedDirectory $dst -NewsBundle $bundles

別に保存済みのboj_whatsnew原本があれば、そのバンドルも含める。無い場合、JPYを対象とするUSD/JPYとEUR/JPYのニュース地域カバレッジは不足と明記される。欠損を埋めたと仮定してAIへ発注させない。

AI推論を実行したい場合は別途 -AllowPaidAi、二つの現実に利用可能な異なるモデルID、OPENAI_API_KEYを明示する。API利用は有料になりうる。研究結果はどんなAPPROVEDでも発注指示ではない。デモ注文EAのEnableDemoOrders=falseとAutoTrading OFFは保持する。

## 残りの正式テスト
新しいMQL4の実コンパイル/端末実測、口座・PC時計の独立照合、楽天MT4のlot/tick/SL契約、デモ実約定・成績検証、NY17日次更新、通信断・再起動、異常停止・決済、通知、連続無人実行。今回のPython CIはそれらを認定しない。mainマージは利用者本人の承認のみ。
