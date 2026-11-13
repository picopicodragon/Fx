# FWD-1201〜1360：保存原本の版管理・鮮度確認・改訂追跡・runbook一括統合

## この工程で実際にできること
既存の `forward_regional_original_bundle` と `forward_regional_source_intake` で保存・照合できる経済指標の原本を、複数回の観測順に蓄積して検証する。新しい原本のSHA256を人間が手入力する必要はなく、以前の履歴を上書きせず新規履歴を作る。**自動Web収集・架空指標の作成・実取引再開は行わない**。

### research.forward_regional_history_register
保存した `original_manifest.json` を最大32件まで明示列挙し、各manifestのSHA256を自動計算。原本自体のSHA256・原文引用・出典時刻・発表予定・発表15分前の予想記録を既存監査で再検証する。出力は `fx_fwd_regional_evidence_history_manifest_v1`。
更新時は `--previous-history` で元履歴を指定し、**新しい** `--out` を指定する。元履歴と原本は不変更。指定フォルダー内のデータを勝手に走査・自動追加しない。期限外/破損/不正順序の資料はFail Closed。

### research.forward_regional_evidence_history
保存した履歴から全manifestと各原本のハッシュを再検証し、同一通貨＋event_idの発表時刻・名称・分類・公式原文・予想値の変化を検出する。
- USD / EUR / JPYの**次回予定イベント件数**と発表前予想が付いた件数を別々に表示。
- USD/JPY・EUR/JPY・EUR/USDそれぞれに関連する保存予定の件数を表示。ただし相関波及や独立認証は未実施。
- 各通貨の最新保存時刻が24時間超古い、または未保存なら保留。古い原本を今の最新ニュースとして扱わない。
- 指標の名称・発表時刻・予想値に改訂があれば「要レビュー」とする。似た名前のイベントの自動統合・予想値の上書き・自動GOは不可。
- 指標がすでに発表された日時なら「今後の予定」として数えない。原本の歴史的価値は保持する。
- publisherやsource URL、manifest内のpublished_at・captured_atは独立認証されていない。SHA256はローカル整合性のみを証明する。

### 既存research.forward_evidence_runbookへの統合
新フィールド `regional_history_file` を任意で追加。過去のフィールド数の少ないプランも読める。履歴があればその結果の `regional_saved_history_readiness` と、今後の収集不足項目を既存の一括レポート・研究タスク優先表示に含める。
履歴を指定しなかった場合も `regional_saved_history_missing=true` とし、他の実BLS原本/公式ニュース/MT4非発注CSV/AI研究/安全テストを従来どおり評価する。

## Windowsでの最小コマンド
原本パッケージを生成済みの新worktreeで実行。以下のパス名は説明用で、実際に存在するパスに置き換える。PowerShellの `$asof` は利用者PCの時計に依存し、出典の時刻を独立に証明しない。

    $asof = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
    python -m research.forward_regional_history_register --manifest 'C:\saved\batch1\original_manifest.json' --manifest 'C:\saved\batch2\original_manifest.json' --asof-utc $asof

上記の事前チェックに成功した場合、**未存在のファイル名**で初回履歴を作成する。

    $history = 'out\regional_history_' + (Get-Date -Format yyyyMMdd_HHmmss) + '.json'
    python -m research.forward_regional_history_register --manifest 'C:\saved\batch1\original_manifest.json' --manifest 'C:\saved\batch2\original_manifest.json' --asof-utc $asof --out $history
    python -m research.forward_regional_evidence_history --history-file $history --asof-utc $asof

後日新たな保存原本を追加する場合、**以前の `$history` を上書きしない**。

    $next = 'out\regional_history_' + (Get-Date -Format yyyyMMdd_HHmmss) + '.json'
    python -m research.forward_regional_history_register --previous-history $history --manifest 'C:\saved\batch3\original_manifest.json' --asof-utc $asof --out $next

既存runbookとまとめるには、プランのJSONに ``regional_history_file`` を設定する。新規プランなら `--init-plan ... --init-regional-history-file $history` でも指定可能。

    python -m research.forward_evidence_runbook --plan-file out/real_forward_plan.json

## 未解消のブロッカー
- 米欧日の主要指標を完全にカバーする独立した時点付き経済カレンダー。
- 発表前の実コンセンサス保存原本、独立な出版社・公開時刻と取得時刻の証明。
- MT4デモサーバー時計、発注経路の物理的停止、双方向監視、通信障害、DD4/5%承認インターロック。
- 経済イベント前後15分の実EA停止と安全再開、実通知と本人承認。

全モジュールは `NO_GO`、`safety_hold_latched=true`、`demo_orders_permitted=false`、`real_orders_permitted=false` を固定。バックグラウンド監視なし、ネットワーク0、AI API0、MT4/EA操作0、注文0。mainマージは人間の最終承認のみ。