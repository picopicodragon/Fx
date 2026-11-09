# FX-BT-010 | 2025Q1 AIマクロ判断のREVISION監査・最大2回の修正・検証履歴・同一条件比較

## 正式な運用対象と安全状態

2026-11-09本人指示により、**将来の正式運用対象も USD/JPY・EUR/JPY・EUR/USD の3通貨ペアに確定**。既存の2026-11-04 G1審査範囲3ペア×5属性と整合。旧Q3のGBP/USD・AUD/USDは歴史的な設計記録として保持し、現行運用対象には含めない。**この決定は実口座・デモ口座での注文、MT4/EAの起動、安全ゲート解除、リスク閾値変更を一切承認しない。** 現状の `NO_GO` と `safety_hold_latched=true` を維持。

通貨別ネット/グロス集中、EUR/USDのブローカー契約属性、P05/G1その他安全審査は未承認のまま。1取引0.5%、同時1.0%、日次1.5%、DD停止等の既存仕様を緩めない。

## 監査対象の実観測（ユーザーWindows実行の報告）

2025Q1 公式マクロ10イベント・30判断・3ペアに対して、`LONG=3`、`SHORT=4`、`HOLD=23`、`APPROVED=24`、`REVISION=6`。内訳はHOLD/APPROVED=23、LONG/APPROVED=1、LONG/REVISION=2、SHORT/REVISION=4。唯一承認された非HOLDは `AI00016`（USD/JPY LONG、2025-02-12T14:00Z）。旧バックテストの取引1件、純損益-400円。ただし元のJSON決定ファイルは**ユーザーのWindowsにのみ存在**し、GitHubでは実際の6件のレビュー理由や個別約定結果を確認していない。検証前にレビュー理由を捏造しない。

## 実装された4作業

1. **REVISIONの原因分析**: `research.macro_revision_pipeline` のオフライン実行は既存30判断を検証し、各REVISIONの初回分析文、反証、レビュー原文、対象時刻、ペア、ソースのハッシュを監査JSONへ保存。ネットワークアクセスなし。集計と理由は人間がこの監査ファイルで確認できる。
2. **修正・再検証ループ**: 明示 `--allow-external-api` がある場合のみ、元の6件など初回REVISIONに限定し、分析モデルが独立レビュアーの指摘を使って**最大2回**修正。毎回異なるモデルIDのレビューを必須とする。承認・棄却・保留のいずれかになればその時点で停止。なおREVISIONが最後まで続く場合はHOLD、REJECTED/PENDINGはHOLD。**売買成立件数を増やすために承認基準を緩めない**。
3. **判断履歴の保存**: 初回・各修正回・最終の仮説と反証、レビュー理由、レビュー判定、引用元ハッシュ、回数、初回・最終判断ジャーナルのSHA-256を個別の監査JSONに保存。元の30判断ファイルは上書きしない。新しい判断ジャーナルは従来の厳密な`fx_macro_decisions_v1`互換でバックテスト可能。
4. **比較検証**: 初回と修正後の30判断を同一の公式10イベント、同一のユーザー保有H1 bid/ask CSV6本、同一資金・リスク・売買エンジンにかけて再計算。取引数、損益、最大DD、売買承認数、拒否理由を比較。判断件数とas-of、根拠ハッシュの変更を拒否する。**本物の2025Q1での修正後パフォーマンスはユーザーPCで実行するまで不明**。

## 利用方法: オフラインの6件監査（従量課金なし）

```powershell
cd C:\Users\Suzuki\Documents\ChatGPT\Fx
git fetch origin
git switch --detach origin/feat/macro-revision-audit-compare-three-pairs
python -m research.macro_revision_pipeline `
  --decisions out/macro_ai_decisions_2025Q1_30.json `
  --audit-out out/macro_ai_revision_initial_audit_2025Q1.json
```

`out/macro_ai_revision_initial_audit_2025Q1.json`の`revision_cases`で各案件の`initial.reviewer_rationale`を監査。出力にはテキストが含まれるのでAPIキー等の秘密情報を含めないようローカル保管し、チャットに全文貼付しない。

## 6件の再検証と導入前後比較（有料API、最大24回）

```powershell
python -m research.macro_revision_pipeline `
  --decisions out/macro_ai_decisions_2025Q1_30.json `
  --prices-dir data/raw/dukascopy_h1 `
  --analyst-model gpt-6-luna `
  --reviewer-model gpt-6.1-sol `
  --audit-out out/macro_ai_revision_paid_audit_2025Q1.json `
  --revised-out out/macro_ai_revised_decisions_2025Q1.json `
  --comparison-out out/macro_ai_revision_comparison_2025Q1.json `
  --allow-external-api
```

初回6件が全てREVISIONなら各2ラウンド、最大 **6×2×2=24 API呼び出し**。一次の30判断については再生成せず、保存済み履歴を再利用。出力先が存在する場合は上書き禁止、失敗時は`FAIL_CLOSED/NO_GO`。比較は研究結果であり、利益保証や本番GOを意味しない。

### 残る重要な限界

- アーカイブの市場コンセンサス6件は正確な公表前時点のスナップショットが未証明。AI学習に埋め込まれた未来知識も完全排除できない。
- 10イベント・3ペア×10回の狭い観測。標本数不足に加え、REVISIONだけを追加推論するため、改善を観測しても独立したアウトオブサンプルでの優位性は示せない。
- 初回30判断のモデル出力が再現可能とは限らないため、**同一の保存済み30判断**を初回と修正後で比較する。
- API呼び出しはローカルユーザーの明示指示時のみ。CIは合成資料・モック推論でテストし、外部送信しない。
