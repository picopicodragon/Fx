# FWD-141〜170：マクロ情報・二段階AI・MT4実測価格の研究統合

## 現状と評価可能な範囲

利用者の楽天MT4単一DEMO端末から、USD/JPY・EUR/JPY・EUR/USDで2セッション計114 CSV、38完全観測周期（欠損0）が取得・統合監査済み。スプレッド実測は各0.5/1.0/0.5pips（38回の観測期間内）。ユーザーは `FXFWD_OBSERVER: 30-cycle safety cap reached; timer stopped.` がMT4 Expertsに存在すると確認済みだが、ログの原本照合/独立口座・時計認証は未実施。

**既存機能を再利用する**：`research.forward_rss`（BLS雇用・CPI、FRB政策RSSを明示opt-inで取得）、`research.forward_bls_calendar`（明示opt-inの公式BLS iCalendar）、`research.forward_observation`（ローカルハッシュ連鎖ジャーナル）、`research.forward_ai_shadow`（明示した最大2回の課金済みOpenAI Responses分析AI＋別モデル検証AI、API呼び出し前の台帳書込みと不確実結果の再送禁止）、`research.ai_provider_comparison`（Responses/Jev/Decisionsの補助判断比較）、`research.forward_shadow_causal_replay`（当時提出された仮説からスナップショット評価）。

今回追加したコードは**既存の外部アクセスやAI呼び出しを勝手に開始しない**。ブローカーへの注文経路は設けず、既存の`NO_GO`のままオフラインで統合評価する。

## FWD-141〜149：経済指標の「市場予想差」の根拠付き検査

`research/forward_macro_consensus_surprise.py`。

- イベントID・対象ペア（3ペアのみ）・CPI/GDP/PMI/雇用/政策金利など・同一の数値単位・予定時刻を記録する。
- **予想値**は独立したテキスト抜粋のSHA-256、HTTPS出典リンク、公開時刻、収集時刻を要求。**発表予定前に取得した予想値のみ**受け入れる。
- **実績値**も別のテキスト抜粋/SHA-256と公開・取得時刻を要求。予定時刻より前に入手したと主張する実績値は拒否。
- 両方揃った時だけDecimalで`実績−予想`を算出。予想値が無い場合は`NO_POINT_IN_TIME_CONSENSUS`、発表値が無い場合は`OFFICIAL_RELEASE_VALUE_NOT_RECORDED`として比較しない。
- 報道が見つかっただけで事前の市場コンセンサスを捏造しない。ハッシュは**与えられた抜粋との一致**だけを検査し、発行元の真正性を独立に証明しない。正負符号から通貨高/安や発注方向を導出しない。
- 発表15分前〜15分後の研究注意を付加。重要度の確定やEA停止許可ではない。

入力JSONは`schema: fx_fwd_macro_release_surprise_v1`、`event_id`、`pair`、`event_type`、`unit`、`scheduled_at_utc`、`forecast`、`release`。両方の記録には`value`、`source_text`、`source_sha256`、`source_url`、`published_at_utc`、`captured_at_utc`が必要。`forecast`/`release`は未入手時nullにする。

## FWD-150〜160：観測データとマクロ判断履歴の厳密な突合

`research/forward_macro_evidence_readiness.py`。

- 既存FWD-104複数セッション監査（3ペア完全周期、異セッション重複/リプレイ、SHA-256等）を再利用。
- ローカル`forward_observation`ジャーナルを読み込む際は全記録の**連鎖ハッシュ・時刻・元イベント→仮説→レビューのリンク**を再検査する。
- イベント・仮説・レビューの件数、同一ペア紐付け、未記録の市場予想と結果、候補方向・出典発表/収集時刻・二段階識別子の違いを集計。
- `APPROVED`はあくまで**自己申告されたモデルレビュー状態**であり、AIレビュー独立性/出版物の真正性を認定しない。モデルIDが同一、レビュー重複、ジャーナル時刻の未来値は安全側に扱う。
- 任意で既存の`forward_ai_shadow`研究台帳を読み、元イベントのハッシュと入力ハッシュを照合。課金APIの`pending_request`が残っていれば`AMBIGUOUS_API_REQUEST_MANUAL_RECONCILIATION`。自動再試行しない。
- `--store`省略も許可。実測CSV114件だけの段階では**マクロイベント0、候補0**、課金0で安全に報告。これは既存114件から存在しない経済ニュースを推定しないための仕様。

