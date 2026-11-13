# FWD-1441〜1460：実マクロ根拠によるフォワード研究の更新（非発注）

## 目的と限界

FWD-1401 の shadow_forward_20261113 は2セッション90CSV/30周期で**価格観測の初期開始**に成功済み。ただし現在 registered_macro_events=0、registered_review_count=0、AI_hypotheses_generated_this_cycle=0 であり、実AI判断を伴うフォワード評価は未開始。

新規 --mode refresh は、**実マクロイベントや独立レビューが観測ジャーナルに新規追加されたときだけ**、既存価格セッションを変更せず、過去のCSV原本SHAをすべて再照合し、研究履歴を追記する。--mode step は従来どおり新たな価格セッション追加専用。

refresh は**研究用証拠の取り込み記録**であり、AIを呼び出さず、各ペアは NO_SIGNAL のまま、発注しない。AIモデルを実際に呼び出す経路は独立して存在する research.forward_macro_two_model_gate / research.forward_ai_shadow の**明示した課金上限・オプトインのみ**であり、自動実行しない。

## Windows操作（PRブランチまたはマージ後の対応版で実行）

今回すでに開始した状態フォルダーをそのまま使う。二度目の start を実行しない。

### 1. 研究マクロ・ジャーナルの初期化（まだ未作成の場合）

~~~powershell
$root = "$env:USERPROFILE\Documents\FXForwardEvidence"
$state = Join-Path $root "shadow_forward_20261113"
$store = Join-Path $root "macro_forward_journal"
python -m research.forward_observation --store $store --init --session fxmacro20261113
~~~

既存ジャーナルがある場合、--init は拒否するので再初期化しない。

### 2. 実際に取得した原本を先に保存し、その根拠と時刻を検証する

BLS、ECB、Eurostat、日銀、総務省等の対象イベントについて、公表前の予想は**発表前に収集した証拠のみ**を保存する。BLSの変更済み日程や後から得た予想値を、事前に知っていた情報として遡及登録しない。原本時刻、取得時刻、URL、原本SHAを保存する。対象通貨は USD/EUR/JPY。

既存 research.forward_macro_pre_release_capture、research.forward_macro_evidence_handoff 等で原本の局所整合性を検証し、**本当に作成された** MACRO_EVENT スナップショットファイルができたら本人が明示的に追記する。

~~~powershell
python -m research.forward_observation --store $store --ingest "C:\実際の場所\verified_macro_snapshot.json"
~~~

この MACRO_EVENT は提出者記述の出典であり、ネットワーク・公表時刻が独立に認証されたものではない。スナップショットがまだ無い場合は**この操作を飛ばし、架空のサンプルや古い予想を作らない**。

### 3. 保存済み2セッションとマクロ・ジャーナルを含む計画ファイルを作成する

fx_fwd_evidence_runbook_v1 のすべての必須フィールドを維持する。下記は一例（保存先が既に存在するときは上書きせず、新しいファイル名にする）。

~~~powershell
$planPath = Join-Path $root "shadow_macro_plan_20261113.json"
$plan = @{
  schema = "fx_fwd_evidence_runbook_v1"
  bls_snapshot_dir = $null
  official_news_bundle = $null
  external_macro_file = $null
  forecast_archives = @()
  sessions = @(
    @{ label = "s1"; directory = (Join-Path $root "session_20261113_01"); experts_log = $null; compile_log = $null }
    @{ label = "s2"; directory = (Join-Path $root "session_20261113_02"); experts_log = (Join-Path $root "session_20261113_02_logs\experts_20261113_02.txt"); compile_log = (Join-Path $root "session_20261113_02_logs\compile_20261113_02.txt") }
  )
  observation_store = $store
  ai_ledgers = @()
  regional_source_manifest = $null
  mt4_observer_source = $null
  regional_history_file = $null
}
if (Test-Path -LiteralPath $planPath) { throw "既存の計画ファイルは上書き禁止" }
$plan | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $planPath -Encoding UTF8
~~~

本例の s2 ログはユーザーがすでに保存したものを指定している。該当ログが存在しない場合は null にする。ログの未提出は安全保留に残る。

### 4. **イベントが1件以上本当に追記された後**に、マクロのみ更新

~~~powershell
.\scripts\forward_shadow_start_once.ps1 -Mode refresh -StateDirectory $state -PlanFile $planPath
~~~

期待状態は SHADOW_FORWARD_MACRO_EVIDENCE_REFRESHED_HOLD_NO_GO と new_session_count=0、registered_macro_events が1以上。追加されたイベント・レビューがなければ**失敗停止**し、状態の連番記録を増やさない。古いセッションの一部でも内容・SHAが変化している場合も停止する。今回の時点ではユーザーはマクロイベントを未登録なので、**すぐには実行しない**。

### 5. AIモデル二段階分析を実際に行う条件

ジャーナルへ記録できた実マクロイベントの record_sha256 を --event-sha256 に指定し、現実の公開証拠と発表前予想（ない場合は欠損扱い）を独立に確認する。

~~~powershell
$eventSha = "ジャーナルが出力した実際の64桁のrecord_sha256"
$ledgerDir = Join-Path $root "shadow_macro_ai_ledgers"
New-Item -ItemType Directory -Path $ledgerDir -Force | Out-Null
$ledger = Join-Path $ledgerDir ("event_" + $eventSha + ".json")

# 完全オフライン・API課金0の事前検査。利用モデル名は利用可能なものを明示する。
python -m research.forward_macro_two_model_gate --store $store --event-sha256 $eventSha --ledger $ledger --analyst-model "<実際の分析モデル>" --reviewer-model "<実際の独立検証モデル>"
~~~

分析・レビューの有償API呼出しは上記とは別の明示オプトインと呼出し数上限が必要。実際のモデル、APIキー、費用、APIの適用範囲が確認できるまで勝手に実行・課金しない。pending_request（課金済みか不明）があれば自動再送は禁止。完了した研究だけを --publish-offline で既存ジャーナルに公開した後、新しい計画ファイルの ai_ledgers に実在する台帳を指定して再度 refresh する。

## 安全と認証の境界

- いずれの新機能も実際のMT4端末操作、トレード、注文、ポジション作成、価格取得、AI課金、HTTPアクセスは**ゼロ**。
- 対象はユーザーのローカルCSV、任意のログ、提出済みマクロジャーナル。出典URLやファイルSHAだけでは経済イベントの真偽・正しい事前予想時刻は独立には証明されない。
- refresh はマクロイベント数または独立レビュー数が**単調に増加**したときのみ追記。過去レコードの書換え・リプレイ・注文許可は不可。
- マクロイベントが追加されても、安全のため各通貨ペアに NO_SIGNAL のまま。価格・マクロの原本と独立AIレビューを実際に整え、別途既存研究レポートで事後評価が必要。
- 出力は NO_GO、安全ラッチ維持、デモ・本番発注禁止。自動売買フォワードへの切替承認ではない。
