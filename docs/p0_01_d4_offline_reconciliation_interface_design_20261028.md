# P0-01 D4：オフライン照合インターフェース設計（2026-10-28）

**設計のみ。実測情報の取得・取込・照合エンジンの実装は未承認。**

## 確定した前提
- PR #107をmainにマージ。本人のWindowsローカルテストは435件OKと報告。CIのLinux Repository checksとWindows Python 3.13もsuccess。
- D2の20項目はすべて合成フィクスチャに限る。 `SYNTHETIC_CHECKS_PASS_NEVER_VERIFIED` は実測値の証明ではない。
- 既存デモMT4にはMACD Sampleと既存注文または建玉あり。新規ログイン・新規口座・EX4実行・読取を行わない。独立デモ口座の安全な同時保持に関するG1は未解消。
- `verified_values`はすべてnullを維持し、FORM-01/FORM-03およびPHASE-1をBLOCKEDに保つ。

## スキーマ境界（将来の実装向け）
完全に別のデータ型と名前空間を使い、合成値が観測値を装えないようにする。

1. `synthetic_fixture`: D2のメモリ内合成行。 `origin=SYNTHETIC` に固定。外部ファイルからの受入は禁止。
2. `observation_candidate`: 将来の人間が明示的に許可したローカル手入力候補。 `origin=MANUAL_UNVERIFIED`、取得日時・時区間・対象口座の種類（識別子や個人情報は禁止）・出典画面/取得方法の記述・観測単位・担当者確認の有無を必須とする。欠落はPENDING。**本PRではサンプル値・実ファイルを作成しない。**
3. `broker_verified`: 将来の独立証拠、契約単位、口座通貨、銘柄仕様、timestamp、承認が揃うまで生成不可。人手確認があっても自動昇格しない。

変換は明示的な別工程とし、`synthetic_fixture -> observation_candidate`と`synthetic_fixture -> broker_verified`は常に禁止。生の観測値や口座情報をGitHubに保存しない。

## 5属性の照合上の注意
| 属性 | 単位 | 扱い |
|---|---|---|
| min_lot | lot | 最小数量。ブローカーが定める注文数量の刻み起点は推定しない |
| lot_step | lot | 最小値とステップの大小確認だけでは十分ではない |
| point_quote | quote currency / point | digitsと独立証拠が無ければ未認証 |
| tick_size_points | points / tick | tick価格幅 = point_quote × tick_size_points。pointとtickを同一視しない |
| tick_value_deposit_currency | deposit currency / tick | 口座通貨・1lotの契約数量・通貨換算根拠無しではリスク算出禁止 |

## 失敗時と安全な戻り値
- スキーマの未知・重複フィールド、型不一致、不正なDecimal、timestamp未設定、出典不足、口座通貨・契約単位の欠落、対象銘柄不一致：fail-closed。
- `REVIEW_REQUIRED` > `INCOMPLETE` > `PENDING_EVIDENCE` の順に、安全側の判定を優先。外部入力を例外文やログへ反映しない。
- 診断の戻り値は固定された状態コード・既知の5フィールド名のみ。元の観測値・口座情報・機微メタデータを表示しない。
- 成功しても `MATCHED_OFFLINE_NOT_BROKER_AUTHORIZED` であり、売買承認とは無関係。
- 口座純資産10万円に対する0.5%、1%、1.5%、DD5%などの本番想定リスク規則は、楽天デモ500万円の残高と混ぜない。

## 次PRのための受入テスト案
- 合成origin偽装、未知のorigin、不正な相互変換を拒否。
- 欠損/重複/単位差・銘柄差・通貨差・古い観測時刻・DST境界を拒否、いずれも入力値を出力しない。
- 4通貨ペア×5属性の全観測が記載されても、独立根拠不十分ならUNVERIFIED。
- 認証済みとみなす自動操作は存在しないことを検査。
- 純Python、ネットワークなし、MT4/EAアクセスなし、実口座/秘密情報の読取と書込みなしを静的検査する。
- 仕様からテストへのトレーサビリティとCI Linux Python3.12 / Windows Python3.13を別PRで確認する。

## 禁止操作・承認ゲート
このPRでは取引プログラム、MQL4、MT4、実測値入力、検証器、EA、資格情報、デモ口座、注文を変更しない。実際の照合を含むD4実行は**別途ユーザーの明示承認が必要**。

`terminal_execution_approved=false`、`broker_queried=false`、`orders_generated=false`、`forward_trading_enabled=false`、`human_safety_approval=false`、`PHASE-1 BLOCKED`。
