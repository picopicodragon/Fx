# FWD-205〜252：実マクロ判断のための先行コンセンサス・発表時刻・二段階AIフォワード研究

## 背景・実機データ

- 既存楽天MT4単一デモ端末、3ペア USD/JPY・EUR/JPY・EUR/USD、2セッション合計114CSV・38完全周期のオフライン研究を維持。
- 2026-11-12、ユーザーがBLSのCPI・雇用統計両フィードを**Atom配信と確認**。PR #266の対応後、両フィードで実機取得・パース正常（各12記事）、ただし公表から24h以内の新規記事0。過去記事は過去に遡って新規情報と扱わない。
- `out/forward_macro_research_001`は作成済みだが、現段階で`macro_events=0`、二段階AI実際の判断・取引成績は未蓄積。**このPRは開発実装と合成テストを行い、存在しない市場予想や事後予測を捏造しない。**

## FWD-205〜212：BLS経済イベント15分前後の研究用停止窓

`research/forward_macro_event_windows.py`：

- 既存`forward_bls_calendar`の**オフラインICS由来レポート**を入力。BLS固定公式URL、元SHA256形式、カレンダーの研究状態、イベント名と時刻・前処理上限を検査。
- 各BLSイベントに対し公開予定時刻の**15分前〜15分後**の研究注意窓、再評価必要状態、全3ペア研究上の注意対象を算出。
- 研究用であって**EA発注停止機能や解除許可ではない**。米国外・他の金融政策を含む全イベントカレンダーの完成認証にはならない。停止終了時刻後も安全確認なき自動再開は認めない。
- 報告から24h超過したカレンダーは`CALENDAR_SNAPSHOT_OLDER_THAN_24H`を記録。

## FWD-213〜222：発表前の市場予想を時刻付きで改ざん検出可能に保存

`research/forward_macro_pre_release_capture.py`：

- 元BLS予定の日時とタイトルが**完全一致**する研究用イベントに限り、発表の15分前より早く取得した市場予想の値・単位・短い出典引用・HTTPSリンク・引用SHA256を新規JSONに保存。
- 収集日時はプログラムの**実際のUTC実行時計**で刻む。CLIで過去の時刻を指定して事前入手を偽装する機能は設けない。
- ユーザー入力の`source_published_at_utc`は独立検証されず、引用元の真正性や市場の代表コンセンサスを証明しない。
- 外部データ収集は行わず、**実際の予想値の一次証拠を人間が用意**する。原文の著作権・機密情報に注意。指定パスが既存なら`open("x")`で上書き拒否。SHA256はローカル整合性であり外部タイムスタンプ署名ではない。

予想提出JSONのスキーマは`fx_fwd_pre_release_consensus_submission_v1`。`event_title`、`scheduled_at_utc`、`pair`、`value`、`unit`、`source_text`、`source_sha256`（**source_textのUTF-8 SHA256**）、`source_url`、`source_published_at_utc`が必要。

## FWD-223〜233：事前予想＋実測発表値＋BLS記事の結合

`research/forward_macro_evidence_handoff.py`：

- 既存`forward_observation`のハッシュ連鎖上に**実際に保存済み**のBLS記事レコードSHA256を必須指定。CPIはCPI予定、雇用統計は雇用予定、公式記事と発表予定の公表時刻は0〜4時間の範囲に限る。
- 保存済みの予想書類を独立再検査。公表済み発表値は同一BLS記事のURLと短い引用、引用SHA256、日時、数値、同一単位を要求する。手元の市場予想をAIが勝手に創作したり、RSSの長文から適当な数値を推測しない。
- `forward_macro_consensus_surprise`を再利用して実績−予想の数値差を確認。元BLSイベント・予想保存・発表値引用の3ハッシュを研究用テキスト内に保持。
- 出力は**研究ジャーナルへの登録準備ができた単一MACRO_EVENT JSON**であり、まだジャーナル書き込みなし。明示`forward_observation --ingest`で初めて新しい書込が発生する。出典認証・モデル承認・注文許可ではない。

発表値入力JSONは`fx_fwd_release_source_submission_v1`。必須`value`、`unit`、`source_text`、`source_sha256`、`source_url`（BLS記事と完全一致）、`source_published_at_utc`（発表予定以降）。事実・時刻の検証証拠がなければ生成しない。

## FWD-234〜244：二段階AIへの引渡しと課金前ゲート

`research/forward_macro_two_model_gate.py`：

- ハッシュ連鎖に登録された**結合済み**マクロイベントを、既存の`forward_ai_shadow`の二段階AI研究・課金ジャーナルへ厳密につなぐ。
- 初期実行は**検査のみ、API 0、追加課金 0、観測ジャーナル追加 0**。元記事だけで数値コンセンサス未リンクのBLSイベントは課金研究に進めない。FRB政策記事は数値予想がない場合にも「定性政策研究のみ・予想差未認証」の制約付き。
- 主分析/検証モデルは異なる明示モデルIDが必要。ただし異なる文字列は独立性の実証ではない。将来本番モデルの承認でもない。
- `--max-api-calls 1|2 --allow-external-api`を**利用者が明示した場合に限り**、既存の`forward_ai_shadow.run`に委譲する。OpenAI APIキーなし、研究イベントが24hより古い、元の出典不十分、未解決`pending_request`がある場合はAPI呼び出し拒否。
- 既存の課金API台帳は呼び出し前に書き込み、不確実な通信失敗時の再送は禁止。結果と費用は事後に照合。レビュー後の観測ジャーナル公開も`--publish-offline`という**別の明示コマンド**を必要とする。
- `APPROVED`でも研究用に過ぎず、実運用の発注承認を付与しない。AI判断の予想差、金融政策因果・織り込み・反証は別のモデル評価とリアルデータで検証が必要。