## FWD-161〜170：独立レビューと実測価格の事後比較

`research/forward_macro_reviewed_outcomes.py`。

- 観測ジャーナルにリンクした`APPROVED`かつLONG/SHORTの研究候補のみ対象。ジャーナル原本なしやPENDING/HOLDなら結果0件。
- レビューの記録時刻より**厳密に後**の最大120秒以内の最初の3ペア完全観測に限定する。結果の比較は**同一セッションの次の観測1回**。75秒超の周期欠落があれば採点しない。
- 既知イベントの自己申告公表時刻±15分以内の仮想エントリーを除外。**経済カレンダー全件のブラックアウト認定にはならない**ので保留を残す。
- LONGはAsk→次のBid、SHORTはBid→次のAskでスプレッド込みの価格変化（1通貨単位当たりpips）を算出する。売買損益や実行可能な約定を主張しない。数量・ロット・手数料・DD・真のスリッページを評価するには別途研究用シナリオとFWD-140リスク審査が必要。
- 重複セッション、データ欠損、時間窓の衝突、EUR/USD換算不整合、同一モデルIDのレビュー、複数レビューは採点しない。
- 研究上の正/負/ゼロ件数を記録するが、見かけの勝率から実績・将来の収益性を断定しない。マクロAIの因果判断を事後評価する最初の集計基盤。

## Windows：一括実行して現在の進捗を判定する

PR #264がユーザーによってmainにマージされた後、既存Windowsで以下のコマンドを実施。MT4の起動・EA再設定は不要。

```powershell
cd C:\Users\Suzuki\Documents\ChatGPT\Fx
git switch main
git pull --ff-only origin main
```

実測114件との突合：**マクロジャーナルがまだ無い場合も実行可能**。

```powershell
$asof = [DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ"); python -m research.forward_macro_evidence_readiness --session "s001=out/mt4_timer_clean_001" --session "s002=out/mt4_timer_clean_002" --asof-utc $asof --out "out/macro_readiness_$(Get-Date -Format yyyyMMdd_HHmmss).json"
```

シャドー評価の空結果を確認：

```powershell
$asof = [DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ"); python -m research.forward_macro_reviewed_outcomes --session "s001=out/mt4_timer_clean_001" --session "s002=out/mt4_timer_clean_002" --asof-utc $asof --out "out/macro_outcomes_$(Get-Date -Format yyyyMMdd_HHmmss).json"
```

既存の実際のマクロ観測ジャーナルがある場合のみ`--store "out/<journal_dir>"`を双方に追加。生ファイルを変更せずにリンクが検査される。レビューの処理が独立に完了したことはAPI台帳だけで証明できないため、時刻付き観測ジャーナルも使用する。

### 実際のマクロ情報・AI判断を蓄積するには

既存のローカルジャーナル初期化：

```powershell
python -m research.forward_observation --store "out/forward_macro_research_001" --init --session "macro_research_001"
```

既存の公式発表フィードを**任意の明示操作でのみ**収集。最新のデータを必要とするときだけ実行。取得内容は公的サイト由来の自己申告RSSエントリーであり、実在の市場事前予想までは含まない。

```powershell
python -m research.forward_rss --store "out/forward_macro_research_001" --feed bls_cpi --allow-network --max-new 3
```

`--feed bls_empsit`・`--feed fed_policy`も使用可能。楽天MT4へ直接アクセスしない。APIキー・個人情報・著作権対象の長文をGitHubにアップロードしない。

イベントハッシュがジャーナル内に保存され、研究APIの利用予算を別途容認する場合に限り、既存の**課金API明示オプトイン**コマンドを利用する：

