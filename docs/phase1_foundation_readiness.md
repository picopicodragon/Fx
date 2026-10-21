# Phase 1: 共通データ基盤・安全制御 | 着手計画

- 作成日: 2026-10-21
- 基準仕様: README v19.9 / Q1–Q199（Q199は推奨案暫定採用）
- 状態: **開発フェーズへ移行、ただし安全重要実装は承認待ち**
- 対象: ローカル・オフラインの開発基盤、仕様照合、受入試験設計
- 非対象: 実売買、実口座接続、注文送信、承認未取得の安全重要機能の実装
- 参照: `AGENTS.md`、`MASTER_SPEC.md`、`specs/safety_foundation.md`、`specs/reconciliation_policy.md`、`specs/standing_recommendation_policy.md`

## 不変の安全条件

```text
forward_trading_enabled=false
implementation_approved=false
human_safety_approval=false
owner_approved_for_safety=false
```

Q1–Q199の損失制限・注文前検証・停止理由・復旧承認・Q171隔離失敗ラッチ・Q195–199の結果不明時の無確認再送禁止を維持する。外部注文応答やDB事前保存は約定証明ではない。原議未照合の安全重要仕様を実装承認済みと見なさない。

## 作業順序と完了条件

| ステップ | 実施内容 | 完了条件 | 制約 |
| --- | --- | --- | --- |
| P1-01 | 原議照合・差分／未決登録 | Q1–199の証拠レベルと未決事項を可視化 | 推定でVERIFIEDを付けない |
| P1-02 | Python開発・CI/単体試験の現状棚卸し | 既存チェックの実行結果と欠落検査を記録 | PASSを金融安全性の証明にしない |
| P1-03 | オフライン構成・データ契約設計 | 識別子、時刻、型、イベント形式と入力検証を仕様IDへ紐付け | 本番注文処理は作らない |
| P1-04 | SQLite設計・障害注入試験計画 | WAL/FULL、停止ラッチ、曖昧コミット、復旧の試験表 | 原議照合・本人承認前に安全重要コードを実装しない |
| P1-05 | 模擬ブローカー境界の仕様化 | DISPATCHING、応答三分岐、独立照合と再送禁止をテストケース化 | 実口座への接続を禁止 |
| P1-06 | TASK/MODULE/PHASE受入判定 | 証跡、未解決事項、本人承認を記録 | CI PASSやPRマージだけでPHASE合格にしない |

## 最初の検査コマンド（ローカル／CI）

```powershell
python scripts/check_master_spec.py
python scripts/check_reconciliation.py
python scripts/check_source_evidence.py
python scripts/check_source_review_priority.py
```

各スクリプトの存在・実行環境・実行成否は開発機で確認する。未実行をPASSとは記録しない。トレーサビリティと受入登録の既存チェックもCI定義に従い確認する。

## 明示的ブロッカー

1. 原議の完全なローカルアーカイブとの照合、および安全要件の本人による元資料確認が未完了。
2. 楽天MT4の注文応答、約定確認、口座・建玉照合の具体API挙動は未実機検証。
3. Q197–199のSQLiteとブローカー間の障害境界および再起動後の状態遷移は未決。
4. 安全重要モジュールの実装承認、PHASE合格承認、本番稼働承認は未取得。

## PRレビュー条件

- 本PRはフェーズ着手計画の文書追加のみ。
- コード変更・自動テスト実行・実機検証は含まない。
- 既存の安全閾値・運用許可は一切変更しない。
- オーナーが差分を確認し、手動でmainへマージする。

## CIイベントの再検証

PR本文の必須見出し（`関連仕様ID`、`テスト結果`、`本人確認`）は`check_repository.py`で検証する。過去の失敗済みworkflow_runの再実行は当時のイベントpayloadを使う場合があるため、PR本文変更後は新規pushによる新しいpull_request/synchronizeイベントのチェック結果を確認する。古い失敗ログのみをもって新しい変更の判定としない。
