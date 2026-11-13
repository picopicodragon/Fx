# FWD-1041〜1200: 保存済み原本の一括パッケージ化・BLS照合・runbook統合

## 開発の目的
これまでの人工的なテストケース作成から、利用者が実際に保存した米欧日の経済指標ページ、発表前コンセンサス、BLS原本を利用するフォワード研究へ進む。原本のSHA256を手入力したり、manifestの中立ファイル名を人手で決める必要を減らす。出版社・出典時刻は独立認証されておらず、研究NO_GOは維持。

## 新モジュール: research.forward_regional_original_bundle
利用者のrequest.jsonに、source_file（既に保存済みUTF-8/HTMLファイル）、source_url、source_kind、published_at_utc、captured_at_utcを明記し、eventsで指標名・予定UTC・原本に完全一致する引用・存在する場合だけ予想値を示す。
SHA256、保存ファイル名（original_001.txtなど）、完全一致した原文引用、前15分締切を一括検査する。出力は新規専用ディレクトリで、原本コピーと最後の original_manifest.json。保存後には従来の厳格な regional_source_intake.load でも再検証する。
最大64原本、512KB/件、最大64イベント。ネットワーク・自動探索・イベント/予想/出典日時の推定なし。元ファイルの改ざんや同一元ファイルの重複、引用値の不一致は拒否する。出力先は既存原本ディレクトリの中に作れず、上書き不可。

request.jsonの必須構造（以下の角括弧内は入力例ではなく説明用のプレースホルダー。実際のデータを保存原文に基づいて設定する）：

    {
      "schema": "fx_fwd_original_package_request_v1",
      "observed_at_utc": "保存原本を確認した実際のUTC",
      "horizon_days": 14,
      "sources": [{
        "source_id": "official-1",
        "source_kind": "OFFICIAL_SCHEDULE",
        "source_file": "saved_calendar.html",
        "source_url": "実際の公式HTTPS URL",
        "published_at_utc": "公式出典で根拠を確認した公表UTC",
        "captured_at_utc": "原本を保存したUTC"
      }],
      "events": [{
        "event_id": "release-1",
        "currency": "USD",
        "event_type": "INFLATION",
        "title": "原本にある名称",
        "scheduled_at_utc": "原本にある発表予定UTC",
        "calendar_source_id": "official-1",
        "calendar_excerpt": "原本に完全一致する引用文",
        "consensus": null
      }]
    }

発表前コンセンサスを追加するときは、source_kind=PRE_RELEASE_CONSENSUSの独立した保存原本をsourcesに追加して、イベントconsensusにsource_id、excerpt、value、unitを指定する。保存した原文内に予想値が含まれ、記録時刻が発表15分より前でなければ拒否。公表時刻が不明な場合は推測で埋めない。

## Windowsでの一括実行
保存原本とrequest.jsonを準備した後、別worktreeに切り替えて次のコマンドで一度だけ確認する。まず出力なしのpreflightを実行する。

    $asof = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
    python -m research.forward_regional_original_bundle --request 'C:\saved_sources\request.json' --asof-utc $asof

検証成功時だけ、未存在の出力フォルダーに原本を保存する。実ディレクトリ名は利用者の保存場所に合わせる。

    $out = 'out\regional_bundle_' + (Get-Date -Format yyyyMMdd_HHmmss)
    python -m research.forward_regional_original_bundle --request 'C:\saved_sources\request.json' --asof-utc $asof --out-dir $out

生成された original_manifest.json の絶対パスを既存runbookのregional_source_manifestに設定する。BLSスナップショットもプランにある場合は保守的な時刻/名前照合が同時に実行される。

    python -m research.forward_evidence_runbook --plan-file out/real_forward_plan.json

## 新モジュール: research.forward_saved_macro_conflict
実保存BLS ICS/HTMLと、同じBLS公表元を名乗るregional_source_manifestの保存記事を、完全一致するタイトル＋UTC時刻で機械的に比較する。名称のみ一致する時刻違い、時刻のみ一致する別名称を区別し、いずれも原本の改訂・省略の可能性として未解決報告する。自動的なイベント追加、名称補正、実発注停止判断は行わない。BLSの2形式と別保存ページは独立出版社ではない。

## 完了までの未検証事項と安全
- URL文字列の許可と原本SHA合格は、公式サイトへの実接続や真の公開時刻の独立証明を意味しない。
- 米欧日マクロイベントの完全網羅・発表前市場予想の出典時刻・意味的正確性は実資料で別途確認する。
- MT4デモ口座・サーバー時計・通信障害時の独立watchdogと注文停止・人間承認は実機で未証明。
- ネットワーク0、AI API0、MT4/EA操作0、注文0。NO_GO、safety_hold_latched=true、demo_orders_permitted=false、real_orders_permitted=false固定。
- 既存リスクルール（1取引0.5%、合算1%、日次1.5%、DD4/5%、NY17、イベント前後15分）を変更しない。
- 旧Fx Windows作業フォルダーと保存原本を変更せず、mainの最終マージは人間の承認のみ。