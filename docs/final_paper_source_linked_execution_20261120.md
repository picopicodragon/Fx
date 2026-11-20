# FINAL-PAPER-111〜125: 実H1/公式ニュース/AI台帳/MT4価格の最終仮想E2E

ベース：PR #292（その下に#291, #290）。mainへのマージ、旧台帳の改変、
Windows上で稼働中のPython監視停止、MT4売買指示、追加有料APIは行わない。

## 実装

1. research/final_paper_completed_decision.py
   - 既にCOMPLETEとなった二つの異なるモデルによる判断を厳格再検証。
   - 同じpair・確定H1 bar・公式ニュース原本から作ったpacket SHA256に再結合。
   - 返答pending、2つ以上の同じbarの台帳、将来時刻、期限超過、
     異なるpacketをfail-closed。PCファイルmtimeは独立した証拠ではない。
   - 新規API 0回。reviewed_epochはローカル最終書込時刻を保守的に採用。

2. research/final_paper_runtime.py
   - 新たな請求前に、該当H1で既存COMPLETEモデル判断があれば検証して使用。
   - processed_h1_keys、used_signal_ids、pending_signals、旧IDとの重複を防止。
   - そのH1に既存判断が無い場合の旧6コール上限や証拠停止を維持。
   - 安全証拠により仮想エントリーが停止されるのは従来どおり。

3. research/final_paper_e2e_replay.py とPowerShellエントリー
   - 実物のMQL4/Files/FxPaperQuote CSVと、H1の三通貨原本、公式ニュース
     保存済み原本、COMPLETE AI台帳がすべてそろう場合にのみ実行。
   - 事前モデル判断を再生成/偽造せず、既存判断と元packetを厳格照合。
   - 隔離されたメモリ内初期10万円仮想ポートフォリオで次quoteに約定し、
     SL/TP/FLAT/残高を計算。結果は「過去の反実仮想研究」だけ。
   - 30〜90秒の連続実CSVが無い場合は失敗停止。
   - 本番journalやMT4ファイルへの書戻し無し。API0・broker注文0。

4. research/final_paper_point_in_time_evidence.py
   - USD/EUR/JPY重要予定と発表前コンセンサスについて、保存済み一次資料と
     合意資料の局所SHA256、PC申告の時刻順、HTTPS許可ホスト、パス逸脱を検証。
   - 保存バイトの完全性は外部の発表主体認証・時計認証・将来イベント完全網羅と
     同義ではないため、これだけで本番の仮想取引を許可しない。

5. research/final_paper_api_cost_envelope.py
   - 2モデルの最大入力/出力トークン、ユーザーが収集したAPI料金表、
     USD/JPY上限、既存月間JPY費用から2回推論のワーストケース費用を計算。
   - 課金表や為替上限が提供者により独立認証済みとは主張しない。
     上限6/6は変更せず、これだけで追加APIを許可しない。

## Windows実機での作業（安全な非発注研究）

新ブランチを「稼働中監視とは別の作業ツリー」で取得し、必要な原本が
存在する場合に限り、以下を実行する：

    .\scripts\final_paper_source_linked_e2e_once.ps1 `
      -Mt4FilesDirectory $mt4Files `
      -H1Snapshot $verifiedH1CaptureFolder `
      -Pair 'USD/JPY' `
      -NewsBundle $originalOfficialNewsBundles

上記の変数は実在する元ファイルへの絶対パスで設定する。
H1・ニュース・AI台帳が同じ時刻・同じpacketを表さない場合は停止。
過去のユーザー実機で完了済み3モデルペアが全てAPPROVED/HOLDであれば、
新規仮想建玉が0であることが正しい結果。実証のために人工的なLONG/SHORTへ
書き換えてはいけない。

## 未解決の外部受入ゲート

- 通信ラッチの実機適用は#291にある一度限りの手順が必要。
- ブローカー時計・マクロ予定完全網羅・発表前コンセンサス・コストは
  第三者原本と時刻の真正性確認が必要。
- AIは6/6回で、OpenAI料金実績・最大トークン価格・月3,000円管理と
  新たな課金承認が無いため、今は増額せず0回。
- 全て満たされても、実AIがAPPROVED/HOLDなら新規建玉は0である。
- 既存mainの変更や実注文許可は人間承認まで停止。

Windows画面ロック Win+L だけで通常監視は止まらない。
スリープ・休止・シャットダウン・再起動・ネットワーク切断は
監視停止となるため電源設定の確認が必要。
