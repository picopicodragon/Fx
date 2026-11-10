# FWD-085〜094: 楽天MT4デモ観測の証拠保全・停止判定・障害監査

## 状況と目的（2026-11-10）

利用者が既存の単一楽天MT4 DEMOターミナルにて、読み取り専用タイマーEAのCSVを取得。合計24件、8つの完結した3ペア観測周期、不完全周期0件。FWD-084の数値比較修正後に円換算の誤警告も消えた。ここまで成功したのは**8周期のファイル整合性**であり、最大30周期での実機停止、コンパイルの0警告、長時間通信断後の動作、MT4/ブローカーの独立認証ではない。

## 一括実装
- **FWD-085〜086：** 監査済み3ペアCSVごとのSHA-256とサイズ・元のファイル名を固定順に列挙した証拠マニフェストを生成。データを加工、訂正、コピー、削除しない。
- **FWD-087：** オプションのExpertsログ（UTF-8のテキストコピー）から、開始・3ファイル生成・最大30周期停止・正常撤去・口座/接続停止・価格陳腐化・CSV書込失敗をそれぞれ分類。
- **FWD-088：** 30周期CSVがあっても停止ログが無ければ「未確認」。停止ログがあっても30周期に達しないときは矛盾として記録。ログは自己申告ファイルなので**独立した実行証明にはならない**。
- **FWD-089：** オプションのMetaEditorコンパイル結果テキストから`0 errors, 0 warnings`を検出。ただしコピーできた表示だけで、現在のEX4の出所や実稼働バイナリを認証するものではない。
- **FWD-090：** 異常・欠損・周期逸脱・ログ異常・無停止ログを`observed_issues_and_safety_holds`に集約。タイマーEAの自己復旧・常駐化・発注許可は行わない。
- **FWD-091〜094：** 元のFWD-084監査結果と統合したJSON監査、原本保持・1行PowerShell実行手順・障害検出回帰テスト。

## Windows側の具体的な一括手順

**PR #260がmainにマージされたあと**、Windowsでソースを更新する（このPRはMT4 .mq4/.ex4を変更しないので再コンパイル不要）。

```powershell
cd C:\Users\Suzuki\Documents\ChatGPT\Fx
git switch main
git pull --ff-only origin main
```

### 現在の既存8周期24ファイルを即座に保全・監査

過去のファイルは`out/mt4_timer_session_001`に保全されたままにする。初回はログ指定を省略し、**この1行だけ**を実行：

```powershell
$asof = [DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ"); python -m research.forward_mt4_observation_evidence --directory "out/mt4_timer_session_001" --asof-utc $asof --out "out/mt4_evidence_8cycle_$(Get-Date -Format yyyyMMdd_HHmmss).json"
```

期待値：`csv_manifest_count=24`、`capture_audit.complete_cycle_count=8`、`incomplete_cycle_count=0`。未提出ログや`THIRTY_CYCLE_STOP_NOT_YET_OBSERVED`などは残り、成功したことにして消去しない。

### 次の独立した30周期・停止ログの試験

初回8周期が保全済みで、デモ口座、単一既存ターミナル、USDJPYの一つのチャートだけ、既存EAとの競合なし、MetaEditor **0 errors, 0 warnings**、発注無効、AutoTrading OFFのすべてを確認できた場合に限る。

- 現行EAは60秒周期、最大30回のOnTimerでCSV出力を試み、次のタイマー呼出時に`FXFWD_OBSERVER: 30-cycle safety cap reached; timer stopped.`をログに記録する。**30回のタイマー呼出時点では停止メッセージは出ない。** その後の停止呼出（31回目相当）を観測する必要がある。
- 利用者が監視できる時間だけデモで実施し、別の新しいセッション専用フォルダー（例`out/mt4_timer_session_002`）に、セッション開始後の3ペアCSVのみを手動コピー。旧セッションのCSVとは混ぜない。
- MT4「ターミナル→エキスパート」の出力から、このEAの観測セッションに関わる行だけをUTF-8テキストとして別名保存（例`out/mt4_timer_session_002_experts.txt`）。口座ID等の秘密情報が含まれていれば共有時に注意し、**監査対象のCSVは改変しない**。
- MetaEditorの実際の表示を別のUTF-8テキストファイルに記録（例`out/mt4_timer_session_002_compile.txt`）。自己申告であることを維持。

停止後、生成CSVのタイムスタンプを確認し、EAをチャートから手動で取り外す。ターミナルの自動売買はOFFのままにする。読み取り専用CSV監査を次の**1行**で実行：

```powershell
$asof = [DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ"); python -m research.forward_mt4_observation_evidence --directory "out/mt4_timer_session_002" --asof-utc $asof --experts-log "out/mt4_timer_session_002_experts.txt" --compile-log "out/mt4_timer_session_002_compile.txt" --out "out/mt4_evidence_30cycle_$(Get-Date -Format yyyyMMdd_HHmmss).json"
```

ログ/コンパイル証拠はオプションであり、実際に存在しないファイルのパスを指定しない。数値の整合性とログが揃っても、第三者の独立認証ではない。**原本CSVとログは保全し、Gitへコミットしない。**

## 注意点と停止条件

- コンパイル警告がある、口座がデモと確認できない、AutoTradingがON、既存EA/注文が予期せず動作、通信断や端末異常、ファイル消失・書込み失敗がある場合は、実行試験を開始しない、またはEAを停止し、原因を記録する。
- 本PRではMQL4の常駐化や自動再起動をしない。既存EAの30周期停止を勝手に解除しない。
- 30周期すべてを生成するには、通常、30分前後と次の停止呼出が必要となる。営業日中も価格配信やMT4状態によって欠損・短縮がある。30周期試験の完全性は今回のPythonソースだけでは証明できない。
- Python CLIの出力先は**CSV証拠フォルダーの外**で既存ファイルのない名前を指定する。

## 自動売買・安全条件

`runtime_go_no_go=NO_GO`、`safety_hold_latched=true`、`real_orders_permitted=false`、`demo_orders_permitted=false`。通貨ペアはUSD/JPY、EUR/JPY、EUR/USDのみ。既存のG1〜G9、FX-SAF、契約属性3×5=15、独立ブローカー時刻・口座真正性・長時間運用承認はまだ満たしていない。GitHub側のCIテストはMetaEditor実機コンパイルでもMT4端末運用でもない。
