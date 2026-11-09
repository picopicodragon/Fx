# FX-FWD-007〜010：公式RSS観測、研究AIシャドー評価、継続可能な仮想再生、MT4デモ手動見積

## 状態

- **実装対象**：公開RSSの明示的ネットワーク取得、事前予想値を補完せずイベント記録、OpenAI主推論+別モデルIDの独立反証の明示API呼出、局所記録への安全な出版、仮想品質/損益の繰り返し監査、手動MT4デモ価格CSV入力
- **未実装・未確認**：経済カレンダーの完全な未来予定、BLS/ECB/日銀等すべてのソース、独立した情報真正性認証、契約審査、OpenAI API費用上限の自動円換算、レートライブストリーム、EAからの一方向自動出力、本番相当の口座照合、MT4デモの実注文、24時間のWindows常駐プロセス。これらの未検証を隠さない。
- **不変**：`runtime_go_no_go=NO_GO`、`safety_hold_latched=true`、`real_orders_permitted=false`。外部APIの応答や仮想収益がどんな内容でも、EA/MT4/証券口座へ注文を出さない。

## 1. 公的RSSソースの範囲

`research/forward_rss.py` は、固定されたHTTPS公開RSSのみを取得し、XMLサイズ256KB、応答12秒、最大30記事を上限とする。追加先URL・ホスト・ポートを自由入力できず、リダイレクトとDTD/ENTITYを拒否する。

