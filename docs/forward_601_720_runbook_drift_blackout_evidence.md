# FWD-601〜720：繰り返し作業を減らす一括フォワード研究運用

## 開発目的
コードを小工程に分けず、従来の研究用フルスタック監査を再利用する「一度プランを作って何度でも同一コマンド」「前回の不足項目との比較」「発表前予想の再検証を強化」「イベント前後15分の研究観測カバレッジ」を一つのPRにまとめた。すべて研究専用で注文を一切出さない。

## 構成

### FWD-601〜616：書き込み済み発表前予想の安全再検証
forward_macro_pre_release_capture.verify_archive は、本人が独立に検証していないアーカイブのSHAが整合していても、`captured < scheduled - 15min` を再チェック。前15分以内、発表後、未来時計、デモ注文許可フラグや出典認証の偽装をFail Closed。既存の保存仕様と発行手続きはそのまま。

### FWD-617〜672：研究用runbook
新モジュール `research.forward_evidence_runbook`。固定スキーマのJSONにBLS保存フォルダー、中央銀行・BLSニュース原本、米欧日マクロファイル、最大64予想、最大24 MT4 CSVセッションとログ、AI研究ジャーナルを指定。一度作れば次回から同じパスを繰り返さずにオフライン一括実行。
- プランの相対パスはプランファイルのあるディレクトリ基準で解決。ワイルドカード、ディレクトリの無断走査、環境変数展開、シンボリックリンク、存在しない明示ソース、重複ソースを拒否。
- 明示されたパスは必ず原本再監査し、合格しない場合は失敗。ソースの未指定は保留とする。偽の価格CSV・時刻・カレンダー・予想は生成しない。
- `--init-plan` で空のプランを一度だけ作成可能。`--init-bls-snapshot-dir` と `--init-official-news-bundle` は既存の**フォルダーだけ**を初期プランに埋める。保存原本内部へのプラン書込は禁止。
- `--out` は新規ファイルへ一度だけ書き込む。省略時は画面出力のみ。未解決アクションを5区分の優先順に並べるが、優先順位は投資判断/安全解除には使わない。

### FWD-673〜700：前回の監査との差分
新モジュール `research.forward_readiness_drift`。前回runbook出力を `--previous-report` で指定すると、保留の増減、価格CSV・予想・MT4観測・停止窓研究の数値変化を再掲。以前の保留理由が消えても**解決したことの証明ではない**。どのケースでもNO_GOと人間承認条件は維持。

### FWD-701〜720：前後15分の研究用ブラックアウト観測
新モジュール `research.forward_blackout_observation_coverage`。保存したBLS ICSの予定と、検証済みUSD/EUR/JPY外部予定の各発表時刻から研究用±15分の時間窓を生成。コピー済みMT4観測CSVから得たセッション開始/終了時刻と重なりを調べ、USD/JPY・EUR/JPY・EUR/USDの観測できた時間窓の件数を表示。
- BLS HTMLにだけある発表予定をICSから**勝手に生成しない**。不一致があれば専用保留を付与。
- 保存CSVに相場価格があっても、注文停止やEA自動再開が正しく稼働した証拠にはならない。実売買/デモ取引との接続はない。
- 観測時刻と原本時刻は自己申告・ローカル時計のため独立認証ではない。

## Windowsでの最少操作
既存のPowerShell変数 `$originalBundle` が2026-11-13に保存したBLS原本の絶対パスを指しており、別worktreeの新ブランチに移動した状態で、最初の一回だけ以下の2行を実行する。

    New-Item -ItemType Directory -Force out | Out-Null
    python -m research.forward_evidence_runbook --init-plan out/forward_evidence_plan.json --init-bls-snapshot-dir $originalBundle

以後はこの一行で繰り返し監査（自動ダウンロードなし）。

    python -m research.forward_evidence_runbook --plan-file out/forward_evidence_plan.json

実行結果を保存して次回との差分を見る場合は、以下のように毎回**新しい**ファイル名で書き込む。

    $name = "out/forward_check_$(Get-Date -Format yyyyMMdd_HHmmss).json"
    python -m research.forward_evidence_runbook --plan-file out/forward_evidence_plan.json --out $name

前回の `$previous` を保持していれば、次回は `--previous-report $previous` を足すだけ。プラン内の `sessions` や外部マクロ原本は実データが揃った場合のみ追加する。実データが未取得ならnull/空配列のままでよい。

## 安全境界と受入
- 自動ネットワークアクセス、AI API、MT4/EA、注文・決済はすべて0。runbookはワンショットでバックグラウンドタスクではない。
- Q21〜24に沿う前後15分停止、1取引最大0.5%、同時1%、日次1.5%、DD4%・5%、人間承認などの仕様は変更しない。
- `runtime_go_no_go=NO_GO`、`safety_hold_latched=true`、`demo_orders_permitted=false`、`real_orders_permitted=false`。
- GitHub CIテストの合格は入力ファイルの構文・相互整合の検証を示すが、実価格・金融公表時刻・MT4口座・発注停止動作の独立検証を示さない。
- mainへのマージは既存規約どおり人間の承認のみ。