# FWD-1361〜1400：MT4デモ非発注フォワード観測パイロット

## この段階で実行可能にしたこと
これまでの研究用バッチ監査を、既存の単一楽天MT4デモ口座と既存の30周期・60秒読み取り専用観測EAへつなぐ。**端末側操作は利用者が明示的に実行**し、Python/PowerShellはMT4を起動しない・MQL4を配備しない・自動売買を有効にしない。実機での注文停止・口座種類の独立認証は行わない。デモ/実注文は引き続き禁止。

### 実装
- `research.forward_demo_pilot` の `--mode prepare` はリポジトリ固定の `research/mt4_readonly/FxForwardDemoTimerObserver.mq4` のSHA256、MQL4禁止API、3ペア、60秒/30周期上限を静的検証。MetaEditorやMT4は開かない。
- `--mode audit --session LABEL=COPIED_CSV_FOLDER` は**明示された端末外コピー**の3ペアCSVだけを既存 `forward_evidence_runbook` → `forward_fullstack_noorder_hub` に渡し、CSV/UTC、欠落ペア、停止証拠、NY17時間バケット、マクロ証拠・ブラックアウト窓、各種安全保留を一括監査する。セッションラベルは一意にする。
- 新規ファイルだけ作成する `--out` を追加。原本CSV、既存runbook、MQL4ソース、MetaEditor出力を変更しない。`--out` が指定されなければ画面出力のみ。
- `--plan-file` があれば以前のBLS/予想/地域原本履歴/MT4観測/価格AI研究を含むプランをそのまま監査できる。その場合 `--session` との二重指定を禁止。プランのsessionsが0ならauditは拒否。
- 既存手作業を減らすため `scripts/forward_demo_pilot_once.ps1` を追加。準備/監査ともに一度のコマンドでNO_GO研究レポートを保存する。PowerShellの実行ポリシー変更やタスクスケジューラーの登録はしない。
- 試験が緑でも `operator_manual_gate_statuses[*].verified_by_this_program=false` を維持。デモ/実注文経路には一切つなげない。

## 初回の一括準備（実機を操作しない）
GitHubの変更をマージしたあと、Windowsの新しい別worktreeで実行する。元 `C:\Users\Suzuki\Documents\ChatGPT\Fx` の変更をstash/reset/上書きしない。現在のworktreeでなくクリーンな別worktreeの最新mainを使用する。

```powershell
New-Item -ItemType Directory -Force out | Out-Null
.\scripts\forward_demo_pilot_once.ps1 -Mode prepare -OutputDirectory out
```

出力の `observer_static_preflight_passed=true`、`observer_maximum_timer_cycles_declared=30`、`runtime_go_no_go=NO_GO` とMQL4原本SHAを確認する。ここまでならMT4/ネットワーク操作はゼロ。

## 実機で初めて必要になる作業（本人の目視・明示操作）
1. **同じ一台の楽天MT4デモ端末のみ**を使う。別デモ/別ターミナル同時ログインはしない。楽天口座種別DEMO、正常通信、AutoTrading OFF、DLL/外部通信許可OFF、保有建玉と未約定注文の有無、MACD Sampleなど既存EAによる意図しない動作がないことを本人が確認。不明点があれば観測器を実行しない。
2. MT4の「ファイル→データフォルダを開く」で、実際の `MQL4\Experts` を確認。`research/mt4_readonly/FxForwardDemoTimerObserver.mq4` の**レビュー済み同一SHA**のコピーを、本人が必要と判断したときだけそこへ手動配置する。同名ファイルが存在すれば勝手に上書きしない。
3. MetaEditorで手動F7コンパイルし、**0 errors**を確認。警告も説明できなければ利用を保留。EA/EX4の正体、取引API呼出しなし、既存チャートEAの状態を本人が確認する。source静的合格はコンパイル/安全性の代替ではない。
4. MT4のUSDJPYチャート**1枚だけ**へ読み取り専用EAを本人が手動でアタッチ。AutoTradingはOFFのまま。初回は目視監視で数周期を観測し、重大な異常があればEAを外す。タイマーは60秒、**最大30周期で停止**する設計だが、実機で実際に止まったという証明にはならない。
5. EAを手動で外し、`MQL4\Files` に生成された `FxFwdV3_USDJPY_*.csv`・`FxFwdV3_EURJPY_*.csv`・`FxFwdV3_EURUSD_*.csv` のうち、その観測セッションでできたCSVだけを**端末外**の専用フォルダーにコピーする。ファイル名を変更しない。Expertログ・コンパイルログも別に保存できる場合は保存。別セッションのファイルを同じフォルダーに混ぜない。

## 一括監査（端末を操作しない）
CSVコピー先を `C:\path\to\copied_session1` としたときのコマンド（パスは実際のものに置換）：

```powershell
.\scripts\forward_demo_pilot_once.ps1 -Mode audit -Session @('s1=C:\path\to\copied_session1') -OutputDirectory out
```

2回目以降の別セッションをまとめるなら：

```powershell
.\scripts\forward_demo_pilot_once.ps1 -Mode audit -Session @('s1=C:\path\to\copied_session1','s2=C:\path\to\copied_session2') -OutputDirectory out
```

以前の正式runbookの証拠プランにセッションが入っていれば、代わりに `-PlanFile 'out\real_forward_plan.json'` だけ指定する。この場合BLSの元原本や発表前コンセンサスの保存データがあれば、一緒に検証する。なければ未取得としてNO_GO保留を返す。

## 出力と判定の読み方
- `MT4_READONLY_PILOT_PREPARATION_NEEDS_OPERATOR_ACTION_NO_GO`：プログラムは固定MQL4ソースの静的検査を通過。人間のデモ口座・コンパイル・非発注・設置確認は未実施。
- `MT4_COPIED_FORWARD_OBSERVATIONS_AUDITED_HOLD_NO_GO`：端末外にコピーされたCSVの構造を監査。報告する価格・時間・停止は証拠ファイル内の自己申告であり、実ブローカーの独立認証ではない。
- `MT4_READONLY_PILOT_FAIL_CLOSED_NO_GO`：ソース、セッション、CSV、履歴、計画、または出力先に不備。出力を上書きせず取引禁止を維持。
- `observer_source_sha256_local_integrity_only` は元MQL4レビューの目印。`operator_manual_gate_statuses` は全て未認証であり、勝手に true に昇格しない。
- `pending_holds_preview` と `prioritized_research_actions_advisory_only` は次の収集・研究タスクであり、実売買・デモ注文の許可ではない。

## 本当に残る停止条件
このプログラムはローカルWindowsや楽天MT4を**この会話から操作していない**。MetaEditor本物のコンパイル、端末へのEA配置/実行、CSVの取得、口座・注文状態の確認、サーバー時計の独立照合、通信60秒/600秒の実機遮断、日次/DD停止、AIによる実指標予想の発表前保存、メール/スマホ通知、実デモ注文の許可条件は未実証。

本工程で到達可能なのは **「本人管理下のデモMT4における非発注フォワード観測＋研究用一括検証」の実行準備**まで。実注文を伴うデモフォワードテストではない。建玉ゼロ・自動売買OFFを維持。

**安全不変**：`runtime_go_no_go=NO_GO`、`safety_hold_latched=true`、`demo_orders_permitted=false`、`real_orders_permitted=false`。GitHub mainのマージは本人承認のみ。