# FWD-1461〜1475：公式ニュース原本取得と実マクロジャーナル記録のワンコマンド

## 実装目的

ユーザーの既存の非発注シャドー研究（2セッション、90CSV、完全30周期）と `macro_forward_journal`（初期化済み、MACRO_EVENT 0件）の間に、**明示的な1回限りの公式ニュース原本収集**を追加する。

起動時は**ネットワーク不可が既定**。実取得を行う際には `--allow-network` を明示し、公式URL固定、同一ホスト・タイムスタンプ・フィード構造・最大件数・XMLサイズを既存ライブラリで検査する。1回で指定した各フィードを最大1回だけ取りに行き、リダイレクト・自動リトライ・ポーリングは行わない。取得不能なフィードは他の成功を虚偽の全体成功とせず、個別のHOLDとする。

- US: BLS CPI / 雇用統計 / FRB金融政策の既存 `forward_rss` を再利用。**公表後24時間以内**の未登録ニュースを、出典URL・公表時刻・受信時刻付き、数値予想・実値空欄の `MACRO_EVENT` として既存のハッシュチェーン付きジャーナルに追記する。
- EUR/JPY: ECB/日銀の公式RSSの生XMLと証拠マニフェストのみを保存する。ニュースは経済指標の実値、事前予想、完全な経済カレンダーではないため、`MACRO_EVENT` には**自動昇格させない**。
- 1フィードごとに新規サブフォルダーへ `feed.xml` と `manifest.json` を保存する。元データは上書きしない。最上位に `capture_report.json` を最後に作り、部分成功と完全失敗を区別する。
- 分析AI・独立検証AI・ブローカー・MT4注文・実時間の無人スケジューラーは**一切実行しない**。

## 現行のWindows作業環境から実行

マクロジャーナルは `fxmacro20261113` として初期化済み。再度 `--init` しない。

新しいバージョンのワークツリーから下記を実行する。キャプチャ出力は毎回新しいフォルダーで、過去のXMLと記録を上書きしない。

~~~powershell
$root = "$env:USERPROFILE\Documents\FXForwardEvidence"
$store = Join-Path $root "macro_forward_journal"
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$out = Join-Path $root "macro_official_feeds_$stamp"
python -m research.forward_macro_feed_once `
    --store $store `
    --out-dir $out `
    --allow-network `
    --feed fed_policy `
    --feed bls_cpi `
    --feed bls_empsit `
    --feed ecb_press `
    --feed boj_whatsnew
~~~

公式サイトへのアクセス制限、フィード構造変更、タイムスタンプ欠損がある場合は、そのフィードだけ `SOURCE_UNAVAILABLE_OR_INVALID_HOLD_NO_GO` と表示される。部分成功は `OFFICIAL_FEEDS_PARTIAL_HOLD_NO_GO`。全失敗は `OFFICIAL_FEEDS_ALL_FAILED_HOLD_NO_GO`。

**重大な区別：** `new_recent_us_journal_records=0` は正常に起こり得る。新しい米国発表が24時間以内に存在しない／取得できない場合、ローカルジャーナルは0件のままでも、取得した原本と失敗理由を監査記録に残せる。ECB/日銀のニュースはこのコマンドではマクロイベント数を増やさない。

完了後のローカル監査：

~~~powershell
python -m research.forward_observation --store $store --audit
~~~

この結果のイベントハッシュは `journal.record_sha256` であり、公的時刻に対する第三者認証ではない。

## FWD-1476〜1478：部分失敗時の安全な原因切り分け（2026-11-17）

ECBと日銀が `SOURCE_UNAVAILABLE_OR_INVALID_HOLD_NO_GO` を返した場合でも、URLが無効だと断定しない。両URLは中央銀行公式RSS案内ページと一致している。更新後の `capture_report.json` の失敗フィードにだけ、追加の `failure_stage` と `failure_reason_code` を含める。

