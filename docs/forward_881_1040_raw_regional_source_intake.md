# FWD-881〜1040：保存済みの実原本と市場予想を一括研究評価へ取り込む

## 目的
既存の合成・静的テストを増やすだけでなく、ユーザーが実際に保存した米欧日の公式発表予定、発表前の市場コンセンサスの原文、MT4観測ソース、価格・AIジャーナルを一括監査に渡せる状態にする。**実原文、公開・取得時刻の真正性は自動認証されない**。独立証明がない限りNO_GOと注文禁止を保持。

## 主要実装
### 1. research.forward_regional_source_intake
manifestを指定して、同じディレクトリにある保存済みUTF-8テキストまたはHTMLを1件ずつオフラインで読み込む。最大64ソース、64イベント、原本512KB/件。URLを訪問したりダウンロードしたりしない。
- 公式予定の許可ホストは、USD：BLS/Federal Reserve/BEA/Census、EUR：ECB/欧州委員会サイト、JPY：日銀/総務省統計局/厚労省/内閣府経済社会総合研究所/財務省。ホスト名は完全一致、HTTPS限定。**許可ホストへのURL記載は、そのURLから本当に取得した証明ではない**。
- 各ソースの保存ファイルのSHA256とmanifest内のSHAを照合し、指定された引用文が原文の連続した文字列であることを確認。URL、種別、公開時刻、取得時刻を保持。未来時計、SHA不一致、パス移動・シンボリックリンク、未使用ソースは拒否。
- 予想値については数値が引用文中に実際に現れることをチェックし、発表15分前より**前**の自己申告取得時刻を必須とする。予想数値が引用文の正しい市場予想と一致するかは**意味的に認証しない**。
- 取得後の観測形式は既存 `fx_fwd_external_macro_observation_v1` と同じ。既存 `forward_global_macro_evidence.inspect_observations` でもチェックし、互換JSONを `--emit-observations` で新しいファイルへ書き込み可能。既存原本ディレクトリへ書き込まず、通常は読み取り専用。

### 2. research.forward_evidence_runbook
- 既存の証拠プランに任意項目 `regional_source_manifest` と `mt4_observer_source` を追加。既存の古い8項目プランもそのまま読み込める。
- `regional_source_manifest` があれば保存原本を再解析し、自動で既存のUSD/EUR/JPYマクロ研究判定へ連携。`external_macro_file` の同時指定は禁止し、重複した証拠を2回数えない。
- `mt4_observer_source` があればMQL4観測器の静的検査を既存監査で実行。OrderSend等の禁止呼出しを検出するが、ソースに見当たらないからといってコンパイル済みEA・ブローカー注文の不可を証明しない。
- 既存の `observation_store` を**JSON単体ファイルでなくジャーナルディレクトリ**として扱うよう修正。価格・AI連携の既存入力契約と整合。
- 今回追加した証拠も、既存のBLS原本・公式ニュース・予想アーカイブ・MT4 CSV・合成安全ドリルと一括して評価。CIの合格だけで受入可能と判定する経路は設けない。

## ソースmanifestの形式
`original_manifest.json`（以下は構造例。タイトル・日時・数値は**説明用の架空値**であり、原本から検証できないまま転記してはいけない）：

    {
      "schema": "fx_fwd_regional_original_source_manifest_v1",
      "observed_at_utc": "2026-11-13T03:00:00Z",
      "horizon_days": 14,
      "sources": [
        {
          "source_id": "official_us_calendar",
          "source_kind": "OFFICIAL_SCHEDULE",
          "filename": "official_schedule.txt",
          "source_url": "https://www.bls.gov/schedule/news_release/",
          "sha256": "実際のUTF-8原本バイト列のSHA256",
          "published_at_utc": "原文で確認した公表UTC（未確認なら作成しない）",
          "captured_at_utc": "原本保存UTC時刻（ローカル時計、独立証明なし）"
        }
      ],
      "events": [
        {
          "event_id": "manually-observed-event-id",
          "currency": "USD",
          "event_type": "INFLATION",
          "title": "原本にあるイベント名",
          "scheduled_at_utc": "原本で確認した発表予定UTC",
          "calendar_source_id": "official_us_calendar",
          "calendar_excerpt": "official_schedule.txt内の完全一致の引用",
          "consensus": null
        }
      ]
    }

予想原本があるときだけsourcesに `source_kind: PRE_RELEASE_CONSENSUS` の別レコードを追加し、対応イベントのconsensusに `source_id`、`excerpt`、`value`、`unit` を指定。予想の正しい発信元、日付、数値を推測してはならない。manifestの `published_at_utc` と `captured_at_utc` の時刻は申告値として扱う。

## Windows実行手順
既存Windows作業フォルダーや保存BLS原本を変更しない。GitHub新ブランチを **別のdetached worktree** として取得後、実証拠の保存ディレクトリにmanifestを作成して以下を実行。

    $asof = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
    python -m research.forward_regional_source_intake --manifest 'C:\path\to\saved-originals\original_manifest.json' --asof-utc $asof

初回だけ既存runbookを作る場合（指定した実ファイルが存在すること）：

    python -m research.forward_evidence_runbook --init-plan out/real_forward_plan.json --init-bls-snapshot-dir $originalBundle --init-regional-source-manifest 'C:\path\to\saved-originals\original_manifest.json'

以後は元の研究プランを使って一度に横断チェック可能。

    python -m research.forward_evidence_runbook --plan-file out/real_forward_plan.json

原本が実際には未取得なら、架空のURL・予想・公表日時を作らず、プランの `regional_source_manifest` はnullにしてNO_GOの欠落理由を受け取る。

## 安全と残課題
- 完全オフライン、ブローカー0、MT4/EA起動0、API0、注文0、バックグラウンド監視0。
- 公式発表の情報収集・発表前予想の時点付き保存は本人が独立証拠を取得するまで未完了。ニュースRSSだけでは将来経済カレンダーや市場予想の代わりにならない。
- MQL4コードの静的判定は実EAの安全性を保証しない。デモ口座のサーバー時刻、自己申告ローカル時計の真偽、人間承認条件も別途実証が必要。
- 1取引0.5%、合算1%、日次1.5%、DD停止/解除、NY17、±15分発表停止の既存規則は無変更。
- `runtime_go_no_go=NO_GO`、`safety_hold_latched=true`、`demo_orders_permitted=false`、`real_orders_permitted=false`。
- mainへのマージは人間承認のみ。既存のWindows未コミットファイル、BLSスナップショットや価格CSVは変更しない。