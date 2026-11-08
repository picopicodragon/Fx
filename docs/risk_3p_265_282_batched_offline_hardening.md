# RISK-3P-265〜282 | 3検証器を1PRに集約したオフライン安全境界強化

## 目的と方式

方式Eの確認・マージ頻度削減のため、**P52、P56、P59の18工程を1本のPR**にまとめる。変更は3つの公開リポジトリ・合成検証コード、1つの新規回帰テストファイル、本書のみ。原議、承認台帳、注文コード、楽天MT4/EA、秘密ログ、CI設定は変更しない。

## 実施範囲

| 工程 | 対象 | 安全強化 |
|---|---|---|
| 265〜270 | P52 合成由来証拠の統合QA | 注入辞書root・子レポートの組込みstrキーを辞書比較前に検証。status/errors/runtimeの厳密型、未知カラム、bool/int偽装を検出。未想定の子例外を固定`P52_OFFLINE_CHILD_EVALUATION_FAILURE`で拒否 |
| 271〜276 | P56 6モジュール静的AST監査 | AST parse・walkの例外と公開ファイル読込・検査中の例外を、それぞれ固定`P56_INVALID_PYTHON_SYNTAX`、`P56_TARGET_MISSING_OR_UNREADABLE`に変換。秘密・例外文字列を反射しない |
| 277〜282 | P59 P05依存関係8ゲート監査 | root、state、各行辞書キーを検査してから参照。入れ子の値と依存関係は型厳密に比較し、`False == 0`・未知比較オブジェクトを拒否。予期しない例外は`P59_INVALID_OR_MISSING_OFFLINE_SPEC`へ |

**回帰試験**：`tests/test_risk_3p_265_282_batched_offline_boundaries.py`に26件のunittestメソッドを追加。既存P52/P56/P59テストと全ユニットテストの互換性をGitHub Actionsで確認する。

```powershell
python -m unittest tests.test_risk_3p_265_282_batched_offline_boundaries -v
python -m unittest discover -s tests -p "test*.py"
```

### 絶対安全境界

P05実証0/8 BLOCKED、G1実証0/15、FX-SAF原議0/15、FORM承認0/43、PHASE-1 BLOCKED、runtime `NO_GO`、安全停止ラッチtrue、verified_values=null、production_authorized=false。1取引最大0.5%、同時リスク1.0%、日次1.5%、DD4%新規停止、DD5%全決済と本人承認、NY17:00取引日境界を変更しない。Q109固定45ソース・元資料照合/承認の状態も変更しない。

合成検証における`Exception`派生例外の封じ込めは、SystemExit/KeyboardInterrupt、OS停止、全動的Python処理や実運用安全性を証明しない。PRのCI SUCCESSは本番売買許可や停止解除を意味しない。

## 集約運用

本PRは方式Eの**1回分のバッチ**。作業単位ごとに本人の確認・マージを要求せず、差分・CI・レビュー情報をこのPRに集約する。mainへのマージ、人間承認が必要な安全状態の変更、MT4操作、発注は引き続き実施しない。最新headのWindows Python 3.13 / IANA time zonesとRepository checksの成功を確認したうえで、本人の最終mainマージ判断を残す。