| キー | 取得先 | 根拠 |
|---|---|---|
| `bls_empsit` | `https://www.bls.gov/feed/empsit.rss` | [BLS公式RSS一覧](https://www.bls.gov/feed/) |
| `bls_cpi` | `https://www.bls.gov/feed/cpi.rss` | [BLS公式RSS一覧](https://www.bls.gov/feed/) |
| `fed_policy` | `https://www.federalreserve.gov/feeds/press_monetary.xml` | [FRB公式RSS一覧](https://www.federalreserve.gov/feeds/feeds.htm) |

RSSが提供するのは公開済み記事のタイトル/要約/リンク/配信側公表時刻。**速報に先行するコンセンサスや値、配信時刻の保証、FXに直接対応するイベント重要度などは提供しない**。ゆえに`market_expectation`/観測実績を空欄で記録する。受領UTCとRSS発表UTCを分離し、24時間を超えた既知の記事は新しいリアルタイム事象として追加しない。同じ記事URLは再登録しない。

**重要**：実際のRSS応答を取れたとしても、その内容が市場価格として有効/公式確認済みとみなさない。`USER_SUPPLIED_UNVERIFIED`の信用階層を維持。BLS/FRBの接続・利用ポリシー、robots、アクセス頻度は実運用前に確認する。大量ポーリングは禁止。コネクションエラー・サイトのRSS仕様変更・URL変化はFail Closed。

### 公式RSSの明示的1回取得（オプトイン）

```powershell
cd C:\Users\Suzuki\Documents\ChatGPT\Fx
git fetch origin
git switch --detach origin/feat/forward-official-feeds-shadow-monitor
python -m unittest discover -s tests -p "test*.py"

# FWD-01既存セッションを利用、新しい出力先を勝手に上書きしない
python -m research.forward_rss `
  --store out/forward_observation_20261109 `
  --feed bls_empsit `
  --allow-network `
  --max-new 3
```

異なるRSSは`--feed bls_cpi`または`--feed fed_policy`。3件を超える記事が追加対象になる場合は課金/注文はないが明示値`--max-new 5`を指定し再実行する。一般的な利用では新着0件が正常。BLSが403やフィード仕様不一致を返す場合は安全に停止し、URLや認証を勝手に迂回しない。

### ネット接続なしのRSS動作確認

```powershell
python -m research.forward_rss `
  --store out/forward_observation_20261109 `
  --feed bls_empsit `
  --xml-file out/official_rss_fixture.xml
```

`official_rss_fixture.xml`は別途自分で入手・作成したファイルのみを入力する。CLIが架空の公式結果を生成することはない。

## 2. 人工ではないニュースからAIを研究評価する（有料・明示実行のみ）

`research/forward_ai_shadow.py`は、FWD-01に既に保存した1件のマクロイベントを指定し、`ResearchRoleRegistry`の既存主推論AI/独立反証AI（異なるモデルID）を2回で実行する。予算Q91/Q100各3,000円を自動制限するコードではないため、**請求とモデル選択を事前に確認すること**。補助AI v1/v2を本番承認済みとみなして接続しない。

初期化/読むだけ（無料）：

```powershell
# 監査済みイベントのrecord_sha256を特定して設定
$eventHash = "<64桁のマクロイベントレコードのhash>"

python -m research.forward_ai_shadow `
  --store out/forward_observation_20261109 `
  --event-sha256 $eventHash `
  --ledger out/forward_ai_shadow_001.json `
  --analyst-model "<実際に使用できる主推論モデルID>" `
  --reviewer-model "<別の実際に使用できるモデルID>"
```

この操作は1回目では台帳だけ作成し、請求0件。

必要に応じ有料AIを最大1回または2回だけ実行する。**今までの2025年研究と同様、曖昧な失敗後の自動再課金禁止**。

```powershell
python -m research.forward_ai_shadow `
  --store out/forward_observation_20261109 `
  --event-sha256 $eventHash `
  --ledger out/forward_ai_shadow_001.json `
  --analyst-model "<主推論モデルID>" `
  --reviewer-model "<別モデルID>" `
  --max-api-calls 1 `
  --allow-external-api
```

2回目は同じコマンドで`--max-api-calls 1`。成功済みの呼出は台帳から再利用し、再送しない。OpenAIの`OPENAI_API_KEY`が環境変数に必要。

完了後、**無料で**両判断をFWD-01観測記録へ発行（独立した操作）：

```powershell
python -m research.forward_ai_shadow `
  --store out/forward_observation_20261109 `
  --event-sha256 $eventHash `
  --ledger out/forward_ai_shadow_001.json `
  --analyst-model "<主推論モデルID>" `
  --reviewer-model "<別モデルID>" `
  --publish-offline
```

公開操作も記録状態を事前に`pending_request=publish`へ変更し、異常で中断した場合は人間によるローカルジャーナル照合が必要となる。単純に保留マーカーを削除・API呼び出しを再送しない。

**AI判断はデモ発注の指示ではない**。回答がAPPROVEDでも`research_only=true`であり、実ロット発注は禁止。

## 3. MT4デモ手動価格ファイルの安全な受け入れ

現時点では既存のMT4環境から自動でデータを抽出するEAは**未作成**。ユーザーが手動で保存したCSVの唯一の1行を検査する。必須列順：

```csv
observed_at_utc,pair,bid,ask,quote_to_jpy,account_type,origin
2026-11-10T08:00:00Z,USD/JPY,150.000,150.010,1,DEMO,MANUAL_MT4_DEMO_EXPORT_UNVERIFIED
```

値はあくまで**形式説明用の架空例**。観測UTCを実時刻に合わせる。90秒を超える古い価格、未来価格、bid>=ask、DEMO以外、未知の3ペア、口座番号など余計な列は拒否。

```powershell
python -m research.forward_mt4_quote_import `
  --store out/forward_observation_20261109 `
  --csv out/mt4_demo_quote_export.csv
```

デモ申告値の信頼性は証明されず、MT4接続/約定処理は行わない。

## 4. 日次/分次の「一回だけ」品質・仮想損益検証

`research/forward_shadow_cycle.py`は完全オフラインでFWD-01ジャーナルを検証したうえで、品質レポートと研究シナリオの仮想再生結果を**1回**生成する。

```powershell
python -m research.forward_shadow_cycle `
  --store out/forward_observation_20261109 `
  --out-dir out `
  --cycle-id shadow_20261110_170000 `
  --scenario out/paper_plan_20261110.json
```

`--cycle-id`は毎回新しい値を指定。既存の同一IDは上書きしない。Windowsタスクスケジューラ等で定期的にコマンドを起動することは可能だが、**当コードは自身で常駐せず、実行予定の登録も行わない**。観測ジャーナルが空/ニュースのみなら仮想ポジションなしで正常、実際のトレードが成立した意味ではない。データ取得、AI判断、仮想損益は無関係な失敗でも次の自動発注を開始しない。

## 安全な進捗管理

| 工程 | 今回の進展 | なお必要な工程 |
|---|---|---|
| FWD-02 | BLS雇用統計/CPI、FRB金融政策RSSの個別明示取得と保管 | 利用規約/配信安定性、他国ニュース、将来のカレンダー、予想値、実時間価格配信 |
| FWD-03 | 公表/受領時刻と既存品質監査へRSS情報を接続 | 速報から約定可能なデータ品質保証、イベント予告 |
| FWD-04 | 明示API権限付き主推論+別モデルIDレビュー、課金ジャーナルと観測記録発行 | 実データ真正性の独立検証、予算連動停止、自動スケジューラ |
| FWD-05 | 1回ごとの品質/仮想損益レポート、複数回実行で観測履歴を蓄積 | 多時点・複数ポジション、日次1.5%/DD5%、約定/SL/取引時間の検証 |
| FWD-06 | MT4手動状態・1行気配CSVのローカル読込 | 実デモ口座を認証した読み取り専用EA/IPCと照合 |
| FWD-07 | **実装せず** | 既存Safety Gate、MT4デモ専用の新規実行権限と人間承認 |
| FWD-08 | **未承認** | Q110正式モジュール/フェーズ受入 |

新機能によってユーザーの既存楽天MT4でEAを実行させない。デモ注文は既存のNO_GOとは別の安全審査が完了しない限り無効。


## 5. FWD-06B：MT4デモからの一方向・読み取り専用ファイル出力のソースを用意

`research/mt4_readonly/FxForwardReadOnlyQuote.mq4`を追加した。これは**MQL4スクリプトのソースコードだけ**であり、CIにMetaEditorのコンパイラがなく、コンパイル/楽天MT4での実動作は**未検証**。自動ロードやEA起動は行わない。既存のデモMT4を別PCへ多重ログインしたり、新しい口座を追加することは要求しない。

後に本人がローカルのMT4に明示的に導入する場合、手順の要点は以下のとおり。

1. **既存デモの環境が正しいことを画面で確認**し、取引タブの既存建玉・未約定注文、別EA/スクリプト稼働、AutoTrading状態を先に確認する。AutoTradingはOFFのまま。スクリプトは`IsDemo()`かつ`IsConnected()`を確認できなければ何もしない。
2. MetaEditorを使用してソースを**一度だけ手動コンパイル**し、USDJPY/EURJPY/EURUSDのいずれかのチャートに**本人の操作で一度だけ**配置する。取引、注文、ポジション変更APIはソースに含まれないが、動作未検証のため初回に実MT4へ適用する前にはソース・コンパイル結果のレビューが必要。
3. 出力ファイル`MQL4/Files/FxForwardReadOnlyQuote.csv`を端末で確認し、`research.forward_mt4_quote_import`へ`--csv`で渡す。内容をChatGPTへ送信する必要はない。
4. `TimeGMT()`は**PC時刻に由来**し、ブローカーのtickの正しい受信時刻を保証しない。USD/JPY、EUR/JPYの円換算=1、EUR/USDはUSDJPY BIDを研究上の概算として参照。配信鮮度/スプレッド/換算同時性/営業許可の証明にはならない。

**導入を自動化しない**：実MT4に対するコンパイル/配置/スクリプト実行は本PRでは行っていない。例外として必要なレビューが済むまで、研究用の手動CSVを優先する。本人の明示的なデモ実行承認が別途必要な注文プログラムではないものの、MT4の実稼働環境への変更はこの段階では避ける。


## 6. FWD-02B：BLS公式の今後の発表予定（ICS）の研究用監視

公式BLSは[発表予定のオンラインカレンダー](https://www.bls.gov/schedule/news_release/empsit.htm)から`https://www.bls.gov/schedule/news_release/bls.ics`を案内している。RSSは過去/公開済み記事しか扱えないため、**将来の重要イベント時刻の見落としに備えて別のICSスナップショット**を実装。

`research/forward_bls_calendar.py`：明示`--allow-network`時に固定URLから1回だけ取得、350KB以下、12秒上限、リダイレクト禁止。ISO UTCまたは`America/New_York`の現地時刻を夏時間込みでUTCへ変換、DST非存在/重複時間帯、欠落日付や長大入力は拒否。最大31日/500件の範囲だけを保存し、発表予定の±15分を`imminent_research_event_halt_suggested`として報告。情報が発表延期・日時変更された場合、このスナップショット単独では検知できない。

```powershell
python -m research.forward_bls_calendar `
  --out out/bls_calendar_20261110.json `
  --allow-network `
  --days-forward 14
```

このコマンドは**市場データを自動取得せず、取引を停止/再開する既存の安全ゲートに直接接続しない**。ICSの将来予定はBLS対象のみであり、FOMC、ECB、日銀、他国データを網羅しない。信用レベル`PUBLISHED_SCHEDULE_UNVERIFIED`であり、出典/更新時刻・実際の発表・予想値の確認は別ゲート。レポートが「予定なし」でも、新規売買許可にはならない。
