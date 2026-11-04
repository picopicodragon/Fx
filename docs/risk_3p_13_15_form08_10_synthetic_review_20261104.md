# RISK-3P-13〜15 追加一括工程：FORM-08〜10 日次損失・DD・時刻の合成検証

2026-11-04。PR #178マージ済みmainを基準に、FORM-03〜07のバッチと**同一ブランチ**に追加した本人審査用資料。本工程もオフライン・合成のみ。実運用計算やMT4/EA/売買/停止解除の承認ではない。

## 1. まとめて追加した検証

| 工程・FORM | 合成で検証すること | 正式な未決事項 |
| --- | --- | --- |
| RISK-3P-13 / FORM-08 | NY17の「与えたUTC時刻」の日にちをAmerica/New_York（DSTあり）に正規化、期首純資産10万円×1.5%=1500円、1500.00円と1500.01円の境界、出入金調整の一例 | 利益相殺、費用/Swap転記、取引休場日、原本帳簿への入出金有効時刻、遅延調整の採用規則 |
| RISK-3P-14 / FORM-09 | 合成unit現在値/過去HWMからDD4%/5%の閾値を比較。HWM・外部入出金・再起動ラッチ不明なら計算拒否 | 口数発行償還の実ルール、HWMの耐改ざん永続化、再起動中の承認・復帰、ゼロ/負値と同時入出金 |
| RISK-3P-15 / FORM-10 | ACCOUNT/POSITIONS/PENDING/FX_QUOTES/CONVERSION/LEDGERの6系統の合成UTC時刻・epoch照合、時計逆転/異常・未来時刻・証拠欠落を拒否 | データごとの承認済み鮮度上限、休場日・時刻補正・DSTスケジュール、再起動後の単調増加時計整合 |

## 2. 数値と時間の合成例

- 夏時間：2026-07-01のNY17:00 = 2026-07-01 21:00 UTC（翌取引日区切り）。冬時間：2026-01-01のNY17:00 = 2026-01-01 22:00 UTC。実際のFX休日・稼働可否を決める関数ではない。
- 期首の架空JPY純資産100,000、現在98,500、入出金0なら架空日次損失1,500円。既存1.5%上限には**到達時点で停止**する条件を変えない。入金があっても分母を現在equityへ増額して上限を緩めない。
- `opening + net external cashflows - current`という説明用の調整は**確定した本番損失算定式ではない**。利益相殺と費用・訂正の計上方法も未承認。
- 過去最高の合成unit価値100、現価96ならDD4%、現価95ならDD5%。既存DD4%新規停止とDD5%の全決済・人間承認を維持。unit価値とHWMの真正性・入出金による償還式は未検証。
- 鮮度チェックは**意図的に共通TTLを設定しない**。全6データが形式上同一世代でも、観測時刻が古ければ本番の鮮度合格にはならない。`review_freshness()`は実際の合格を返さず、常時NO_GO。

## 3. 証拠未取得と実装承認の境界

FORM-08/09/10は既存の`specs/p0_01_risk_formula_open_decisions.json`で`UNDECIDED_IMPLEMENTATION_DETAIL`と`blocking=true`。それらを変更しない。Q128のDD2/3監視解除に限る15秒という記録を、口座/注文/為替/証拠の共通TTLとして流用しない。異なる資料/世代/時計補正、休場日の新規エントリーの可否も将来の証拠・本人承認が必要。

純粋関数は`datetime`とIANA `ZoneInfo`だけで**与えられた合成UTC時刻**を変換する。現在時刻取得・OSウォッチドッグ・NY17による発注再開機能はない。DD4%/5%の判定表示でもstopの解除関数はなく、`phase_1=BLOCKED`、`runtime_go_no_go=NO_GO`、`safety_hold_latched=true`を必ず保持する。

## 4. ファイル・レビュー方法

- `scripts/phase1_form08_10_synthetic_controls.py`（合成日次/ DD/ 時刻形状の純粋関数）
- `tests/test_risk_3p_13_15_synthetic_controls.py`（DST・1500/1500.01円、DD4/5%、失効/時刻欠落/未来時刻・時計異常の拒否テスト）
- `specs/risk_3p_13_15_form08_10_owner_review_20261104.json`（F08〜10の未決12事項、本人承認履歴なし）
- `scripts/audit_risk_3p_13_15_owner_batch.py`、`tests/test_risk_3p_13_15_owner_batch.py`（虚偽の承認・停止解除・共通TTLの捏造を検出）
- `specs/traceability.json` とWay E期待ファイル一覧にQ109とテスト対応を追加。実コードのproduction_authorized=false。

再現コマンド：
```text
python -m unittest tests.test_risk_3p_13_15_synthetic_controls -v
python -m unittest tests.test_risk_3p_13_15_owner_batch -v
python scripts/audit_risk_3p_13_15_owner_batch.py
python -m unittest discover -s tests -p "test*.py"
```

## 5. バッチ後の優先順位

本PRでRISK-3P-08〜15（FORM-03〜10）をまとめてオフライン検査したあとに必要な**次の実作業**は、本人がFORMごとに未決の仕様方式と証拠要求を承認すること、G1の対象3ペア×5属性について安全な環境で実証する手順を個別審査すること、FX-SAF-001〜015の原議と受入ゲートを確認すること。合成テストPASS/PRマージをその代わりにはしない。

今後の通常のオフライン開発は同一ブランチ/PRへ積み上げられるが、mainへの最終統合は既存`AGENTS.md`により本人の差分・CI確認後の手動マージとする。こうして手動マージを**8回から1回に減らしつつ**、安全重要な仕様承認・本番実行の境界は省略しない。

**不変：** 3ペアUSD/JPY、EUR/JPY、EUR/USD。個別0.5%、全体非相殺1.0%、日次1.5%、DD4%停止/DD5%全決済。G1〜G9 UNRESOLVED、FX-SAF-001〜015未承認、PHASE-1 BLOCKED、runtime NO_GO、停止ラッチtrue、verified_values=null。