- `DOWNLOAD`: 通信・HTTP・リダイレクトなど取得段階の問題。`HTTP_STATUS_403` などの数値はHTTPエラーのときだけ表示。例外本文・サーバー応答本文・アクセス認証情報は一切出さない。
- `FORMAT_VALIDATION`: 取得応答のRSS/Atom XML構造、件数、同一ホストのリンク、発行時刻、サイズ等の既存制限に不適合。
- `ARCHIVE_WRITE`: 保存先のファイルI/Oエラー。既存原本には追記も上書きもしない。
- `JOURNAL_APPEND`: 米国ニュースの新規レコード取り込み失敗。既存ジャーナルは監査対象のまま維持。
- `LOCAL_XML_READ`: 明示した保存済みXMLの読み出し失敗。

`failure_reason_code` は `HTTP_STATUS_<number>`、`NETWORK_REQUEST_FAILURE`、`XML_PARSE_FAILURE`、`INPUT_OR_FORMAT_REJECTED`、`LOCAL_IO_OR_ENCODING_FAILURE`、`VALIDATION_FAILURE` のいずれか。すべて研究・NO_GOであり、失敗理由が分かっても取引許可は発生しない。

2026-11-17 11:56 JSTの初回3/5取得分にはこれらの診断フィールドは存在しない。既存の保存ディレクトリを上書きせず、更新版で新たなディレクトリに対し、必要な `--feed ecb_press --feed boj_whatsnew` の**1回限りの明示実行**が必要。自動再実行やバックグラウンド処理は追加しない。

公式RSSニュースを取得できても、経済統計の発表前予想・事後実値の充足を意味せず、実イベントまたはレビュー記録が増えていなければ `forward_shadow_start --mode refresh` は起動しない。

## FWD-1479〜1482：現地ECB/BOJ失敗に対応する第2段階の非発注診断

2026-11-17 13:24 JSTの実機診断で、ECBは `DOWNLOAD / NETWORK_REQUEST_FAILURE`、日銀は `FORMAT_VALIDATION / INPUT_OR_FORMAT_REJECTED` と確認。今回初めて「通信とRSS形式が異なる原因で失敗」と特定できた。**日銀のRSSがHTTP記事リンクやRSS1 RDFを実際に配信しているかはまだ原本未取得のため確定していない。**

- ECBのネットワーク診断は `DNS_RESOLUTION_FAILURE`、`NETWORK_TIMEOUT`、`NETWORK_CONNECTION_RESET`、`TLS_FAILURE`、`TLS_CERTIFICATE_VERIFICATION_FAILURE` を安全な固定コードとして区分。分類不能な取得失敗は従来どおり `NETWORK_REQUEST_FAILURE`。
- BOJは `OFFICIAL_ITEM_HTTP_ONLY`（公式同一ホストだが記事がHTTPリンク）、`RSS1_RDF_ROOT_UNSUPPORTED`、`RSS_ROOT_UNSUPPORTED`、`ITEM_LINK_UNAPPROVED`、`PUBLISHER_DATE_UNSUPPORTED` 等を厳格に区分。**HTTPの記事リンクを自動でHTTPSに書き換えない。未知形式を勝手に受理しない。**
- 元XML・サーバーエラー内容・内部ネットワーク情報・認証情報・例外本文は失敗レポートに出さない。従来の3米国公式フィードや発表後24時間制限、原本の上書き防止は不変。
- 既存の両公式サイトのURLを勝手に書き換えない。成功数が0の場合は終了コード2が正しい。調査のために自動再試行、継続ポーリング、AI有償API、MT4、発注を起動しない。
- 本修正は失敗理由の分類機能であり、**根本的に通信不能を修復する機能ではない**。取得先ネットワークでの現地実行結果を確認してから形式対応を決める。

更新版を明示的に取り込む場合のみ、下記の2フィードで新規保存先へ一度だけ実行する。

~~~powershell
$root = "$env:USERPROFILE\Documents\FXForwardEvidence"
$store = Join-Path $root "macro_forward_journal"
$out = Join-Path $root ("macro_feed_diagnostic_" + (Get-Date -Format "yyyyMMdd_HHmmss_fff"))
python -m research.forward_macro_feed_once --store $store --out-dir $out --allow-network --feed ecb_press --feed boj_whatsnew
python -m research.forward_observation --store $store --audit
~~~

## FWD-1485：11月17日実機の到達点とECB TLSの安全な切り分け

