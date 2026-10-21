# P1-02：Python開発環境・GitHub Actions・単体試験の棚卸し

- 作成日：2026-10-21
- 前提：PR #66 マージ済み。P1-01の差分棚卸しは作成されたが、原議本人照合・安全重要仕様の実装承認は引き続き **BLOCKED**。
- 関連ID：P1-02 / P1-01 / Q109–115 / FX-AI-ARCH-001
- 到達範囲：**開発基盤の現状点検、環境診断と非売買用テストの追加**。売買ロジック、楽天MT4連携、モデルAPI接続は作らない。

## 1. GitHub上で確認した現況

| 項目 | GitHubに存在する事実 | 制限・次に確認すること |
| --- | --- | --- |
| CIワークフロー | `.github/workflows/ci.yml`、`pull_request(main)`・`push(main)`・手動実行、`Repository checks` | CI上のPASSは原議の真正性・金融安全性を証明しない |
| Python | CIは `actions/setup-python@v5` の **3.12**、Linux `ubuntu-latest` を使用 | WindowsローカルのPython/権限/依存をCIは直接検証しない |
| コード配置 | `scripts/` に純粋な検査・原議候補抽出ツールがある。独立した `src/` 取引実装はまだない | Python/EA/MT4統合、外部API、取引実行は未実装 |
| テスト基盤 | `tests/test*.py` と標準ライブラリの `unittest discover` を利用。PR #66の実行 #356 は成功し、Codexは既存 **217件PASS** を報告 | 実行件数は変更で変わる。新規診断テストは今回のCIで別途確認する |
| スキーマ・追跡 | `scripts/check_repository.py`、`check_traceability.py`、`check_acceptance.py`、`check_master_spec.py`、`check_reconciliation.py`、`check_source_evidence.py`、`check_source_review_priority.py` | 機械検査対象外の仕様意味・原議・障害時動作は本人照合が必要 |
| 構文チェック | CIは存在する `scripts/`・`src/` を `compileall -q` で検査 | `src/` が無ければスキップ。MQL4コンパイルや契約試験は未整備 |
| 外部依存 | CI定義はPython標準ライブラリで検査・テストを実行する | 将来のOpenAI/Jev/Decisions・MT4用SDKは未選定。未承認の依存追加をしない |
| Git管理・機密 | `.gitignore` は .env、秘密鍵、データベース、ログ、会話原本・抽出候補などを除外 | ignoreだけでは既追跡ファイルや手動強制追加を防げないためPR差分の機密レビュー必須 |

参照：[`AGENTS.md`](../AGENTS.md)、[`docs/p1_01_gap_report.md`](p1_01_gap_report.md)、[`specs/ai_provider_architecture.md`](../specs/ai_provider_architecture.md)。上記はGitHub上のコード/CI定義と直近の実行報告による**棚卸し**であり、ユーザーWindows環境の実測結果ではない。

## 2. Windowsで確認したい問題

PR #66のCodex報告では、Windows既定の一時領域が書き込み拒否となり最初の単体テストが失敗した。別の作業用一時フォルダーへ切り替えて217件がPASSした、と記録されている。**原因のWindows ACL・セキュリティ設定まではこのGitHub作業から特定できない。** GitHubのLinux CIが成功してもWindows権限問題の解消とは限らない。

この問題を早期発見するため `scripts/doctor_development_environment.py` を追加する。**完全オフライン**で、リポジトリの必要パスと一時ディレクトリでの小ファイル作成・読取・削除を試すのみ。環境変数、権限、ユーザー設定は書き換えず、外部サービスにはアクセスしない。

### Windowsローカルでの実行例

Fxリポジトリのトップディレクトリに移動した状態で実行：

```powershell
py -3 scripts\doctor_development_environment.py
py -3 -m unittest discover -s tests -p 'test*.py' -v
```

PythonのCI基準は3.12であり、`py -3` が別バージョンの場合は診断スクリプトがWARNを表示する。バージョン差異がある場合、必要に応じて `py -3.12` を明示して再検証する。

一時ディレクトリの検査がFAILしたら、権限を修正するか、**Gitリポジトリ外**の自分の書き込み可能な場所を作成して次を実行：

```powershell
$fxTemp = Join-Path $env:LOCALAPPDATA 'FxTestTemp'
New-Item -ItemType Directory -Force -Path $fxTemp | Out-Null
py -3 scripts\doctor_development_environment.py --temp-base "$fxTemp"
$env:TEMP = $fxTemp
$env:TMP = $fxTemp
py -3 -m unittest discover -s tests -p 'test*.py' -v
```

`TEMP`/`TMP` の変更は**現在のPowerShellセッションに限定**する。問題が解消しなければ、ログの個人パス・機密情報を伏せて原因を調べる。標準ライブラリや権限チェックを無効化してPASS扱いにしない。テスト後の臨時フォルダーの整理は本人が確認する。

## 3. 今回導入した安全な検査

| 追加物 | 目的 | 取引機能への影響 |
| --- | --- | --- |
| `scripts/doctor_development_environment.py` | Pythonバージョンとの差、必要パス、一時書込み可否のローカル・CI検査 | なし |
| `tests/test_doctor_development_environment.py` | 前提パス、書込み成功・後片付け、存在しない一時フォルダーの拒否を検査 | なし |
| `.github/workflows/ci.yml` 追加ステップ | Ubuntuの実行環境でも上記診断が成功することを継続確認 | なし |

上記の検査はユーザーのWindows環境に自動適用されない。Windowsでは前節のコマンドをローカル実行して結果を確認する必要がある。特にテスト件数・実行時刻・実行結果についてはPRのActions記録を最終確認し、未実行をPASSと書かない。

## 4. 次工程の不足・ブロッカー

| 優先 | 課題 | 状態 |
| --- | --- | --- |
| 高 | P1-01で列挙したFX-SAF-001〜006の原議照合、リスク算式、停止/復旧遷移の本人確認 | **BLOCKED**：安全重要実装は禁止 |
| 高 | Windows で実際に診断・217件相当のテストをローカル実行し、TEMP問題を再確認 | **LOCAL_VERIFICATION_PENDING** |
| 中 | Python依存・バージョンの固定運用、将来の非標準ライブラリ追加基準 | **PENDING**：API SDK導入前に定義 |
| 中 | macOS/Windowsランナー、外部APIのモック契約、SQLite故障注入、EA/MQL4のビルド | **NOT_IMPLEMENTED** |
| 中 | `FX-AI-ARCH-001` のアダプター別型契約、例外区分、モックによる返却値検証 | **P1-03に引渡し**（安全承認の代わりにはしない） |
| 中 | 合否のTASK/MODULE/PHASE登録と実証、実機・ペーパー試験 | **未受入**、Q110の本人承認を別途要求 |

## 5. P1-02完了判定と引渡し

- **達成可能**：CI定義・既存スクリプト・テストの棚卸し、オフライン環境診断の追加、GitHub Actionsで構文・テスト合格の記録。
- **保留**：ユーザーWindowsでの診断実行、元対話の本人照合、全取引安全試験、MODULE/PHASE受入・モデル本番承認。
- P1-03では、実口座接続や注文送信コードから独立した**識別子・タイムスタンプ・情報源・AIの共通データ契約の設計**を優先する。仮説/反証AIの交換可能性は `FX-AI-ARCH-001` を基準とし、Q195–199の注文状態は模擬契約にとどめる。

不変：`forward_trading_enabled=false`、`implementation_approved=false`、`human_safety_approval=false`、`owner_approved_for_safety=false`。新規のAI/MT4接続やリスク制約の変更は行わない。
