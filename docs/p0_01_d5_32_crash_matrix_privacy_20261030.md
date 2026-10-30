# P0-01 D5-32：G2公開用JSONの厳格制限とG6クラッシュ地点別マトリクス

作成：2026-10-30。前段D5-31：PR #146マージ済み、本人Windowsの1,318件OK、GitHub CI成功。

**範囲：OFFLINE_SYNTHETIC_G2_PRIVACY_G6_CRASH_CUTS_ONLY。** MT4起動・ログイン・照会、EA/EX4、楽天照会、注文・決済、実OS時計、実ファイルI/O、署名、通知、Gitフック/実Gitリポジトリスキャンを実施しない。安全状態は全経路で `phase_1=BLOCKED` / `runtime_go_no_go=NO_GO` / `verified_values=null` / `safety_hold_latched=true`。

## G2：公開JSONテキストの検査

D5-31は辞書型の公開メタデータを固定5項目に限定した。D5-32は**呼出元から渡されたJSONテキスト**も厳密に検査する。次をすべて満たす必要がある。

- 384バイト以下のASCII文字列、JSONオブジェクト型。UTF-8 BOMや非ASCII文字も拒否。
- キーの重複は禁止。`NaN/Infinity`、追加JSONテキスト、余分なネスト・配列・自由記述は禁止。
- 辞書に復元後、`json.dumps(..., sort_keys=True, separators=(",", ":"), ensure_ascii=True)` で得られる**唯一の正規表現文字列と完全一致**。改行、空白、キー順差、Unicodeエスケープを含む表記の揺れを拒否。
- フィールドは `check_id`、`design_state`、`origin`、`schema_version`、`simulation_only` の5つのみ。値は従来どおり `D530-G2-01〜08` / `NOT_PERFORMED` / `SYNTHETIC_ONLY` / 数値1 / `true` の固定型・固定値。

**注意：** これはインメモリの文字列形式検査であり、リポジトリのファイル内容・Git履歴・コミット前フックを実スキャンしていない。書込み前に強制適用する経路も存在しない。公開内容の機密混入が実環境で防止されたとは主張しない。実口座同一性・EA・建玉・未約定注文の確認も未実施。

## G6：7段階×クラッシュ地点の合成検査

D5-31の7段階（停止ラッチ先行、履歴/取消し準備、耐久保存案、書込み主体/チェックポイント確認、独立基準の発行、ローカル確定、復旧時の停止再確認）について、開始前を含む**8つの完了プレフィックス**を`D532-CUT-00〜07`として作成。全て同じ合成基準スナップショットを参照しているか検査する。

| クラッシュ地点 | 完了した合成手順 | 期待する判定 |
|---|---|---|
| CUT-00 | 0段階 | PARTIAL_COMMIT_STOP_HELD_NO_GO |
| CUT-01〜06 | 1〜6段階 | PARTIAL_COMMIT_STOP_HELD_NO_GO |
| CUT-07 | 7段階 | SYNTHETIC_PROTOCOL_COHERENT_NEVER_AUTHORIZED |

各地点についてD5-27〜31で定義した10脅威（保存中破損、電源断、巻戻し、同時偽造、取消し削除、二重書込み、時計異常、鍵攻撃、保存不可、古いバックアップ）を組み合わせ、**8×10＝80件**の故障注入申告テストを追加。書込み・基準点・取消し・時計・停止ラッチ等の異常も単独・複合で検査する。

**すべての結果はNO_GO**。下位D5-31ゲートを改ざんして`GO`や`broker_verified=true`を返す場合、上位D5-32は拒否する。全プレフィックスが順序どおり揃っても実クラッシュを起こしたことにはならず、真正な独立Trust Anchor、署名・鍵、復旧永続性、異なる保護領域間の原子性は未実証。攻撃者が元スナップショット・履歴・参照値をまとめて書き換えれば、未信頼データの一致だけでは検出できない。

## 追加ファイル

- `scripts/p0_01_d5_32_crash_matrix_privacy.py`：公開JSONと8地点の横断検査。返値は診断ステータスと子ゲートの**固定コードのみ**で、入力データ・機密文字列を返さない。
- `specs/p0_01_d5_32_crash_matrix_contract.json`、`specs/p0_01_d5_32_synthetic_fixture.json`：設計と架空入力（実口座/実ログなし）。
- `tests/test_p0_01_d5_32_crash_matrix_privacy.py`：新規151件（明示71件＋8×10個別生成80件）。
- `specs/p0_01_d5_32_status.json`：G1〜G9未解決、実行未承認を維持。

## 検査と受入

前工程1,318件＋今回151件＝**合計想定1,469件**。GitHub Repository checks、Windows Python 3.13 / IANA time zones、本人Windowsローカルテストの成功を要する。本人が差分を確認してPRを**手動マージ**。このマージはMT4の操作・実ストレージの試験・停止解除・デモ/本番売買の承認ではない。

既存の単一MT4環境方針、楽天問い合わせ中止、別デモB不採用、損失/DD停止上限・NY17日次区切りは変更しない。G1〜G9は全件`UNRESOLVED`。G2現口座状態`UNKNOWN`、G6独立Trust Anchor・原子的保存・クラッシュ実証未実施を維持。
