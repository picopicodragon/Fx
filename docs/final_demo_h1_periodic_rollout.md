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


## 2026-11-17 実API初回失敗：台帳を先に診断する

利用者実機では3ペアの実H1/保存済みニュースの非課金前処理に成功。続くgpt-6.1-sol/gpt-6-astraの明示課金実行はUSD/JPYで PERIDOIC_AI_FAIL_CLOSED_CHECK_LEDGER_NO_GO（綴りは実装のPERIODIC）となり、後続ペアは未実施。注文0件。現行コマンドは詳細な安全分類をログに出さないため、台帳とAPI呼び出しの有無をまだ確定できない。

同じスクリプトを「リトライ」しない。既存AI台帳は下記のローカル読み取りだけで調べる。

    $dir = Join-Path $env:USERPROFILE 'Documents\FXForwardEvidence\final_demo_periodic'
    $items = @(Get-ChildItem -LiteralPath $dir -File -Filter 'ai_USDJPY_*.json' |
      Sort-Object LastWriteTime -Descending | Select-Object -First 3)
    if ($items.Count -eq 0) { 'NO_USDJPY_AI_LEDGER' }
    foreach ($f in $items) {
      $s = Get-Content -LiteralPath $f.FullName -Raw | ConvertFrom-Json
      [pscustomobject]@{
        File=$f.Name
        Stage=$s.stage
        PendingRole=$s.pending_role
        AnalystRecorded=($null -ne $s.analyst)
        ReviewerRecorded=($null -ne $s.reviewer)
      }
    }

この4属性以外の台帳の元データ・本文・APIキーはチャットへ共有しないこと。台帳が存在せず捕捉から10分超の場合、最新のH1読み取り専用スクリプトから再取得して前処理を行う。台帳にpending_roleが残る場合は課金発生の可能性があるため、API usageと原因を人間が照合するまで次の有料呼出しは禁止。既存台帳は消さず、手動でpendingを解除しない。

DEMO-SPRINT-36以降は失敗時にAPIの秘匿済み分類（モデル不存在・アクセス不可・400・401・429・レスポンス不完全等）と現行台帳stage/pendingの有無を表示するよう変更。DEMO-SPRINT-38は以前のAI台帳に保留があれば、新タイムスタンプ名を用いた課金リトライを禁止する。過去の失敗の細分類は後から勝手に再構成できない。

MetaEditorの既存コンパイル・MT4 AutoTrading OFF・EnableDemoOrders=falseは変更しない。実口座注文禁止を維持。


## 2026-11-17: 無料検証が2度目にNO_GOになった場合

3ペアの実レート＋公式RSS研究が一度成功したのち、現地再実行で
PERIODIC_AI_RESEARCH_FAIL_CLOSED_NO_GOが発生。料金・注文は0。
これは必ずしも10分超過を意味しない。3ファイルの不一致、古い
$dst、保存バンドルの変化等の可能性があるため、原因を決めつけない。

DEMO-SPRINT-40〜44によりPython無料CLIはfailure_reason_codeを含める。
H1_CAPTURE_STALE_OR_CLOCK_SKEWなら本当に10分超過または時計差異。
H1_EXPECTED_EXACTLY_THREE_CSVSならコピー先が空/不足。
H1_CAPTURE_SET_NOT_ATOMICなら3ペア異なる取得回を混合。
NEWS_BUNDLE_INTEGRITY_FAILEDなら原本が変わっている可能性。
いずれもAPIの追加呼出しは不要。

H1取得後の複数手順を削減した。最新のMT4読み取り専用
FxFinalTestH1Exportスクリプトを一度実行したのち、PowerShellで
次の単一コマンドを実行できる。$mt4FilesはMT4データフォルダー内
MQL4\Filesの実パス、$bundlesは直前の公式ニュース原本の配列。

    .\scripts\final_demo_periodic_fresh_once.ps1 -Mt4FilesDirectory $mt4Files -NewsBundle $bundles

