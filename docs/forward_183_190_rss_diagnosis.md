# FWD-183〜190: BLS/FRB公式RSSの失敗原因を分類する読み取り専用診断

## 事象（2026-11-12）

実利用者が`out/forward_macro_research_001`を初期化（`FORWARD_SESSION_INITIALIZED_NO_GO`）。`python -m research.forward_rss`のネットワーク収集で`bls_cpi`、`bls_empsit`は`RSS_INGEST_UNSAFE_OR_UNAVAILABLE`、`fed_policy`は`fetched_items=15, new_recent_items=0`。その後の研究ボードは`macro_events=0`と正常に記録。**BLSの失敗原因はこの一般的なエラー文字列からは断定不能**。

BLS公式配信ページは2026-11-12時点で`https://www.bls.gov/feed/cpi.rss`と`https://www.bls.gov/feed/empsit.rss`を掲載しており、URLを憶測で切り替えない。公式RSSであってもネットワーク経路によって403/429/リダイレクト/HTML差替などが発生する可能性があり、**実際のHTTP応答を診断するまでは未確定**。FRBの`new_recent_items=0`はRSSに15件あっても、未登録かつ公開24時間以内の項目が0件だったためであり、エラーではない。

## 追加した読み取り専用診断

`research.forward_rss_diagnose`は、既存`research.forward_rss`のエンドポイント許可リスト・無リダイレクトfetch・RSS構文検証・ローカルジャーナル全連鎖監査を**そのまま再利用する**。ネットワークは`--allow-network`を明示したときのみ。あるいは既に保存した**正規のRSS XML**を`--xml-file`で渡してネットワーク不要。両方の同時指定は禁止。

- stage=`JOURNAL_AUDIT`: ローカルの観測記録が壊れていないか。
- stage=`FETCH`: HTTP 403/404/429/5xx、TLS・DNS・timeout・配信元リダイレクト拒否を**固定コード**として分類。HTTPレスポンス本文・URL・端末情報・APIキー・ネットワーク例外原文は出力しない。
- stage=`PARSE_AND_PREFLIGHT`: 非RSS HTML/XML、DTD、許可されていないリンク/重複、発表日時形式や未来日時、30件/256KBの入力上限等を検査。
- stage=`PREFLIGHT`: 解析した項目数、同一フィードの既登録件数、直近24h未登録数、古い未登録項目数、入力`--max-new`件数上限との関係を報告。既存のデフォルト上限3・最大5は**変更しない**。
- 診断時は観測ジャーナルに**1件も登録しない**。`journal_modified=false`を明記。正常なRSSでも`real_orders_permitted=false`、`NO_GO`。

### 実行手順（PR #265を取り込んだmain、または開発ブランチから）

PowerShell:

```powershell
cd C:\Users\Suzuki\Documents\ChatGPT\Fx
python -m research.forward_rss_diagnose --store "out/forward_macro_research_001" --feed bls_cpi --allow-network
python -m research.forward_rss_diagnose --store "out/forward_macro_research_001" --feed bls_empsit --allow-network
python -m research.forward_rss_diagnose --store "out/forward_macro_research_001" --feed fed_policy --allow-network
```

これは**最大3回の明示的HTTP GETのみ**であり、RSS自動再取得・スケジュール監視・AI課金・デモ/本番発注は実施しない。結果は各フィード1件ずつ構造化JSON表示。

**結果の読み方：**

- `stage=FETCH`, `reason_code=HTTP_403`：先方がHTTPアクセスを拒否。IP・TLS・ポリシーのどれが原因かは断定不可。繰り返し再試行せず、公式の配信をブラウザーで開けるか確認する。ブロック回避のプロキシ・UA偽装・短間隔の再試行を**実装しない**。
- `HTTP_429`：アクセス頻度制限の可能性。手動で長く間隔を空けて扱う。自動再試行禁止。
- `HTTP_REDIRECT_REJECTED`：リンク先変更の可能性、最新公式のURLとコードを人間が照合。自動リダイレクトを認めない。
- `UNEXPECTED_XML_ROOT`：HTML等がXMLとして返された可能性。本文は表示しない。
- `RSS_ITEM_COUNT_LIMIT`：配信中の項目が上限30を超えている。無断の上限拡大はしない。
- `NEW_RECENT_ITEMS_OVER_CAP`：取得・構文検証は通ったが未登録の直近24時間項目が`--max-new`を上回った。4〜5件なら本人の明示判断で既存の最大5件オプションを使う。6件以上は**自動で一部切捨て/再実行しない**。
- `RSS_DIAGNOSTIC_PREFLIGHT_OK_NO_GO`かつ`unseen_published_within_24h=0`：正常取得したが追加対象なし。FRB今回の結果と整合する可能性。
- `NETWORK_TLS_DNS_OR_TIMEOUT`：ローカルDNS/TLS/通信障害の可能性。詳細な秘密情報はログへ出さない。
- `JOURNAL_AUDIT`のエラーは元記録不整合。元のファイルを手動削除・再作成して隠蔽しない。

オフラインで正規RSS XMLをブラウザ等から保存済みの場合：

```powershell
python -m research.forward_rss_diagnose --store "out/forward_macro_research_001" --feed bls_cpi --xml-file "out/bls_cpi_manually_saved.xml"
```

ここでも検査のみ。診断が通っても、通常の収集コマンドを別途明示するまではイベント登録0件。

## 今後のマクロAI判断への接続

判定が正常になり、未登録の直近24時間RSSデータが存在するときにだけ、既存`research.forward_rss`の**通常取り込み**を実施する。RSSに事前予想値は入っていないため、収集後も`NO_POINT_IN_TIME_CONSENSUS`は残る。既に取得後の経済データを過去の実測114CSVに遡って事前予測に使わない。日付を後から改変しない。

**常時NO_GO、safety_hold_latched=true、real_orders_permitted=false、demo_orders_permitted=false**。本機能はエラー調査のみ。取引の準備・実行機能ではない。
