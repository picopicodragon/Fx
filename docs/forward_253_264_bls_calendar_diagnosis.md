# FWD-253〜264：BLS iCalendarのFail-Closed原因を安全に分類する診断

## 実利用者での状況（2026-11-12）

`python -m research.forward_bls_calendar --allow-network --days-forward 14 --out $cal`が
`BLS_CALENDAR_INVALID_OR_UNAVAILABLE`を返した。出力だけではHTTP取得失敗、ICS構造不一致、
TZID/DST解析、応答サイズ、**同一の出力先が既に存在する**場合を判別できない。

BLS公式ヘルプページは現時点でも`https://www.bls.gov/schedule/news_release/bls.ics`を
iCalendarのURLとして案内している。**実Windows側で受信した内容が正常なICSかはこの記録だけでは不明**。

## 新規の読み取り専用診断 `research.forward_bls_calendar_diagnose`

- 既存`forward_bls_calendar.download`と`parse_calendar`を**変更せずに再利用**する。
- `--allow-network`が明示された場合のみBLS公式URLへのHTTP GETを一回実行。自動リトライ、UA偽装、
  リダイレクト先への追従、外部サービスへの切替は禁止。代わりに`--ics-file`でローカル既存ICSを診断可能。
- `--planned-out`で、**取り込み本体を再実行する前**に出力先が存在するか、親フォルダーがあるかを検査する。
  出力先が不正なら**ネットワークアクセス前に拒否**。この診断は出力先を作成・上書きしない。
- ステージ：`INPUT`/`OUTPUT_PRECHECK`/`FETCH`/`CONTENT_CLASSIFICATION`/`STRICT_PARSE`/`PREFLIGHT`。
- 固定コード：`HTTP_403`、`HTTP_429`、`HTTP_5XX`、`HTTP_REDIRECT_BLOCKED`、
  `NETWORK_DNS_TLS_OR_TIMEOUT`、`ICS_RESPONSE_SIZE_LIMIT`、
  `UNEXPECTED_CALENDAR_ROOT`、`ICS_TIMEZONE_UNSUPPORTED`、
  `ICS_DST_GAP`、`ICS_DST_AMBIGUOUS`、`ICS_EVENT_DATE_OR_TITLE_MISSING`、
  `OUTPUT_PATH_ALREADY_EXISTS`、`OUTPUT_PARENT_NOT_DIRECTORY`ほか。
- `document_class`は先頭の文字を**分類するだけ**。実HTTP本文/例外原文/通信設定/記事名は表示・保存しない。
  SHA256とバイト数は再現の比較用であり、BLS発行物やブローカー時刻の独立認証ではない。
- HTTPエラー・ICS異常・出力先既存があれば常に`BLS_CALENDAR_DIAGNOSTIC_FAIL_CLOSED_NO_GO`。
  正常なICSの厳格解析だけ`BLS_CALENDAR_DIAGNOSTIC_PREFLIGHT_OK_NO_GO`。
- **イベント収集、現有114CSV、ローカルのマクロ研究ジャーナル、AI課金台帳は変更しない。**
  MT4/EA/API/デモ注文/本番注文に接続しない。

## Windowsで実行するコマンド

PR #268を使用する場合、未コミット変更がある場合は先に差分を退避してから以下：

```powershell
cd C:\Users\Suzuki\Documents\ChatGPT\Fx
git fetch origin
git switch --detach origin/fix/fwd-253-264-bls-calendar-diagnostics
```

既存の変数`$cal`が残っている場合、先にその状態を確認：

```powershell
$cal
Test-Path $cal
```

**まずは同じ出力先を指定して診断**（既存ファイルなら通信する前に原因判定）：

```powershell
python -m research.forward_bls_calendar_diagnose --allow-network --days-forward 14 --planned-out $cal
```

出力先が存在していた場合、元ファイルを削除・上書きせず新しい名前を生成し直す。
`$cal = "out/bls_calendar_$(Get-Date -Format yyyyMMdd_HHmmss).json"`

```powershell
python -m research.forward_bls_calendar_diagnose --allow-network --days-forward 14 --planned-out $cal
```

診断成功時のみ元の収集処理を新規ファイルで実行：

```powershell
python -m research.forward_bls_calendar --allow-network --days-forward 14 --out $cal
```

診断と保存は別々のHTTPリクエストなので、配信元が変更された場合には保存結果が異なることがある。
**診断がエラーなら、`stage`・`reason_code`・`document_class`・`body_bytes`だけを共有**し、
根本原因に応じてパーサーを修正する。エラーが`ICS_TIMEZONE_UNSUPPORTED`等なら、
実際のBLS ICS仕様を確認するまで日時を推測せず、UTC変換ルールを緩めない。

## オフライン診断

正規のICSを別経路で取得済みである場合の検査：

```powershell
python -m research.forward_bls_calendar_diagnose --ics-file "out/bls_manually_saved.ics" --days-forward 14
```

この操作は取得済みファイルの検査であって、発表予定の認証やイベント網羅性の証明ではない。

## 安全・受入れ条件

- 追加は診断と合成テストのみ。既存BLSカレンダーパーサーのサイズ・時刻・DST・認証元・1回取得ポリシーを変更しない。
- `NO_GO`、`safety_hold_latched=true`、`real_orders_permitted=false`、
  `demo_orders_permitted=false`を維持。
- 現行の3ペア、114CSV、38完全周期、デモ停止ログの存在、米国指標15分前後停止の設計を変更しない。