11月17日13:51 JSTの明示的取得で、日銀 `boj_whatsnew` は **45記事**を形式検証してXML原本・マニフェスト保存に成功。過去の米国BLS/FRB 3系列39記事と合わせ、**4/5の公式系列で原本保存を実証**。同じ実行のECB `ecb_press` は `DOWNLOAD/TLS_CERTIFICATE_VERIFICATION_FAILURE` で停止。これは「Python側が証明書チェーンを検証できない」ことを示すが、ECBの証明書そのものの障害か、Windowsの証明書ストア・中間プロキシ・ローカルTLS設定かを識別しない。ローカルジャーナルは `record_count=0`、発注0、研究NO_GOのまま。

**対応方針:** 通信のためにTLS証明書検証を無効化する処理、`verify=False`、`ssl._create_unverified_context`、環境全体の検証無効化は一切使わない。既存のPython `urllib` 経路は引き続き検証必須。以下の診断も端末上の証明書検証を有効のまま行い、公式URLのHTTPSのまま、最大1回のみ明示してアクセスする。端末内で保存する原文は公開の公式ニュースに限定し、秘密情報を付加しない。

Windows PowerShell 5.1では、**OS既定の証明書検証**を用いた別経路を一度だけ明示試験できる。この方法で成功した原本は、既存の **完全オフライン** `--feed-file` 入力に渡し、同じ厳格なRSS検証・SHA保存処理を適用する（なお発表前コンセンサスは増えない）。Python側のTLS検証を迂回してPythonのネットワーク接続を行う機能ではない。

~~~powershell
cd C:\Users\Suzuki\Documents\ChatGPT\Fx-MACRO-FWD-20261113
$root = "$env:USERPROFILE\Documents\FXForwardEvidence"
$store = Join-Path $root "macro_forward_journal"
$stamp = Get-Date -Format "yyyyMMdd_HHmmss_fff"
$xml = Join-Path $root "ecb_verified_os_tls_$stamp.xml"
$out = Join-Path $root "ecb_local_copy_$stamp"

# 明示的な一度だけのHTTPS取得。OS証明書検証ON、HTTPリダイレクト禁止。
$fetchOK = $false
try {
    Invoke-WebRequest -Uri "https://www.ecb.europa.eu/rss/press.html" `
        -OutFile $xml -UseBasicParsing -MaximumRedirection 0 `
        -TimeoutSec 15 -ErrorAction Stop
    $fetchOK = $true
    Write-Host "ECB_OS_TLS_FETCH_SUCCESS"
} catch {
    Write-Host "ECB_OS_TLS_FETCH_FAILED_NO_GO"
    # 例外や接続先の詳細を共有しない。
}

if ($fetchOK -and (Test-Path -LiteralPath $xml -PathType Leaf)) {
    # 原XMLはwrite-onceの別フォルダーへ。既存のオフライン検証を再利用。
    python -m research.forward_macro_feed_once `
        --store $store --out-dir $out `
        --feed ecb_press --feed-file "ecb_press=$xml"
} else {
    Write-Host "ECB_OFFLINE_IMPORT_SKIPPED_NO_GO"
}

python -m research.forward_observation --store $store --audit
~~~

注意: Windows側のOS証明書検証が失敗した場合はオフライン取り込みをスキップする。成功ログと元XMLの存在を確認した場合に限り、Pythonに保存原本を渡す。オフライン検証に失敗しても `--allow-network` を追加したりリダイレクトを許したりしない。OS既定検証で失敗した場合は公式サイト閲覧・プロキシ・証明書チェーンの管理者確認を優先する。

## オフライン再現検査

ネットワークを使わないテスト入力を、実在するXMLコピーを明示して実行可能。新しい保存先・オリジナル実データのみ使用し、サンプルの合成RSSを実研究ジャーナルに入れない。

~~~powershell
python -m research.forward_macro_feed_once `
    --store $store `
    --out-dir (Join-Path $root "macro_official_offline_$stamp") `
    --feed fed_policy `
    --feed-file "fed_policy=C:\ここを実際のXML保存場所に変更\fed_policy.xml"
~~~

## 発表前予想とAIフォワード判断への接続

