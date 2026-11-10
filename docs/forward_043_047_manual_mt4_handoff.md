# FX-FWD-043〜047：楽天MT4デモの読み取り専用CSV受け渡し準備

## 目的と完成範囲

従来のオフライン監査基盤に、**利用者があらかじめMT4から出力したCSVを明示的に指定し、ローカルの監査用フォルダーに証拠として不変保存する仕組み**を追加した。実機との接続や端末の自動起動、注文は禁止。

| 工程 | 内容 | 到達レベル |
| --- | --- | --- |
| FWD-043 | MT4の手動CSVファイルを利用者指定のパスから読み取り専用検査 | ソースコード完成、実機未検証 |
| FWD-044 | 新規フォルダーへ `quote.csv` とSHA-256監査 `receipt.json` を保存し、検証し直す | オフライン実装完了 |
| FWD-045 | USD/JPY・EUR/JPY・EUR/USDの手動3ペアを照合。欠損、重複、古いレートを安全保留 | オフライン実装完了 |
| FWD-046 | 証拠に取引指示・許可を含めず、出典、時計、価格の独立検証未達を明示 | オフライン実装完了 |
| FWD-047 | Windows PowerShellの単発手動受け渡しスクリプトと回帰テスト | GitHub ActionsでPythonテストのみ検証、実機未検証 |

## Windowsでの操作手順

1. **既存の楽天MT4デモ口座のみ**で実施。追加デモ口座や並行ログイン端末を作らない。AutoTradingはOFFのまま。未承認のスクリプトをいきなり実行しない。
2. 既存の `research/mt4_readonly/FxForwardReadOnlyQuote.mq4` は実行権限を持つMetaEditor用ソースであり、現段階でコンパイル済み・実機で安全確認済みではない。ソースを目視監査し、公式MT4のデモ口座接続状態とチャート対象ペアを確認してから、**利用者が別途承認する時点**でのみ実機試験する。既存CSVがある場合はそれを使い、新たなMT4操作は不要。
3. MT4の `ファイル → データフォルダを開く` から `MQL4/Files/FxForwardReadOnlyQuote.csv` のパスを確認する。これはファイルの場所の調べ方であり、本プログラムはデータフォルダーの自動探索を行わない。**このCSVに口座番号・パスワード等を含めない**。
4. Windows PowerShellの単発ランチャーを使用。以下は**ファイル名の構文例**。実際のデータフォルダーのパスは確認したものを使う。

```powershell
.\scripts\forward_manual_mt4_handoff_once.ps1 `
  -SourceCsv "C:\Path\To\MT4\MQL4\Files\FxForwardReadOnlyQuote.csv" `
  -CaptureId "manual_001" `
  -CaptureDirectory "out\manual_001"
```

この操作は、元CSVを書き換えず新規フォルダーに証拠を保存する。CSVの時刻がローカルUTC時刻と90秒以上ずれている、スプレッドが不正、ペア識別が不正、宛先フォルダーが存在する等の場合は失敗する。すでに保存されたファイルの上書き・暗黙の再試行はしない。

3ペアの別々のフォルダーが揃った場合の照合例：

```powershell
python -m research.forward_manual_three_pair `
  --capture-dir out/manual_001 `
  --capture-dir out/manual_002 `
  --capture-dir out/manual_003 `
  --asof-utc 2026-11-10T03:00:00Z `
  --out out/manual_three_pair_audit_001.json
```

`--asof-utc`は**実際の観測・監査時点UTC**を指定する。上の日時は構文例であり、実測値ではない。実行時刻を偽って過去データを新しいレートとみなさない。JPY換算係数は既存CSVの自己申告値であり、正式なロット計算・損失計算への利用を許可しない。

## 現時点の明確な未完了事項

- 楽天MT4でMetaEditorコンパイル、手動読み取り専用スクリプト実行および実レートCSV作成を実証したわけではない。
- 現状のMQL4はスクリプトのため**手動での一回限りの出力**であり、24時間の自動レート配信は未実装。
- この段階のコードは、自動的にMT4のフォルダーをスキャンしない。監視停止後に勝手に再開しない。外部ネットワークやAI課金APIを呼び出さない。
- 手元のCSVに `DEMO` と書かれていても口座種別認証、価格配信の真正性、時計独立証明、約定品質、出典の利用権限、リスクエンジンの本番適用は認定されない。
- `NO_GO`、`safety_hold_latched=true`、`real_orders_permitted=false`、デモ発注無効は維持する。注文APIや自動売買を一切追加しない。

**次に実機側で必要な作業**は、既存デモMT4の同一セッションを使ったMetaEditorコンパイル・一方向CSV書出しの目視安全確認であり、CIの通過だけで実施済みと扱わない。
