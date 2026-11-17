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