このコマンドはMT4の最新3ペアセットを探して一致をチェックし、
PC推定現在時刻から480秒以内のみ自動コピーし、API課金0・注文0で
3ペアのテクニカルとニュース研究を一括実行する。8分超なら
新しいH1スクリプトを1回実行してから再度実行する。
不正・欠損・期限切れなら理由を示して停止する。

この無料診断が全3ペアで成功するまで、有料モデル分析コマンドを
もう一度実行しない。古いpending台帳があれば別途照合する。
実口座禁止、AutoTrading OFF、EnableDemoOrders=falseを維持。


## 2026-11-17 HTTP401 analyst pending manual review (DEMO-SPRINT-46–49)

An actual OpenAI API call failed with HTTP_401_INVALID_API_KEY before any
model response was accepted. The original analyst ledger remains
stage=ANALYST_PENDING, pending_role=analyst. DO NOT edit or delete it.
DO NOT simply create a new timestamp and repeat a paid AI call.

1. Visit https://platform.openai.com/api-keys and ensure a valid project-scoped
   API key. The paid API platform is distinct from ChatGPT subscriptions.
2. Replace the process-local OPENAI_API_KEY safely. Do not print or commit it.
3. Only if the operator personally observed HTTP_401_INVALID_API_KEY from the
   failed analyst call, select the EXACT original pending USDJPY ledger:
   
    $folder = Join-Path $env:USERPROFILE 'Documents\FXForwardEvidence\final_demo_periodic'
    $pending = @(Get-ChildItem -LiteralPath $folder -File -Filter 'ai_USDJPY_*.json' |
      Sort-Object LastWriteTimeUtc -Descending)
    if ($pending.Count -ne 1) { throw 'Select exactly one verified HTTP401 pending ledger' }
    python -m research.final_demo_http401_recovery --review-ledger $pending[0].FullName --operator-confirmed-http401

This does ONE nonbillable read-only GET to https://api.openai.com/v1/models,
and checks the two designated model IDs are listed for that API project.
Only after successful authentication and model listing does it write a separate
SHA256-bound operator review marker named auth401_review_ai_*.json. The original
ledger is preserved verbatim; no artificial model result is created.
No Responses API calls, inference, broker operations or orders occur.

Run a strictly local review check:

    python -m research.final_demo_http401_recovery --check-directory $folder

This only permits the operator to separately opt in to a NEW AI research cycle
later with fresh validated H1 evidence. It never automatically reruns paid calls.
A pending reviewer, network timeout, unknown outcome, HTTP429/5xx or a changed
ledger cannot be reconciled using the HTTP401 analyst path. Do not share API
keys or full ledgers in chat. Keep demo orders OFF and real orders forbidden.


## 2026-11-18: 449 sec FREE vs 420 sec paid-precheck mismatch fixed

Observed on Windows: MT4 H1 source age 449 seconds, FREE H1/news validation of
all three pairs passed, then the operator's paid AI 420-second freshness
check stopped before any paid inference; no orders. This is a mismatched
preflight timing policy, not an AI decision failure.

DEMO-SPRINT-51 unifies the fresh helper's FREE cutoff at 420 seconds and
allows explicitly opted-in, bounded research directly after FREE preflight
within the same PowerShell command. Default remains free-only. The second
gate rechecks age before any paid dispatch. No auto retry or trading.

After executing the read-only FxFinalTestH1Export on the Rakuten DEMO
USDJPY H1 chart, immediately run from the Fx worktree (single command):

    .\scripts\final_demo_periodic_fresh_once.ps1 -Mt4FilesDirectory $mt4Files -NewsBundle $bundles -AllowPaidAi -Pair @("EUR/JPY","EUR/USD") -AnalystModel "gpt-6.1-sol" -ReviewerModel "gpt-6-astra"

This explicitly permits at most four API inference calls across the
remaining EUR/JPY and EUR/USD pairs (two per pair); still research-only,
with no MT4 order and no trading authorization. A preexisting unreconciled
paid ledger or stale H1 fails closed. Do not rerun after a billable API
dispatch failure without manual ledger reconciliation.


