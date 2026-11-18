# FINAL-PAPER-104〜110：5工程の統合監査

対象：2026-11-18、監視・通信停止ラッチ・マクロ時計とコスト・AI課金・仮想E2Eの5工程。
PR #291を親とする積み上げPR。既存Windows監視は変更しない。
MT4注文、追加有料AI、mainマージは実行しない。

## 実装

- research/final_paper_five_gate_readiness.py：journal・AI台帳・請求監査・公式イベント一覧・MT4契約属性・producer/consumerの全てを読み取り専用で統合評価。非原子的に変わったjournal末尾はfail closed。
- scripts/final_paper_live_supervisor_check_once.ps1：Windows側でPython監視プロセスを数え、秘密のコマンドラインを印字せず統合監査を実行。プロセス存在だけで稼働正常とは宣言しない。
- tests/test_final_paper_five_gate_readiness.py：292サイクル・0追加AI、ラッチ解除だけでentry不可、全synthetic許可フラグでも実環境のE2E成功を主張しない、ハッシュraceを拒否する回帰テスト。

## Windowsでのread-only監査

監視ウィンドウを閉じず、別のWindows PowerShellで、新しいレビュー用Git作業ツリーから：

    .\scripts\final_paper_live_supervisor_check_once.ps1 -Mt4FilesDirectory $mt4Files

公式原本がある場合だけ任意の -EventCalendar $eventFile、請求の確認記録がある場合のみ -BillingStatement $billingFile を指定。
本人提供のファイルは公式独立認証ではない。欠損項目はNO_GOを維持。

## 現在の非充足条件

1. PythonプロセスとMT4 Experts稼働証拠、時間差のあるjournal増加の確認はWindows実機で必要。
2. 通信ラッチの本人承認は受領。PR #291の手動ステージングと次の新鮮quoteへの反映を実機で検証する必要がある。
3. USD/EUR/JPYの一次イベント原本・事前コンセンサスと独立時計・スリッページ／手数料／スワップの実測は未完。
4. API累計6/6は維持。月3,000円請求額の独立照合と追加有料AI利用の承認は未完。
5. synthetic仮想エンジン試験と実市場データによる独立AI APPROVEDシグナルの実行証拠は異なる。新規仮想建玉は未発生。

新規仮想エントリーは全ゲートの実証まで不許可。承認を勝手に拡張しない。

## Windowsのロック

Win+Lによる画面ロックだけなら通常MT4のOnTimerとPythonは動く。スリープ・休止・電源OFF・通信断・更新再起動で観測は止まる。既存PowerShellを閉じず、電源接続中の自動スリープを無効にし、解除後にCSVとjournalの更新を別々に確認する。