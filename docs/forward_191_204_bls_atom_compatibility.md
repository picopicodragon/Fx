# FWD-191〜204：BLS Atom 1.0への安全対応（RSS 2.0は維持）

## 実測による変更根拠（2026-11-12）

利用者のWindowsから、`bls_cpi`と`bls_empsit`の公式許可URLへのHTTP取得に成功した一方、現行の`research.forward_rss_diagnose`は`UNEXPECTED_XML_ROOT`を報告。その後、本人による**本文を保存・表示しないXMLルート分類**で、両方とも`ATOM_FEED`と確認。RSS 2.0だけを受ける`research.forward_rss.parse_feed`と配信XMLが不一致だったことが判明。

BLS配信先のRSS一覧ページは`https://www.bls.gov/feed/`。既存の安全な配信URLは変更しない。BLSが全記事でAtomの`published`などを提供しているかは未確認であり、**実機の配信本文に対する全項目の最終検証はWindows側で行う**。

## 対応範囲

- **FWD-191〜198:** `research.forward_rss`の`parse_feed`が既存の`<rss><channel><item>`に加えて、`{http://www.w3.org/2005/Atom}feed`のAtom 1.0を解釈。Atomは**BLS CPI/雇用統計の2フィードのみ**で許可し、FRB`fed_policy`は既存RSS形式だけのまま。
- Atom各`entry`の`title`、唯一の`alternate`リンク、`published`、`summary`または`content`を既存の`MACRO_EVENT`形式へ変換。リンク先はBLSのHTTPS公式ホストのみ。Atomの`updated`は記事の変更時刻であり**本来の公表日時として代用しない**。`published`欠落/時区間不明はFail Closed。
- RFC3339のタイムゾーンをUTCに変換し、取得より未来の日時は禁止。市場予想/発表結果を補完しない（`consensus=""`, `released_value=""`、`USER_SUPPLIED_UNVERIFIED`）。
- URLの自動切替、リダイレクト、追加の外部ホストを許可しない。レスポンス最大256KB、30エントリー上限、1回の新規収集3件（明示時最大5件）、公表から24時間以内だけ収集、過去記事や重複リンクは前方の新規イベントに偽装しない。原ジャーナルは既存の監査・ハッシュ連鎖/排他制御で保存。
- **FWD-199〜201:** `research.forward_rss_diagnose`がAtomの日時欠落、タイムゾーン欠落、複数alternateリンク、他ホストの判定を固定コードで分類。診断は取得のみ・書込みなし。
- **FWD-202〜204:** 合成Atom、古いRSS、証拠時刻、未来時刻、別ドメイン、DTD/ENTITY、重複、過多、オフラインXML、診断の回帰テスト。

## Windowsで最初に実行する手順

PR #266のブランチを取り込んだ後、まず**登録せず**診断：

```powershell
cd C:\Users\Suzuki\Documents\ChatGPT\Fx
git fetch origin
git switch --detach origin/fix/fwd-191-204-atom-feed-compatibility
python -m research.forward_rss_diagnose --store "out/forward_macro_research_001" --feed bls_cpi --allow-network
python -m research.forward_rss_diagnose --store "out/forward_macro_research_001" --feed bls_empsit --allow-network
```

`RSS_DIAGNOSTIC_PREFLIGHT_OK_NO_GO`なら構造検査通過。出力の`feed_items_parsed`、`unseen_published_within_24h`、`already_seen_in_this_feed`で現状の収集可能件数を確認する。これらのコマンドは外部取得を各1回実行するが、**ジャーナルにはまだ何も登録しない**。

合成テストは実Atomデータの全スキーマを認証するものではない。実フィードに`published`が無ければ`ATOM_PUBLISHED_MISSING_OR_INVALID`になり、元の更新日時を公表日時に擬装しない。URLが変わった場合も自動リダイレクトしない。

構造が有効で新規24h項目が1〜3件存在するときだけ、**別操作で**既存の正規取り込みコマンドを実行：

```powershell
python -m research.forward_rss --store "out/forward_macro_research_001" --feed bls_cpi --allow-network --max-new 3
python -m research.forward_rss --store "out/forward_macro_research_001" --feed bls_empsit --allow-network --max-new 3
```

**注意：** 2026-11-10の経済指標記事は2026-11-12時点では既に24時間より古い可能性が高いため、Atomパーサーの改善後でも`new_recent_items=0`は正常。情報の日時を書き換えて過去の価格114CSVと恣意的に照合しない。イベントが登録されても事前の市場コンセンサスは別資料で検証が必要。

## 残る安全条件

最新のBLS Atom本文を本環境から独立に取得・照合したわけではない。厳格な構文検査が未対応フィールドを検出した場合は不正取り込みではなく停止/原因分類する。発注権限は常に`NO_GO`、`safety_hold_latched=true`、`real_orders_permitted=false`、デモ注文禁止。MT4単一デモ口座・読み取り専用観測設定を変更しない。AIモデル課金なし。
