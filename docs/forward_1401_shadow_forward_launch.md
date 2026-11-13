# FWD-1401：実観測CSVから非発注シャドーフォワードを開始する

## 今回の到達点
これまでのFWD-1361の単発CSV監査から、**複数日にわたる実データ観測を積み上げるシャドー研究キャンペーン**を開始する仕組みに接続する。`start`で実際に保存済みの3ペアCSVを初期基準として登録し、`step`で**新規の明示された観測セッションだけ**を追加。各回で以前のCSVのSHA256を含む全データを再評価し、実体の異なる新規ファイルのみを受理。`status`は既存の履歴を閲覧（原本の再検証はしないと明示）。

**本機能の開始は「価格に基づく非発注シャドーフォワード観測キャンペーン開始」であって「実AIによる自動売買判断開始」ではない。** マクロ根拠、独立レビューレポートや発表前予想が不足している場合、USD/JPY・EUR/JPY・EUR/USDについて`NO_SIGNAL`を出力する。この状態はAIのHOLD判断ではなく、安全上の無信号である。架空の売買、仮想約定、仮想損益、API呼出しは一切生成しない。

### Windowsでの開始（すでに取得済みのセッションを使う）
新機能を含むPRブランチの別worktreeで実行する。古い `Fx-FWD-PILOT-20261113` ワークツリーをリセット、stash、強制checkoutしない。`s1` は6周期、`s2` は24周期のCSV専用フォルダーであり、ログを混ぜない。観測日時から24時間以内なら「新しいデータあり」、それより古ければ「履歴の初期登録のみ」と明確に区別する。

```powershell
$root = "$env:USERPROFILE\Documents\FXForwardEvidence"
$s1 = Join-Path $root 'session_20261113_01'
$s2 = Join-Path $root 'session_20261113_02'
$state = Join-Path $root 'shadow_forward_20261113'
.\scripts\forward_shadow_start_once.ps1 -Mode start -StateDirectory $state -Session @("s1=$s1", "s2=$s2")
```

出力例の `SHADOW_FORWARD_STARTED_DATA_ONLY_HOLD_NO_GO` は、**24時間以内の保存観測データを認識してキャンペーンを開始**したことを示す。`SHADOW_FORWARD_BASELINE_ONLY_HOLD_NO_GO` は保存CSVが古くなったときの**既存履歴登録**だけを示す。どちらもAI推論/デモ注文/実注文は行っていない。

### 新しい観測セッションを追加する
既存の単一デモMT4/読み取り専用60秒タイマーEAを**人間の監視下**で用いて、別セッションの新しいCSVを端末外 `session_202611XX_03` のような空のフォルダーにコピーする。最初の `s1` と `s2` は再指定不要。別の同期端末・デモ口座を立ち上げる必要はない。

```powershell
$s3 = Join-Path $root 'session_202611XX_03' # 実際のフォルダー名に置換
.\scripts\forward_shadow_start_once.ps1 -Mode step -StateDirectory $state -Session "s3=$s3"
```

`step`では過去のレコードを上書きせず `00000002.json` を追加する。元のCSVを消す/変更する、同じセッションを再送信する、異なる観測セッションを混ぜる、過去に巻き戻った時刻を指定するなどは `SHADOW_FORWARD_FAIL_CLOSED_NO_GO`。エラー時は古い履歴をそのまま残す。

```powershell
.\scripts\forward_shadow_start_once.ps1 -Mode status -StateDirectory $state
```

### 実マクロイベントと2モデルAIの接続方法
- 価格だけでは金融政策や経済指標の織り込みを評価できない。BLS/EU/JPの一次原本と発表前コンセンサスを、実際に公開された時刻・ユーザーの取得時刻とともに原本保存する。
- 既存の `forward_regional_original_bundle`、`forward_regional_history_register`、`forward_evidence_runbook` で原本と予定をオフラインで照合し、発表前15分の予想欠損や予定改訂がないか確認する。未保存なら欠損であり、自動補完しない。
- 発表後の実値を保存して `forward_macro_evidence_handoff` で原本・予想と紐づけ、`forward_observation` の既存のappend-onlyジャーナルへ本人が明示的に登録する。
- 実イベントSHAと既存の有償API台帳を用い、`forward_macro_two_model_gate` → `forward_ai_shadow` の**明示承認つき/課金上限つき**2モデル研究を実施。`pending_request`が残る場合は同一のAPI呼び出しを自動再送しない。AI判断は独立レビュー後に記録する。
- 上記原本、ジャーナル、AI台帳とMT4コピー済みCSVを含む `fx_fwd_evidence_runbook_v1` のプランを準備したときは、`--plan-file` で `start` または `step` を実行できる。これは既存の完全なプランを**読み取るだけ**。AIが出した非HOLD判断や実リスク値を自動発注したり、真のコンセンサスとして証明することはない。
- `forward_macro_reviewed_outcomes` の実際の時間順レビュー後2スナップショット評価、`forward_shadow_causal_replay` の仮想リスク研究などの既存機能で後続評価できるが、必ず別途実証済みデータと明示設定が必要である。

### 明確に保持する禁止事項と限界
- 本モジュールには、価格の自動取得/MT4へのEA配置/MetaEditorコンパイル/リアルタイムの無人ポーリング/スケジューラー登録/HTTP/BLS自動巡回/AI API呼出し/注文が**ない**。既存のAIモデルを勝手に使って有償呼出しもしない。
- 一度保存したCSVが本当にブローカーで観測されたか、PC時刻が独立認証されたかは、ローカルハッシュからはわからない。`source_real_broker_provenance_attested=false`。
- 旧歴史が24時間を超える場合、`start`してもその事実を `new_observation_within_24h=false` と明示し、最新のライブ観測だと主張しない。数値が一致しても再提出は拒否。
- 当該データだけで100,000円の資金、0.5%単発損失、合算1%、日次1.5%、DD5%の実注文管理の動作が証明されるわけではない。現行のバックテストには本物の実行約定や証券会社保証はない。
- mainへの最終マージは人間承認のみ。暗黙のデモ売買テスト昇格禁止。

固定の出力は `runtime_go_no_go=NO_GO`、`safety_hold_latched=true`、`demo_orders_permitted=false`、`real_orders_permitted=false`、注文0、API0、ネットワーク0。実AIシャドー判断を含む完整なフォワード評価には実マクロ情報と明示API呼出しがまだ必要。