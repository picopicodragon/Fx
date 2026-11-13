# FWD-441〜488: BLS/FRB/ECB/日銀の公的ニュースRSSを一括取得、原本保存、検査

## 2026-11-13の開発方針
ユーザーの開発速度重視の方針に従い、48工程の研究機能・統合・合成回帰・手順を一つのPRにまとめる。これ以上BLSの個別HTML照合で止まらず、USD/EUR/JPY各地域の公表済みニュースの収集を増やす。mainは本人の手動承認のみ、デモ/本番の注文は依然禁止。

## 新コマンド
`research.forward_multi_official_news_snapshot` は既存のBLS/FRB公的フィード実装を利用し、ECB、日銀の公表済みニュースRSSを追加で扱う。下記URLは各行の公式提供ページで確認。5フィードの既定の全取得は明示 `--allow-network` を付けた場合に限る。

- bls_cpi: https://www.bls.gov/feed/cpi.rss
- bls_empsit: https://www.bls.gov/feed/empsit.rss
- fed_policy: https://www.federalreserve.gov/feeds/press_monetary.xml
- ecb_press: https://www.ecb.europa.eu/rss/press.html (ECB RSS一覧 https://www.ecb.europa.eu/home/html/rss.en.html)
- boj_whatsnew: https://www.boj.or.jp/en/rss/whatsnew.xml (日銀 https://www.boj.or.jp/en/tips.htm)

### 取得と保存
- **ユーザーが1回だけ `--allow-network` を指定**した場合に、固定HTTPSフィードを各1回、12秒上限、最大256KB、リダイレクトなし、自動リトライなしで取得。BLSとFRBは既存forward_rss.get_feedを再利用。
- `--feed ecb_press --feed boj_whatsnew`など明示的に少数だけ対象にできる（--allow-network必須）。指定なければ全5フィードを対象。
- ネットワーク無しで `--feed-file ecb_press=保存.xml` などを並べるモードも可。ネットワークモードと同時指定不可。
- 出力先はまだ存在しない専用ディレクトリ。取得した `feed-id.xml` を原本バイトで保存し、SHA256・バイト数・観測UTCローカル時計値・解析されたitem件数をmanifest.jsonに記録。manifestは全原本保存後に最後に生成し、途中失敗は未完了として扱う。既存のoutファイルを上書きしない。
- 原本解析はDTD/ENTITY拒否、フィード別公式同一ホストのHTTPSリンク、既知のRSS2/Atom1形式、公開時刻のタイムゾーンと観測前、公表件数の上限を検証。合致しない形式は自動補正せず失敗。
- `--verify-bundle` で完全オフライン再解析し、manifest内容と原本SHAを検証。ニュース記事のタイトルはSHAだけ記録し、値や通貨方向のAI推定をしない。
- 過去ニュースの `pubDate`/`published` は予定時刻やコンセンサスではない。ネットワーク成功でも `scheduled_event_count=0`、`pre_release_consensus_count=0`、`NO_GO`。

### 統合
- `research.forward_global_macro_evidence`、`research.forward_macro_integrated_readiness` に任意 `--official-news-bundle` を追加。受け取ったニュースバンドルの完全性を照合し、ニュース件数・USD/EUR/JPYの各情報源種別を表示。
- `OFFICIAL_RSS_NEWS_NOT_A_FUTURE_MACRO_CALENDAR`/`PUBLISHED_RSS_NEWS_CANNOT_REPLACE_FUTURE_EVENT_CALENDAR`などの保留を付与し、取引・予想の認証条件を満たしたとはみなさない。
- 既存のBLSカレンダーと価格CSV/AI研究セッションは別の入力のまま。保存済み原本に勝手にイベントを追加しない。

## Windowsでの実行例
新しい別worktreeでPRブランチを取得後、非発注の研究用取得として以下を明示的に実行できる。

    New-Item -ItemType Directory -Force out | Out-Null
    $capture = "out/official_news_$(Get-Date -Format yyyyMMdd_HHmmss)"
    python -m research.forward_multi_official_news_snapshot --allow-network --out-dir $capture
    if ($LASTEXITCODE -eq 0) { python -m research.forward_multi_official_news_snapshot --verify-bundle $capture }

最初のネットワーク検証で403/429や想定外XMLが返るとFail Closedし、**別サイトへの回避や自動再試行はしない**。原本取得時刻はWindowsのローカル時計に基づき、出版元の本当の公開時刻やデータの完全性は独立認証されていない。

## 安全と未解決事項
- コードは研究用でMT4/EAやブローカー接続を実施しない。価格・取引リスク制御や停止解除は変更しない。
- RSSは公表**後**の更新の観測手段であり、今後の重要経済イベントの完全カレンダーや発表前市場コンセンサスは未収集。次段階で出典ごとの事前予想原本と独立時計、MT4非発注環境の長時間監査が必要。
- 元のFx作業フォルダーの未コミット差分と既存の114価格CSV、BLS原本を変更しない。
- `NO_GO`、`safety_hold_latched=true`、`demo_orders_permitted=false`、`real_orders_permitted=false`固定。