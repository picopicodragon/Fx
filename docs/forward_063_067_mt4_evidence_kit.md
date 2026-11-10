# FX-FWD-063〜067：楽天MT4読み取り専用・実機試験前の証拠受入キット

## 工程と実証範囲
正式通貨ペアは**USD/JPY、EUR/JPY、EUR/USDの3ペアのみ**。2026-11-10再確認済み。既存の単一デモ口座と単一MT4環境を維持し、同時ログイン・別デモ口座の開設をしない。

| 工程 | 今回の実装 | 完了と扱えない事項 |
| --- | --- | --- |
| FWD-063 | `research.forward_metaeditor_evidence`：コンパイル自己申告の有効性・件数とMQL4ソースSHA256を照合 | 実MetaEditorのコンパイル・実機での動作 |
| FWD-064 | コンパイル未実行／報告成功／報告失敗を分離。成功申告でも`metaeditor_compilation_independently_verified=false` | 申告の真正性、画面確認・EX4バイナリ |
| FWD-065 | `research.forward_mt4_v2_series`：複数のv2手動CSVをオフライン監査。3ペア別の欠損と複製検知 | 本物のレート供給、完全なティック履歴 |
| FWD-066 | Windowsの観測UTCとサーバーローカル時計の**経過率**を比較。サーバー時計停止、逆転、時刻の重複、ギャップを診断 | 独立時計/サーバー時刻のUTC変換、時刻認証 |
| FWD-067 | `scripts/forward_mt4_evidence_once.ps1`、障害再現テスト、実機受入用書式・操作範囲を整理 | ユーザーPCでのWindowsスクリプト実行・長時間監視 |

### 事前に用意するソース付きコンパイル申告書
手動で作成するJSONの**形式例**。実際のエビデンスを偽造しない。元ファイルのSHA256はPowerShellで `(Get-FileHash <file> -Algorithm SHA256).Hash.ToLowerInvariant()` により確認できる。以下の`source_sha256`は説明用表記のため利用時は実ファイルの64桁SHA256と差し替える。

```json
{
  "schema": "fx_forward_metaeditor_evidence_v1",
  "captured_at_utc": "2026-11-10T03:15:00Z",
  "compiler_status": "NOT_RUN",
  "source_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "reported_error_count": 0,
  "reported_warning_count": 0,
  "operator_environment": "WINDOWS_MANUAL",
  "account_type_reported": "DEMO",
  "mt4_script_executed": false
}
```

`compiler_status=REPORTED_SUCCESS`の場合も、自己申告であり独立検証済とは判定しない。コンパイルを行ったかのようなデータは生成しない。スクリプトの実機コンパイル・配置・実行は**この工程では実施しない**。

### 既存ファイルの手動単発監査（Windows）
```powershell
.\scripts\forward_mt4_evidence_once.ps1 `
  -Mql4Source research/mt4_readonly/FxForwardReadOnlyQuoteV2.mq4 `
  -CompilerManifest out/metaeditor_manual_record.json `
  -CompilerReport out/metaeditor_evidence_001.json `
  -QuoteCsvs @("out/v2_001.csv","out/v2_002.csv","out/v2_003.csv") `
  -AsOfUtc "2026-11-10T03:15:00Z" `
  -SeriesReport out/mt4_v2_series_001.json
```
ファイルがない場合は停止。時刻は**形式例**であり実測値として使用しない。既存出力ファイルは上書きしない。CSVが過去のものでも履歴診断できるが、過去の価格を現在の価格とみなさない。価格鮮度を断定しない。正常なローカルCSVとコンパイル自己申告が揃っても発注許可にはならない。

## 独立した実機ゲート（未完了）
1. 楽天MT4の既存デモ口座で、`AutoTrading=OFF`、余分なEA停止、口座種別・接続状態を画面で確認する
2. MQL4ソース静的レビューを維持し、MetaEditorによる実コンパイル結果、出力ファイル、明示的な実機操作記録を**人間が**確認する
3. v2の`TimeGMT()`はPC時計由来、`MODE_TIME`/ `TimeCurrent()`はサーバー内時計。時刻の差分は両者が止まる場合に完全な鮮度を保証しない
4. 独立時計、レートの第三者照合、契約属性3×5=15項目、経済指標の出典、G1〜G9・FX-SAF・ストレス/相関リスクを安全ゲートとして保持する

**常時`NO_GO`、`safety_hold_latched=true`、`real_orders_permitted=false`、デモ発注無効。** 研究用監査プログラムがOSタスク・MT4スクリプト・ブローカー注文を起動しない。
