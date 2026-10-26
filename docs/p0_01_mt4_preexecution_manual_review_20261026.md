# P0-01：読取専用MQL4 実行前の端末点検（2026-10-26）

## 0. 到達点と承認範囲

本人のWindows報告：
- `python scripts/audit_mt4_readonly_source.py` は `PASS`。
- `python -m unittest discover -s tests -p "test*.py"` は **409 tests / OK**。
- Git管理MQ4と `Documents/FxLocalReview/CompileOnly` に隔離コピーしたMQ4の SHA-256 は **`PASS: SOURCE_MATCH`**（ハッシュ値自体は回収しない）。
- コンパイル成功は MetaEditor の本人報告 `0 errors, 0 warnings, 291 msec elapsed`。
- `P0_01_ManualSymbolSnapshot_ReadOnly.ex4` は隔離フォルダー内に存在し、**13,644 bytes**、Windows表示の更新日時 **2026/10/26 15:53:36**。
- **EX4のビルド同一性や実端末でのMQL4実行は独立検証されていない**。スクリプトの実行承認・値の取得・発注権限は一切付与されていない。

GitHubにEX4バイナリ、絶対Windowsパスに含まれるユーザー名、完全なWindowsログ、口座ID、パスワード、MQ4の個人改変版を保存しない。

## 1. MT4の手動・表示専用点検（端末でスクリプトを動かさない）