## FWD-245〜252：価格・予定・事前予想・AI研究の一括オフライン監査

`research/forward_macro_integrated_readiness.py`：

- 既存`forward_macro_campaign_board`の価格品質、3ペア×38周期、研究イベント、AIレビュー、事後2スナップショット評価に、**BLS予定の研究用停止窓と事前予想書類**を加えた一括オフライン状況レポート。
- 証拠欠落は`NO_BLS_CALENDAR_RESEARCH_SNAPSHOT`・`NO_PRE_RELEASE_FORECAST_CAPTURE_PROVIDED`。スケジュール修正やSHA256のずれは`CONSENSUS_ARCHIVE_CALENDAR_IDENTITY_CHANGED`として保留。書込みは新規のレポートJSONだけ。
- すべて発注禁止、AI課金0件、外部ネットワークなし。

## Windows実行手順（既存資料を変更しない）

**PR #267のブランチを取得する場合：**

```powershell
cd C:\Users\Suzuki\Documents\ChatGPT\Fx
git fetch origin
git switch --detach origin/feat/fwd-205-244-point-in-time-macro-forward
```

**A. 現時点の114CSV・空ジャーナルでも正常動作する統合監査**（すぐに実行可能）

```powershell
$asof = [DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ"); python -m research.forward_macro_integrated_readiness --session "s001=out/mt4_timer_clean_001" --session "s002=out/mt4_timer_clean_002" --store "out/forward_macro_research_001" --asof-utc $asof --out "out/macro_forward_readiness_$(Get-Date -Format yyyyMMdd_HHmmss).json"
```

**B. BLS公式カレンダーを明示的に1回取得して別ファイル保存**（要ネットワーク、費用0、発注なし）

```powershell
python -m research.forward_bls_calendar --allow-network --days-forward 14 --out "out/bls_calendar_$(Get-Date -Format yyyyMMdd_HHmmss).json"
```

実際に生成されたカレンダーファイル名を指定して時間窓検査：

```powershell
$cal = Get-ChildItem "out/bls_calendar_*.json" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
$asof = [DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ")
python -m research.forward_macro_event_windows --calendar-report $cal.FullName --asof-utc $asof --out "out/bls_windows_$(Get-Date -Format yyyyMMdd_HHmmss).json"
```

**C. 発表前の値を人間が実際に入手したときのみ**、独立出典本文SHA256と単位を備えた`out/forecast_submission.json`を手元で作成。発表15分前までに次を実行：

```powershell
python -m research.forward_macro_pre_release_capture --calendar-report $cal.FullName --forecast "out/forecast_submission.json" --out "out/forecast_capture_$(Get-Date -Format yyyyMMdd_HHmmss).json"
```

**D. 発表後24時間以内に実際のBLS Atom記事があれば**、通常の`research.forward_rss --allow-network`を明示実行し、出力の`record_sha256s`の値を原イベントSHAとして保存。記事と一緒に発表値・抜粋の根拠をユーザーが別途入手できた場合にのみ`out/release_submission.json`を作成（欠損・架空の値では進まない）。

```powershell
python -m research.forward_macro_evidence_handoff --store "out/forward_macro_research_001" --event-sha256 "<RSSの実際のrecord_sha256>" --forecast-archive "<実際のforecast_capture.json>" --release "out/release_submission.json" --snapshot-out "out/joined_macro_event_$(Get-Date -Format yyyyMMdd_HHmmss).json"
```

`<...>`は説明用プレースホルダー。存在しないハッシュ・レポートで実行しない。

その後、人間が準備済みイベントを観測ジャーナルへ登録：

```powershell
python -m research.forward_observation --store "out/forward_macro_research_001" --ingest "<実際のjoined_macro_event.json>"
```

新しい`record_sha256`（**元RSS記事と異なる派生イベントSHA**）を使い、分析AIと検証AIの研究可否を確認：

```powershell
python -m research.forward_macro_two_model_gate --store "out/forward_macro_research_001" --event-sha256 "<派生イベントのrecord_sha256>" --ledger "out/ai_macro_event_001.json" --analyst-model "<利用可能な分析モデル>" --reviewer-model "<それとは異なる検証モデル>"
```

**有料APIは自動実行しない。** 本人が課金と最大呼び出し数を別途明示承認した場合にのみ、上記の最後に`--max-api-calls 2 --allow-external-api`を加える。必ず現在のAPI料金、API利用権、月間3,000円の研究予算（Q100）、既存台帳の`pending_request`を確認。安全と予算が不明なときは実行禁止。

モデル結果が両方揃っても、ジャーナルへの書込みは別の明示的な`--publish-offline`であり、成功後に初めて**その時刻以降**の価格を観測して評価する。既存114CSVを使って、存在しなかった過去の予測を再現したことにしない。

## 未完了の実務前提と安全ゲート

- 経済カレンダーBLS以外の全重要指標・日銀/ECB・為替ニュース、実際の市場コンセンサスの入手権・タイムスタンプ原証拠、真正性、口座時計認証は別途。
- 新規の本番AIモデル承認、モデル比較の品質合格基準、API費用の円換算、信頼可能なフォワード成果、楽天MT4発注・デモ発注は含まない。
- **時刻窓の検査は研究用のアラートであり、既存の本番/デモ取引停止ロジックを改変したものではない。**
- 既存の0.5%/1%/1.5%/DD4〜5%等の安全条件を一切変更せず、常に`NO_GO`、`safety_hold_latched=true`、`real_orders_permitted=false`、`demo_orders_permitted=false`。