```powershell
python -m research.forward_ai_shadow --store "out/forward_macro_research_001" --event-sha256 "<実際に記録された64桁ハッシュ>" --ledger "out/macro_ai_event_001.json" --analyst-model "<利用可能な主分析モデル>" --reviewer-model "<異なる利用可能な検証モデル>" --max-api-calls 2 --allow-external-api
```

`<...>`は**文字どおり入力せず**本人が現実のハッシュ/モデルを明示したときだけ使用。無料の事前チェックや本PRのCLIには上記のフラグを付けない。コスト・推論モデルの利用可否は別確認。モデル間の識別子を分けても真正の独立性や確証を意味しない。通信切断後の課金要求は自動再試行せず、台帳の`pending_request`を確認してから手動照合する。

マクロ仮説の意味づけは予想差・政策因果・市場の織り込み・反証を総合判断する**A+方式**を維持。単一の予想差で自動発注しない。

### 実測価格との時刻に関する重要制約

今回の実測114ファイルは既に観測済みで、取得時刻より後に作成した仮説を過去に移して「事前予測」と称することは**厳禁**。新しい真のマクロ判断の事後検証は、**判断をジャーナルに保存した後**の観測値が必要。現在の既存CSVに該当時刻が無ければ0件が正常。30周期制限は継続し、自動再起動は認めない。

### 安全・受入条件

- マクロ入手元の独立認証、コンセンサスの事前入手時刻、ブローカー時刻/口座、EA停止ログ原本、全経済イベントカレンダーはまだ実務上の課題として記録。
- 総資金10万円、単独リスク0.5%、合計1%、日次1.5%、DD4%新規停止、DD5%人間承認等を**変更しない**。このPRはリスク実装や発注経路には手を触れない。
- 発注禁止`NO_GO`、`safety_hold_latched=true`、`real_orders_permitted=false`を固定。デモ口座の実発注も禁止。CI成功は本番運用/収益性の認証ではない。

## FWD-171〜182：マクロAI研究キャンペーン統合ボード

追加された`research.forward_macro_campaign_board`は、価格品質統計、観測時間帯、マクロイベント/AI研究ジャーナル、独立レビュー、レビュー後の2スナップショット比較を**一度のオフライン検査で集約**。予想差のための正当な出典を確認したりAIに判断させたりする前に、何が不足しているかを順序付きで表示する。

**PR #264がmainに取り込まれた後、現有114 CSVから追加操作なしで実行できる最優先の一行：**

```powershell
$asof = [DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ"); python -m research.forward_macro_campaign_board --session "s001=out/mt4_timer_clean_001" --session "s002=out/mt4_timer_clean_002" --asof-utc $asof --out "out/fwd_macro_campaign_$(Get-Date -Format yyyyMMdd_HHmmss).json"
```

現段階でマクロジャーナルが無いなら、期待される**構造上の**指標は`files=114`、`complete_cycles=38`、`macro_events=0`、`reviewed_candidates=0`、`descriptive_marks=0`、`API_calls_this_run=0`。実データの確認結果そのものは本人のWindowsで実行されるまで未確定。

ジャーナルが存在すれば`--store "<実際の保存ディレクトリ>"`を追記し、既存AI課金台帳を検査する場合は`--ai-ledger "<実際の台帳.json>"`を追加する。課金リクエストの`pending_request`がある場合は必ず人間による課金/レスポンス照合待ち。**コマンド自体はネットワーク・OpenAI API・Jev・Decisions API・MT4を呼ばない**。

出力の`maximum_two_model_api_calls_if_all_new_events_chosen`は**上限2呼び出し/イベントという仕様からの事前参考件数**に過ぎず、必要費用の金額を推測していない。過去台帳外の課金履歴がないとは断定できない。モデルコストは利用サービスの実料金を確認する。すべての`next_research_actions`は作業候補であり売買承認ではない。

現有38周期だけで未実測の時間帯を補完したり、過去の真のマクロ仮説を捏造しない。既存30周期EAの自動再起動、別MT4口座、同時ログイン、取引許可は一切追加しない。
