# FWD-721〜880: 一括安全障害ドリル、運用受入証拠ギャップ、NO_GO維持

## 目的
過去の細かいPRや毎回のWindows確認を避け、既存の合成リスク試算、通信中断監視、重要経済指標の前後15分停止窓を **一度の非発注テスト** で横断検証する。あわせて研究証拠と実MT4/ブローカー安全性の独立証明を10分野に分類してrunbookへ統合する。

## FWD-721: 既存シャドーウォッチドッグの型と非有限数の封じ込め
- 最新周期の経過秒数、3ペア各最終レート年齢で NaN/Infinity を拒否。数値による `watchdog_latched=1` の過去ラッチ偽装を拒否。
- 既存60秒LEVEL1、600秒LEVEL2、復帰後も以前のラッチを消さない、同一runで実稼働の復帰承認は行わない、といったルールは変更しない。
- 結果に `demo_orders_permitted=false` を追加し、研究NO_GOとの境界を明確化。

## FWD-742: 合成障害キャンペーン
`research.forward_synthetic_safety_fault_campaign` は **固定された合成データだけ**を読み込む。ネットワーク、MT4、取引口座、Webブラウザー、自動注文機能へはアクセスしない。
- DD2%、3%、4%、5%（解除は自動ではなく承認必須）、回復時のラッチ保持。
- 日次損失1.5%、同時保有リスク1.0%、1取引0.5%の計算上の境界。既存 `forward_risk_timeline` を使い、1取引0.5%の確認は単なる計算契約で実口座の証明ではない。
- NY17時点の夏/冬DST境界。
- 通信障害59/60/599/600秒、LEVEL2から新鮮なレートへ戻っても過去のラッチをクリアしない。
- BLSの**架空イベント**の発表15分前から15分後の研究用停止窓。予定時刻を持つテストデータは合成であり、本物の経済指標予定ではない。
- 時刻逆行、NaN/Infinity、改ざんしたイベントハッシュ、不正なウォッチドッグ過去状態、偽GOを差し込む故障注入。
- どの合格ケースもEA、MT4、注文系の実稼働や本番収益を証明しない。

単独実行：

    python -m research.forward_synthetic_safety_fault_campaign

結果を保存するなら一度限りの新規ファイル名を指定：

    python -m research.forward_synthetic_safety_fault_campaign --out out/synthetic_safety_20261113.json

## FWD-801: 10分野の運用受入債務
`research.forward_safety_acceptance_debt` は既存 `forward_fullstack_noorder_hub` の実資料監査結果と上記合成ドリルを読み込み、全分野を `BLOCKED_AWAITING_INDEPENDENT_EVIDENCE` として返す。
1. USD/EUR/JPY主要経済指標の独立スケジュールと時計
2. 発表前コンセンサスの独立原本と時刻
3. デモサーバー由来3ペアの価格・変換・時計
4. 単一デモ口座・MT4識別
5. 双方向監視と60秒/10分通信中断
6. 1取引0.5%、合算1.0%、日次1.5%の実口座リスク
7. DD2/3/4/5%と4/5%の人間承認ラッチ
8. 経済指標の発表前後15分の実注文停止・安全再開
9. スマホ通知・メール通知の実配信確認
10. 本人最終承認・本番移行の条件

このうち研究資料が手元に存在する件数を表示するが、存在数が増えても `broker_runtime_or_source_truth_independently_verified` をtrueにはしない。
合成テストJSONのSHA、テスト件数と重複を再検証し、書き換えられた合成結果やGOをFail Closed。

## FWD-830: 既存runbookへ一括統合
以前に作成した証拠プランを使うと、従来のBLS/中央銀行ニュース/マクロ予想/MT4コピーCSV/価格AI研究レポートに加え、**今回の合成障害ドリルと受入未検証表も一度に表示**。

    python -m research.forward_evidence_runbook --plan-file out/forward_evidence_plan.json

まだプランを作っていない場合の初回作成例：

    python -m research.forward_evidence_runbook --init-plan out/forward_evidence_plan.json --init-bls-snapshot-dir $originalBundle

上記は新PRブランチのworktreeで実行する場合の例。元の `C:\Users\Suzuki\Documents\ChatGPT\Fx` の未コミット差分と、過去のBLS原本を変更しない。

## 実環境ではまだ満たしていないこと
Rakuten MT4のデモ口座・サーバー時計・実行不可の注文経路、双方向監視、独立ウォッチドッグ、日次/DD強制決済、公式イベントの独立網羅、事前予想の出典時刻、人間承認は**合成テストの結果では立証できない**。収集・承認が必要になった段階だけWindowsで実機テストする。

## 安全条件
`runtime_go_no_go=NO_GO`、`safety_hold_latched=true`、`demo_orders_permitted=false`、`real_orders_permitted=false` を固定。ネットワーク0、AI API0、MT4/EA接続0、デモ/本番注文0、注文停止解除0。既存損失リスク・人間承認の規則は無変更。
mainへの最終マージは本人の承認のみ。CI合格は実稼働・収益・出典真正性の証明にならない。
## フォワードテストへの引継ぎ条件
監査の全10分野は、関係する独立証拠が実際に集まるまですべてBLOCKEDとして扱う。合成障害試験の成功を運用上の合格判定へ変換しない。実証データの収集やMT4の設定変更が必要になる場合は、デモ注文を禁止した独立したレビュー工程で取り扱う。過去に保存されたローカル原本の時刻・件数を新鮮な第三者証拠へ自動昇格させない。
