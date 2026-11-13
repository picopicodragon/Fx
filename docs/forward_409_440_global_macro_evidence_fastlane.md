# FWD-409〜440: USD / EUR / JPY マクロ原本・発表前予想の一括検証（NO_GO）

## 開発速度の改善
個別BLS不一致の解析工程を終えた。以後、関連機能とテストを一つのPRにまとめ、Linux/Windows CIを一括実行する。各工程ごとの手動実行・マージを要求しない。mainは本人最終承認のみ、注文許可と仕様変更は行わない。

## 新しい機能
- research.forward_global_macro_evidence: 保存済みBLS ICS/HTML（任意）とUSD/EUR/JPYの外部マクロ予定・発表前市場予想（任意）を同じNO_GO研究判定に集約。
- 外部JSON: schema=fx_fwd_external_macro_observation_v1。トップは schema / observed_at_utc / horizon_days / events の4項目。イベント数0〜64、最大180KB。全時刻はUTC末尾Zで秒精度。
- イベント項目: event_id / currency (USD,EUR,JPY) / event_type (MONETARY_POLICY,INFLATION,EMPLOYMENT,GROWTH,OTHER) / title / scheduled_at_utc / calendar_source / consensus。
- calendar_sourceの必須項目: source_url（HTTPS）/ source_text（1〜2000文字）/ source_sha256（source_textのUTF-8 SHA256）/ published_at_utc / captured_at_utc。すべて自己申告であり、出典の真正性や時計の独立認証はない。
- consensusは欠測ならnull。存在する場合の構造は value（有限の十進文字列）/ unit（既存ALLOWED_UNITS）/ source（上記と同じ5項目）。取得時刻は発表15分前より早くなければ拒否。原文と数値の意味的対応は未検証。
- 公開≦取得≦観測＜予定の厳格な時刻順序。観測した未来の予定は31日以内。ハッシュ・日時・URL・イベント重複、数値形式不正をFail Closedで拒否。
- 各通貨の観測件数、事前予想の欠測件数、ソースホスト（未認証）、3ペアへの参考情報を表示。ただし情報源が各通貨で1件あっても経済カレンダー全体の網羅性は証明されない。
- 既存 research.forward_macro_integrated_readiness に任意の --external-macro-file を追加し、価格/AI研究ボードで同じ保留理由を合算。従来引数を保持。

## まず実行できるWindowsコマンド
現在の $originalBundle にある保存済みBLS原本を再使用。新ブランチworktreeを取得した場合、以下の一度の実行だけでBLSの不一致、地域イベント不足、コンセンサス未取得を表示する。

    $asof = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
    python -m research.forward_global_macro_evidence --bls-snapshot-dir $originalBundle --asof-utc $asof

外部証拠が揃ったときだけ --external-macro-file <検証対象JSON> を追加する。仮の数値、出典、公開日時を作らず、未取得なら入力自体を省略する。合成テストのイベントは実資料に転用しない。

## 安全と限界
- ネットワーク、AI API、ファイル書き込み、MT4/EA、ブローカー接続、デモ/本番注文はいずれもゼロ。
- 予想値・イベント時刻の外部認証を自動的に行う機能ではない。BLS同一発行元のICSとHTMLも独立第三者検証にはならない。
- 既存の1取引0.5%、合算1%、日次1.5%、DD4/5%、前後15分停止および本人承認条件は変更しない。
- runtime_go_no_go=NO_GO、safety_hold_latched=true、demo_orders_permitted=false、real_orders_permitted=false固定。
- 次の重点：実際の米欧日のイベント予定を安全に収集し、出典と市場予想を発表前に保存する方法、MT4の非発注監視の独立検証。