# H1 原議照合・安全仕様確定：方式E 一括実行引渡し v1 (2026-11-02)

> **承認区分：準備指示書のみ。** 原議照合・原本閲覧・本人承認・実装許可はこの文書の登録によって成立しない。 `PHASE-1=BLOCKED` / `runtime=NO_GO` / `safety_hold_latched=true` / `verified_values=null` / FX-SAF-001〜015の実装承認falseを維持。

## 出発点
- PR #162のオフライン監査済み文書 `docs/phase1_way_e_source_difference_register.md`、`docs/phase1_way_e_evidence_approval_packages.md`、`docs/phase1_way_e_gate_audit.md`。
- `specs/source_review_priority.json` のP0-01〜05、`specs/reconciliation_registry.json`、`specs/source_evidence.json`、`MASTER_SPEC.md`、`specs/safety_foundation.md`。
- `specs/reconciliation_policy.md`、`specs/source_archive_policy.md`、`docs/local_archive_guide.md` および `AGENTS.md` を必ず読む。
- 旧版のアーカイブ説明は保存の実在性を保証しない。Windowsの実ファイル所在・完全性・対象会話はローカルで検証する。存在しなければ `SOURCE_UNAVAILABLE` のまま。

## Codexによる一括作業（ローカルPC上、読み取り中心）
### H1-A: 安全な開始前検査
1. 最新mainにPR #162のマージが含まれることを検証し、作業ツリーと未コミット変更を保護する。H1専用ブランチを利用する。Git同期不可ならローカルを上書きせずリモート・差分を別途照合。
2. 原議全文の場所を **リポジトリ外** で確認する。推奨例 `C:\FxSourceArchive\originals\` は一例であり存在を仮定しない。既存アーカイブ候補を勝手に移動、削除、上書きしない。
3. ユーザーの別途許可がない場合、リポジトリ外の原本内容は自動で読まない。アクセスする前に対象フォルダ、目的、ローカル限定・非送信を説明して本人承認を得る。既に明示許可された場所と範囲がある場合に限り読み取り実行可。
4. エクスポート原本、個人情報、口座番号、資格情報、生チャット、原議全文や候補JSONをGit/GitHub、PRコメント、外部API/AIサービスへ送信しない。GitHubへの登録は機密審査を本人が終えた必要最小限の抜粋だけ。原本のハッシュは完全性の補助であり真正性の証明ではない。

### H1-B: 原議候補と差分の整理
1. FX-SAF-001〜015それぞれについて `specs/source_review_priority.json` の `question_ids` を起点に原議のユーザー発言、その直前の設問、後続の修正決定を関連付ける。後から修正した条件を古い回答で上書きしない。
2. 既存 `scripts/list_export_conversations.py`, `scripts/extract_original_decisions.py` を利用する場合は `docs/local_archive_guide.md` の制限に従い、ローカルGit外の `candidates` のみに出力。入力形式や保存場所が不明なら実行しない。
3. 原議の発言が短く設問番号不明なら周辺文脈を本人レビュー対象にする。対象外の別会話は収集・送信しない。
4. 証拠レベルを `ORIGINAL` / `SUMMARY_ONLY` / `UNAVAILABLE` に分ける。原議を実際に検証していなければ `MATCH` に変更しない。
5. 各要件について (a) 根拠の所在、(b) 提案された最終仕様、(c) 原議との一致/相違/欠落、(d) 数式と境界/例外/Fail Closed、(e) 既存仕様への影響、(f) 必要テスト、(g) 本人への決定質問を整理する。
6. `Q109〜Q115` の原文・運用方針は別立てで確認。Q116〜199の後続決定に優先順位・改訂関係がある場合は引用位置とともに整理。

### H1-C: 優先順で15件をレビュー
- P0-01: FX-SAF-001〜006（0.5% / 1.0% / 1.5%、DD、NY17、停止・再開）。
- P0-02: FX-SAF-010, 013（注文SL・サーバーSL保護）。
- P0-03: FX-SAF-011, 012（通信異常・再起動・独立監視）。
- P0-04: FX-SAF-007〜009（イベント・反証・仮説有効性）。
- P0-05: FX-SAF-014, 015（実口座稼働、人間承認）。

全件について本人に提示するための **レビューシート候補** を作る。特に日次損失の入出金補正・利益相殺、DDの仮想口数/高水位、停止理由の重畳、30分解除時計、結果不明注文再送禁止、SL未確認、AI不在時の保有期間は「未確定」を埋めず明示する。

### H1-D: 本人判断と出力
- 本人が原本の該当発言と前後文脈を照合し、機密審査を終えた後にのみ該当項目の出典状態を更新する。
- **本人の明示承認なく** `implementation_approved`、`human_safety_approval`、`owner_approval`、MODULE/PHASE受入、NO_GO、停止ラッチを変更しない。
- 本人承認を質問ごとに大量往復させない。未決判断は安全上の依存順に一枚のレビュー表へ集約して提示する。ただし解釈が必要な安全数値や承認を推測しない。
- 実装可能な範囲に限定したテスト計画案、差分案と承認対象版を作成する。安全重要な本番実装コードは触れない。

### H1-E: テスト・PR
- 変更した台帳の構造検査、`python scripts/check_reconciliation.py`、`python scripts/check_source_evidence.py`、`python scripts/check_source_review_priority.py`、`python scripts/check_acceptance.py`、`python scripts/check_master_spec.py`、`python scripts/check_traceability.py`、`python scripts/check_repository.py`、既存全Pythonテストを実行。
- GitHub PR本文には `関連仕様ID`、`テスト結果`、`本人確認` の見出しを入れる。GitHub CI結果は実際に確認する。
- PRはCodexが作成可能。mainへのマージは本人のみ。原議が足りずBLOCKEDでも、調査結果と未決事項のレビューPRは作成してよい。

## 人間による承認の入力条件
原議レビューの開始に必要なのは「このローカル原本フォルダ/ファイルを、Codexが読み取り、候補抽出し、Gitリポジトリ外にのみ中間結果を残す」ための**範囲を限定した明示許可**。この許可はGitHubへの全文送信・外部APIへの送信・安全実装承認・MT4接続・取引の許可ではない。

原議確認後、15仕様の各ID・出典位置・解釈・未決数値・安全条件・試験・承認対象版を本人が確認し、承認する場合は意思表示を別記録する。沈黙やPRマージを承認とみなさない。

## 完了判定
- `PREPARATION_READY`: 本書とレビュー作業手順が揃った状態。
- `CANDIDATES_PREPARED`: ローカル原議から候補が抽出されたが、本人による最終照合前。
- `OWNER_REVIEW_PENDING`: 本人レビュー表が揃い決定待ち。
- `RECONCILED`: 原議・差分・仕様文面・例外の確認根拠が揃った個別IDのみ。
- `IMPLEMENTATION_APPROVED`: 別途本人が明示承認した個別IDのみ。

原本にアクセスできない場合は `PREPARATION_READY / SOURCE_UNAVAILABLE` と報告し、原議照合・15件承認完了と宣言しない。