次の表を**目視だけ**で確認する。画面はMT4の**気配値表示 (Market Watch)**。MetaTrader 4では `Ctrl+M` で気配値表示を切り替えられる。[MetaTrader 4公式ヘルプ（Market Watch）](https://www.metatrader4.com/en/trading-platform/help/overview/market_watch)。

| 論理ペア | MQL4ソースの初期銘柄名 | 本人のMT4で見える実銘柄名 | 判定 |
| --- | --- | --- | --- |
| USD/JPY | `USDJPY` | 未確認 | PENDING |
| EUR/JPY | `EURJPY` | 未確認 | PENDING |
| GBP/USD | `GBPUSD` | 未確認 | PENDING |
| AUD/USD | `AUDUSD` | 未確認 | PENDING |

全ての銘柄名について、大文字・数字・接尾辞（例 `.xxx`）を**表示と完全に一致**させて記録する。銘柄名は機密口座識別子ではないが、端末の口座番号/名義や発注履歴と同じ画面をスクリーンショットしない。口座区分は本人が **デモ / 実口座 / 未ログイン / 不明** のカテゴリとして確認するだけとし、番号・サーバー名・認証情報を記録しない。既存EA/スクリプトの自動稼働状態も本人が確認し、既存の口座操作を行わない。

気配値に対象銘柄が見つからなければ **MISSING/PENDING** とだけ記録。現段階で「すべて表示」や「銘柄追加」を実行して環境を変更しない。気配値表示の銘柄をダブルクリックすると注文画面が開く場合があるため、**ダブルクリック、発注ボタン、チャートへのEX4ドラッグを避ける**。

MQL4 の `SYMBOL_SELECT` は「Market Watchで選択扱い」だが、**非表示でもtrueになる銘柄がある**。ソースの `SYMBOL_SELECT` 確認だけでは表示確認にならない。[MQL4 Symbol Properties公式](https://docs.mql4.com/constants/environment_state/marketinfoconstants)。接尾辞を想像して入力しない。

## 2. 接続・停止状態の目視確認

- MT4の画面から「デモ / 実口座 / 未ログイン / 不明」だけ確認。**現段階でログイン/ログアウト/口座切り替えを行わない**。実口座かどうかの区分は次の実行承認設計に重要。画面情報だけで断定できなければ **不明**。
- 端末の接続インジケータは「接続中らしい / 切断 / 不明」という**表示状況のみ**を記録。数値、約定権限、口座取引可能状態を推測しない。
- 実口座/デモ口座に関係なく、EX4は `FxLocalReview/CompileOnly` に置いたままとし、**MQL4/Scripts または Expertsへ移動しない**。AutoTradingボタンの見た目はMQL4の読み取り実行を阻止する保証にはならない。

## 3. ログ出力・個人データの確認

現行ソースには `Print("MT4_RO | ...")` が存在する。実行時には端末がローカルのExperts/Journal系ログへ記録することがある。出力には **銘柄名・5つの数値・観測時刻・結果コード** が含まれ得るが、口座番号やパスワードを取りに行く関数は実装されていない。端末自身の他のログ行まで安全とは断言できない。

実行前のレビューでは、`MT4_RO`を含む行だけを将来どう抽出するか、ローカル保管先とGitHubへのアップロード禁止、個人情報の伏字処理、トラブル時の失効/停止条件を**方針として決めるだけ**。実際のログ/数値を生成しない。

取得値が将来存在しても `OBSERVED_NOT_VERIFIED` に過ぎず、`MODE_TICKVALUE`の口座通貨変換/銘柄契約単位の独立照合まで`FORM-01`/`FORM-03`を実装承認しない。

## 4. 報告フォーマット（機密情報不要）

```text
PRE-EXECUTION MANUAL REVIEW
USDJPY: <表示の正式名称 または MISSING>
EURJPY: <表示の正式名称 または MISSING>
GBPUSD: <表示の正式名称 または MISSING>
AUDUSD: <表示の正式名称 または MISSING>
ACCOUNT TYPE: DEMO / LIVE / NOT_LOGGED_IN / UNKNOWN
CONNECTION DISPLAY: CONNECTED_LIKE / DISCONNECTED / UNKNOWN
SCRIPT/EA RUNNING: NONE_OBSERVED / EXISTS / UNKNOWN
LOCAL MT4 LOG HANDLING: ACKNOWLEDGED / PENDING
```

銘柄名だけは正確な綴りで記録し、**口座番号、ログインID、サーバー名、残高、注文履歴、端末全体のスクリーンショット、MT4のExperts/Journalログ全文を入力・提出しない**。

## 5. 安全判定と未完了

上記の目視確認を行っても **terminal_execution_approved=false**、`terminal_deployed=false`、`broker_queried=false`、`forward_trading_enabled=false`、`implementation_approved=false`、`human_safety_approval=false`、`owner_approved_for_safety=false`、**PHASE-1 BLOCKED**。将来の読取実行は新規の明示承認と独立検証が必要。

独立確認が必要：EX4生成元バイナリ証明、実銘柄名4ペア、端末/口座区分、ローカルログのプライバシー、読取失敗時の動作、ティック価値とポイント/ロット/通貨の整合。トレード/スクリプト起動はこのレビューには含まない。

## 2026-10-26：本人の目視結果と未解消ブロッカー

本人が以下を**MT4気配値表示と端末画面を見た結果として**直接報告：

| 論理ペア | MT4目視の実銘柄名 | スクリプト初期入力 | 結果 |
| --- | --- | --- | --- |
| USD/JPY | `USDJPY` | `USDJPY` | MATCH_BY_OWNER_REPORT |
| EUR/JPY | `EURJPY` | `EURJPY` | MATCH_BY_OWNER_REPORT |
| GBP/USD | `GBPUSD` | `GBPUSD` | MATCH_BY_OWNER_REPORT |
| AUD/USD | `AUDUSD` | `AUDUSD` | MATCH_BY_OWNER_REPORT |

- `ACCOUNT TYPE: DEMO`（本人目視報告であり、口座番号/サーバー名・接続認証は収集しない）。
- `CONNECTION DISPLAY: UNKNOWN`。
- `SCRIPT/EA RUNNING: UNKNOWN`。
- `LOCAL MT4 LOG HANDLING: PENDING`。

**未解消の3ブロッカーに対する次の非実行確認：**

1. 接続表示：MetaTrader 4の「表示」→「ステータスバー」を開き、画面右下の接続インジケータを**目視のみ**。`CONNECTED_LIKE`、`DISCONNECTED`、`UNKNOWN`から選ぶ。メニュー変更以外の再接続・口座変更はしない。インジケータの見た目だけでAPI接続や`IsConnected()`の応答を保証しない。
2. 既存EA・スクリプト：**現在開いている各チャート右上**にEA名/動作アイコンがあるかを見て、`EXISTS` / `NONE_OBSERVED` / `UNKNOWN`で答える。ツールバーの`AutoTrading`をクリックしない。MetaQuotesの資料上、`AutoTrading`を無効にしても**取引以外のスクリプト機能は起動できる**ため、このボタンは誤起動防止策の代用ではない。UI上見えないEAを存在しないと保証しない。
3. ログ保護：今後の`Print()`メッセージはローカル端末のExpertsログ等に残る場合がある。**ログ全文、口座番号、残高、発注記録、認証情報、EX4バイナリはChatGPT/GitHubへ提出しない**。実行が別途承認され、本人が確認する場合も、提出前に必要な`MT4_RO`行を個別に選び口座/識別情報を除去する方針を理解した場合だけ`ACKNOWLEDGED`とする。未確認なら`PENDING`。このレビューでログ自体は生成しない。

MetaQuotes公式：
- [MT4ステータスバー](https://www.metatrader4.com/ja/trading-platform/help/overview/main_menu/main_menu_view)
- [EAのチャート上表示](https://www.metatrader4.com/es/trading-platform/help/autotrading/experts/experts_launch)
- [AutoTradingをオフにしてもスクリプトの実行は防げない](https://www.metatrader4.com/en/trading-platform/help/setup/setup_experts)
- [MQL4 Print](https://docs.mql4.com/common/print)
- [MT4 Expertsログ](https://www.metatrader4.com/pt/trading-platform/help/overview/terminal/terminal_experts)

`terminal_execution_approved=false`、`terminal_deployed=false`、`broker_queried=false`、`implementation_approved=false`、`forward_trading_enabled=false`、**PHASE-1 BLOCKED**維持。

### 次回の報告（機密情報不要）

```text
CONNECTION DISPLAY: CONNECTED_LIKE / DISCONNECTED / UNKNOWN
SCRIPT/EA RUNNING: EXISTS / NONE_OBSERVED / UNKNOWN
LOCAL MT4 LOG HANDLING: ACKNOWLEDGED / PENDING
```

銘柄名・口座区分は上記のとおり記録済みなので、再提出不要。