## DEMO-SPRINT-54 to 57: all three completed AI decisions auditable offline

Windows Rakuten DEMO confirmed a successful 3-pair CLOSED H1 + official-news
research pass, plus two distinct model calls on each pair. The separate
reports show USD/JPY, EUR/JPY and EUR/USD each returning APPROVED/HOLD.
USD/JPY used an earlier capture, so this is NOT a contemporaneous
three-pair snapshot and is NOT a trade approval.

After pulling this branch, run from the worktree:

    .\scripts\final_demo_three_pair_audit_once.ps1

This performs NO network requests, AI calls or orders. It verifies all
existing paid ledgers, including a hash-bound, operator-reviewed historical
HTTP401 pending ledger; then selects the newest completed model ledger
for each pair and emits a new local read-only evidence JSON report under
Documents/FXForwardEvidence/three_pair_ai_audit_*.json.

The report includes three verdict/action pairs, local packet and ledger hashes,
the actual model identities and the separate historical HTTP401-reviewed count.
It explicitly records cross_pair_same_snapshot=NOT_ATTESTED,
point_in_time_news_consensus=NOT_ATTESTED,
broker_server_clock=NOT_ATTESTED,
market_execution_verified=false,
demo_orders_permitted=false and real_orders_permitted=false.
An incomplete newer ledger, changed old rejection marker, absent pair or
unreconciled billable request fails closed.

Next required milestone is a genuinely independent DEMO operational test:
verify EA version and compilation, actual Rakuten DEMO identity/account clock,
market order lifecycle and 0.5%/1%/1.5%/5% risk gates, NY17 rollover, daily
blackout and persistent evidence. A research HOLD/APPROVED is not permission to
create an executable signal or turn on AutoTrading. The local audit alone
cannot demonstrate final-demo trading readiness.


## DEMO-SPRINT-59–64: broker DEMO account/risk terms observation

Three pairs have passed real two-model AI research and an offline ledger
audit, but all decisions were HOLD and none proves execution readiness.

A distinct read-only MT4 **Script** has been added:

    mt4/read_only/FxFinalDemoBrokerSafetyProbe.mq4

Install the MQ4 in the *same existing Rakuten DEMO MT4* data folder at
MQL4/Scripts, then compile in MetaEditor F7 (0 errors/0 warnings required).
Run ONCE from Scripts on the **USDJPY H1** chart with AutoTrading OFF.
It independently checks IsDemo, connection, JPY deposit currency, USDJPY H1
chart, basic account equity and quote/contract values. It writes
FxDemoBrokerSafety_YYYYMMDD_HHMMSS.csv with three rows under MQL4/Files.
No trade, DLL, network, timer or trading permissions are enabled.

The broker snapshot contains sensitive DEMO account number and equity.
**Do not paste or share that original CSV**. It is for operator-local
evidence only. Server time and TimeGMT remain independently UNATTESTED;
broker tick-value figures are broker-reported, not externally verified.

Then, without uploading sensitive raw data, run from the Fx Windows worktree:

    .\scripts\final_demo_broker_safety_once.ps1 -Mt4FilesDirectory $mt4Files

The script copies the newest broker terms file into a local protected
evidence folder and invokes the offline Python auditor. Its **redacted**
report contains broker-reported 3-pair bid/ask, lot steps, min/max lot,
tick-value/tick-size, price step, stop/freeze levels, quote lag and equity.
It rejects >10-minute-old PC clocks, >30-second broker quote lag,
open/pending account orders, invalid contracts or incomplete/cross-account
snapshots. Equity risk references are 0.5% per trade, 1.0% simultaneous,
1.5% daily and 5% maximum DD; none is permission to place an order.

The only success status is
DEMO_BROKER_TERMS_OBSERVED_RESEARCH_HOLD_NO_GO,
with demo_orders_permitted=false and real_orders_permitted=false.
There has been no MetaEditor compilation or physical broker test of the new
script yet. The Python CI cannot substitute for either. Continue to prohibit
real accounts and keep all demo auto-trading switches OFF.
