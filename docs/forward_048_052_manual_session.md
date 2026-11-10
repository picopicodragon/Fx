# FX-FWD-048〜052：実デモ観測への移行前、安全な手動観測系列の統合監査

## 目的

これまでのFWD-043〜047では、楽天MT4から手動で取り出したCSVを個別にSHA-256で保全できる。今回の工程はその**複数の観測フォルダーを時系列で監査**し、MT4エクスポートのMQL4ソースとPythonのCSV受入仕様を突合する。実際の楽天MT4やWindows実機はこのGitHub開発工程から操作しない。

| 工程 | 実装 | 限界 |
| --- | --- | --- |
| FWD-048 | `research.forward_manual_session`で既存の手動観測フォルダーを1,500件以内に限定して検査 | 手動生成されたローカルデータのみ |
| FWD-049 | USD/JPY、EUR/JPY、EUR/USDのペア別時刻・観測間隔・重複/再利用を監査 | ティックサーバー時刻は未認証 |
| FWD-050 | 60秒でLEVEL1、600秒でLEVEL2、欠損はLEVEL2。途中5分超のギャップとリプレイを列挙 | 実時刻監視ではなく保存済みデータの研究用診断 |
| FWD-051 | `research.forward_mt4_source_contract`でMQL4の出力ヘッダー・DEMOガードとPythonインポーターの契約の静的整合性を評価 | MQL4コンパイルや実行ではない |
| FWD-052 | Windows PowerShellでの手動単発実行のスクリプト・回帰試験・運用手順 | Windows実機の動作確認やタスク登録は未実施 |

## 実行方法

まずFWD-043で観測フォルダーを手動生成する。元のCSVには口座番号や秘密鍵を入れない。既存デモMT4は**単一端末、単一セッションのみ**。未承認のMQL4を有効化せず、AutoTradingはOFFのままにする。

例として`out/mt4captures`の直下に`manual_001`、`manual_002`などのFWD-043生成フォルダーが存在する場合、以下のマニフェストを用意する。あらかじめ作成していないファイルを捏造しない。

```json
{
  "schema": "fx_forward_manual_session_v1",
  "capture_folders": ["manual_001", "manual_002", "manual_003"]
}
```

Windows PowerShellから：

```powershell
.\scripts\forward_manual_session_once.ps1 `
  -CapturesDir "out/mt4captures" `
  -Manifest "out/manual_session_manifest.json" `
  -AsOfUtc "2026-11-10T03:05:00Z" `
  -SessionReport "out/manual_session_result_001.json" `
  -Mql4Source "research/mt4_readonly/FxForwardReadOnlyQuote.mq4" `
  -SourceReport "out/mt4_source_contract_001.json"
```

日付は**構文例**。実行時にはローカルで観測した実際の現在UTCを用い、古い観測を現在値として扱わない。どの出力も既存ファイルの上書きを禁止。エラーになった場合、発注の再開・自動再試行・デモ口座追加を実施しない。

## 重要な未解決の実機条件

1. 既存MQL4スクリプトでは`TimeGMT()`によりコンピューター側のUTC時刻を出力する。**楽天証券MT4サーバーの最終ティック時刻ではない**。価格が同じでも正確な更新鮮度の証明にはならない。今後のMQL4設計改善、MetaEditorコンパイル、実ティックと時刻の照合が必要。
2. 実際の楽天MT4 MetaEditorのコンパイル結果、権限、書出しフォルダー、通貨ペア名、デモ口座認証は取得していない。
3. 3ペアが揃い観測間隔が短くても、取引許可にはならない。データ源の利用条件、配信品質、独立時計、実口座純資産、発注安全性、経済カレンダー網羅は未認定。
4. このスクリプトは**ローカルファイルの単発監査**である。Windows上の24時間監視、スケジューラー/サービス常駐、故障時の自動復帰は実装しない。

安全条件：`runtime_go_no_go=NO_GO`、`safety_hold_latched=true`、`real_orders_permitted=false`、`demo_order_execution_enabled=false`。デモ・本番の注文処理には接続しない。

次の真正の実機工程では、ユーザーPCの既存楽天デモMT4で、**読み取り専用MQL4ソースの監査・手動コンパイルと単発エクスポート結果**を検証する。CI成功だけでこれを完了扱いしない。