公式ニュース原本が保存されても、RSSの「発表日時」は発表前予想の時刻付き証明ではない。今後の指標について**発表前に**予想出典の原本を収集し、ハッシュと実際の取得時刻を保存する。発表後に実値を別原本から取得し、既存 `forward_macro_pre_release_capture` / `forward_macro_evidence_handoff` で関連づける。

根拠が成立しているイベントSHAにだけ、既存 `forward_macro_two_model_gate` のドライランを行う。 `--max-api-calls 2 --allow-external-api` は**別操作で明示する有償API**であり本コマンドでは行わない。有償APIの `pending_request` を自動で再試行しない。完全なAI結果の `--publish-offline` によりジャーナルへ記録後、前PRの `forward_shadow_start --mode refresh --plan-file` で、価格CSV再取得なしに既存キャンペーンに反映する。

完全な価格・実マクロ・事前予想・AIの自動連続稼働は**まだ未完成**。本工程は公式実データの安全な収集を前進させるためのもので、架空のフォワード成績や発注権限を作らない。

## 安全

すべての処理は `NO_GO`、`safety_hold_latched=true`、`demo_orders_permitted=false`、`real_orders_permitted=false`。通信失敗時の自動発注経路も存在しない。手元のローカル原本・ログ・時刻を第三者認証したものではない。


## FWD-1487〜1489：保存済みECB原本だけを使用する記事リンクの原因分析

2026年11月17日のWindows実行で、OS既定の証明書検証を経たECB RSS XMLは保存できた。ただし既存Pythonオフライン取り込みは `FORMAT_VALIDATION / ITEM_LINK_UNAPPROVED` で拒否。これは **ECB RSS内の少なくとも1記事のURLが、現時点の固定ホスト・HTTPSなどの規則に合致しなかった** ことを示す。実際のホスト名は未確認。追加の通信は不要。

新コマンド `research.forward_ecb_link_diagnostic` は既存XMLファイルのみ読み、元XML SHA256、記事件数、リンクの `scheme`・`hostname_unverified`・`validation_reason` ごとの件数を表示する。任意の第三者ホスト名は伏せ、`*.europa.eu` を含む文字列も公式認証済みとみなさない。URLフルパス・認証情報・クエリ文字列は出力しない。XMLやジャーナルへの書込み、ネットワークアクセス、AI API、発注は0。

~~~powershell
cd C:\Users\Suzuki\Documents\ChatGPT\Fx-MACRO-FWD-20261113
# 前操作の $xml を継続使用。必ず元XMLの実在を確認。
if (-not (Test-Path -LiteralPath $xml -PathType Leaf)) {
    throw "ECB原本XMLが見つかりません。保存場所を再確認してください。"
}
python -m research.forward_ecb_link_diagnostic --xml-file $xml
if ($LASTEXITCODE -ne 0) { throw "ECB原本の診断を実施できませんでした" }
~~~

詳細のない `ITEM_LINK_UNAPPROVED` を見て、`SOURCE_HOSTS` を `*.europa.eu` 等へ一括拡張してはならない。保存原本の診断結果と公式サイトの説明を照合後、明示的に必要な**正確なFQDNのみ**別途レビューする。既存の `NO_GO`、安全停止ラッチ、demo/real注文禁止、マクロ/予想/AIレビュー不足は継続。PowerShellの `if` と `else` は対話モードで別々に貼ると `else` 単独コマンドとして扱われるため、必ず同一ブロックとして実行する。


## FWD-1490〜1492：ECB 15記事すべて同一公式ホスト、パス形式だけが拒否（実機結果）

2026年11月17日の保存済みECB原本（5859 bytes、ローカルSHA256 `b34f2f8fc607bb8b4c4f8e720ab014fbba4d389aadf61ea92d0937ff857f945c`）を利用した実機診断で、15件全て `https://www.ecb.europa.eu` のホストとスキームに一致したが、15件とも `UNSAFE_PATH_REJECTED` となった。**異なるFQDNを許可する必要性は確認されていない。** この診断だけではパスが空なのか `//` で始まるのか不明。

