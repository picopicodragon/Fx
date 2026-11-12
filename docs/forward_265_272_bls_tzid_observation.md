# FWD-265〜272: BLS ICS `DTSTART`タイムゾーン表現の読み取り専用観測

## 実機診断（2026-11-12）

ユーザーWindowsで公式固定URL `https://www.bls.gov/schedule/news_release/bls.ics`へのネットワーク取得が成功し、80,672バイトの `VCALENDAR_TEXT` を確認した。新規保存先の事前検査も成功。厳格パーサーは `ICS_TIMEZONE_UNSUPPORTED` で停止し、通常の収集処理も `FAIL_CLOSED`。この時点では該当 `TZID` の正確な値や日時表記は未確認。

## 追加機能

- 従来の `research.forward_bls_calendar_diagnose` に、失敗原因が `ICS_TIMEZONE_UNSUPPORTED` の場合に限り `dtstart_timezone_observation` を追加。
- `VEVENT` 中の `DTSTART` だけを検査。`VTIMEZONE` 内の標準・夏時間の開始時刻は集計しない。
- 観測対象は `TZID` ラベル、UTC末尾Z、TZIDなしfloating、日付のみ（`VALUE=DATE`）、個数。**実際の発表日時、イベント名、HTTP本文、ローカルのファイルパスは表示しない**。
- ラベルは長さ80以下の安全なASCII文字集合に限定。その他は短いSHA256識別子に置換。20形態まで表示し、残りは件数のみ。
- 解析は既存のICS 350KB上限と行展開規則を流用。未知の表現を勝手にAmerica/New_Yorkへ解釈したり、DST境界を補正したりしない。
- ダウンロードは明示指定時の既存の1回だけ。HTTPポリシー、既存 `forward_bls_calendar.parse_calendar`、最終JSON保存条件は変更しない。
- 既存の114価格CSV、研究ジャーナル、MT4、EA、API課金台帳、発注経路には一切触れない。

## Windowsでの確認

このブランチをローカルに取り込んでから以下を実行する。診断コマンド自体は保存ファイルを作成しない。

```powershell
$cal = "out/bls_calendar_$(Get-Date -Format yyyyMMdd_HHmmss).json"
Test-Path $cal
python -m research.forward_bls_calendar_diagnose `
  --allow-network `
  --days-forward 14 `
  --planned-out $cal
```

成功条件は `dtstart_timezone_observation.forms` を確認できること。これは**原因同定用のメタデータ**であり、ICS取込成功や発表時刻の認証ではない。失敗継続時も再試行の自動化や手動での時刻補正は行わない。

## 次段階

実Windowsで観測された形式を、BLSが公表する発表時刻の定義およびRFC 5545の日時意味論と照合したうえで、限定的なパーサー対応可否を判断する。未定義のfloating時刻は機械的に米東部時刻へ割当てない。

全段階で `NO_GO`、`safety_hold_latched=true`、`demo_orders_permitted=false`、`real_orders_permitted=false` を維持する。