次版の `research.forward_ecb_link_diagnostic` は既存の全拒否を、`EMPTY_URL_PATH`（URLにパスがない）、`DOUBLE_SLASH_URL_PATH`（パスが `//` で始まる）、`URL_PATH_NOT_ABSOLUTE`（絶対パスでない）の3つにさらに分類する。生のパスやクエリ文字列は出力しない。同時に `distinct_link_count` を追加し、15記事が個別記事へ結びつく固有URLかどうかも、URL原文を公開せずに検査する。

実行は原本に対するオフライン読み取りのみで、次の短いコマンドを用いる。更新版に切り替えた後、前回の `$xml` を再利用する。

~~~powershell
python -m research.forward_ecb_link_diagnostic --xml-file $xml
~~~

結果が `EMPTY_URL_PATH` の場合、記事のリンクが同じホームページを指すのか等を独立確認する。`DOUBLE_SLASH_URL_PATH` の場合でも**単純なスラッシュ縮約や検証条件の解除は行わない**。原本内のリンク形状とECB公式サイトの説明を確認し、個別記事識別と出典評価ができる範囲で限定的に設計する。新しい判断を経るまで、全て `NO_GO`・非発注、マクロ/AI研究ジャーナル0を維持。

## FWD-1493〜1497：ECBプレスRSSの二重スラッシュURLを原文保持で限定受理

2026年11月17日の実原本（5859バイト、15記事、固有URL15件）は、記事リンクが全てHTTPS・正確なホスト www.ecb.europa.eu であり、パス先頭の二重スラッシュだけが拒否原因だった。別ホストの解放やSSL検証無効化は不要。

今回の実装では、ECBの ecb_press 記事リンクのみ、HTTPS・正確な同一ホスト・認証情報なし・非標準ポートなし・フラグメントなしという既存制限を維持した上で、限定された二重スラッシュのURLパスをRSSメタデータとして保存できる。パス先頭はスラッシュちょうど2個で、最初のセグメントは press、home、pub、stats、events のいずれか。三重スラッシュ、内部二重スラッシュ、空・ドット・親ディレクトリのセグメント、バックスラッシュ、パーセント符号化は禁止。**元のURLを勝手に単一スラッシュに正規化しない。** 記事リンクへのアクセスは実行せず、BLS/FRB/BOJの従来検証も変更しない。

注意: 保存済みの実原本15件が全てこの狭い条件に合致するかは未検証。1件でも形式が異なれば保存全体をFORMAT_VALIDATIONのHOLDにする。原本のリンクの安全性を独立認証したという主張はしない。

Windowsでは更新版取得後、既に保存した元XMLの**完全オフライン**取り込みだけを実行する。

~~~powershell
cd C:\Users\Suzuki\Documents\ChatGPT\Fx-MACRO-FWD-20261113
if (@(git status --porcelain).Count -gt 0) { throw "作業ツリーに未保存変更あり" }
git fetch origin
if ($LASTEXITCODE -ne 0) { throw "fetch失敗" }
git switch --detach origin/feat/fwd-1441-macro-refresh-research-launch
if ($LASTEXITCODE -ne 0) { throw "開発版切替失敗" }
$root = "$env:USERPROFILE\Documents\FXForwardEvidence"
$store = Join-Path $root "macro_forward_journal"
if (-not (Test-Path -LiteralPath $xml -PathType Leaf)) { throw "ECB XML原本が見つかりません" }
$out = Join-Path $root ("ecb_local_verified_" + (Get-Date -Format "yyyyMMdd_HHmmss_fff"))
python -m research.forward_macro_feed_once --store $store --out-dir $out --feed ecb_press --feed-file "ecb_press=$xml"
python -m research.forward_observation --store $store --audit
~~~

成功時に期待されるのは OFFICIAL_FEEDS_ARCHIVED_HOLD_NO_GO、feed_bundles_verified_format=1、fetched_news_items=15、new_recent_us_journal_records=0、network_calls_attempted=0、注文0。失敗時は原本を改変せずpython -m research.forward_ecb_link_diagnostic --xml-file $xml で拒否理由を確認する。この対応はRSSの事後ニュース原本の保存に限り、実経済指標の発表前予想、発表値、AIレビューや取引権限を捏造しない。
