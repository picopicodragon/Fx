# FWD-273〜284: BLS公式ICSの `TZID=US-Eastern` を限定的に解釈

## 2026-11-12 Windows実測（前工程）

`research.forward_bls_calendar_diagnose` でBLS公式固定URLから80,672バイト（SHA256 `92a350111ace106deaab5584e4084366bd367b594a0d0bad116008d82d63e501`）を取得。文書種別 `VCALENDAR_TEXT`。VEVENT内の `DTSTART` 313件は全て `TZID=US-Eastern`。旧パーサーは `ICS_TIMEZONE_UNSUPPORTED` で fail closed。

## 根拠と限定

- BLSの公式カレンダーは時刻をEastern Timeで示す（https://www.bls.gov/schedule/2026/home.htm）。
- BLSの購読手順に固定ICS URL `https://www.bls.gov/schedule/news_release/bls.ics` が記載（https://www.bls.gov/help/hlpiCAL.htm）。
- RFC 5545は `TZID` がVTIMEZONEを指す文字列であると規定する。非IANA `US-Eastern` をIANAの正式別名とは扱わない。RFC 4791には `TZID:US-Eastern` の例がある。
- 本パーサーはBLS研究専用。**その公開カレンダーを米東部時間として解釈する便宜的かつ未認証の対応**で、未知のTZIDに一般化しない。
- 変更は `_utc` の厳密ホワイトリストへ文字列 `US-Eastern` を追加することのみ。時刻変換は従来の `ZoneInfo("America/New_York")`、DSTギャップ・重複の保守的拒否は変更しない。
- `calendar_timezone_alias_us_eastern_assumed` で限定変換の有無を明記し、`release_time_independently_verified=false` を追加。

## 不変条件

- 不正なTZID表記、floating、日付のみ、存在しない／重複するDST時刻は今後も拒否。
- 公式URLは固定、明示の`--allow-network`、最大350KB、HTTPリダイレクトなし、自動再送なし、結果JSONは新規作成のみ。
- 今回の処理はBLSイベントの研究用保存であり、市場予想値・発表結果・時刻の独立監査・ブローカー時刻を認証しない。BLSだけで全FX重大イベントは網羅しない。
- `NO_GO`、`safety_hold_latched=true`、デモ/本番発注禁止は維持。MT4/EA、価格CSV、AI請求台帳は変更しない。

## 合成テスト

冬の 08:30 ET→13:30Z、夏の08:30 ET→12:30Z、旧 `US/Eastern`・`America/New_York`・Z表記同値、未知TZID・floating・日付のみ拒否、DST gap/fold拒否、異常なTZID付きZ拒否、重複DTSTART拒否、診断による PREFLIGHT/NO_GO、オフラインCLI新規JSON保存と既存データ保護。

実配信の検査はユーザーWindowsの次回実行で確認する。*合成CI成功を運用GOとみなさない*。

## Windows再検査（既存プロジェクトの未コミット変更を維持）

すでに作成済みの別worktree上であれば、`git status --porcelain` が空の場合に限り下記ブランチへ差し替え可能。既存プロジェクト本体の作業ツリーは切り替えない。

```powershell
git fetch origin
git switch --detach origin/fix/fwd-273-284-bls-us-eastern-guarded-parser
$cal = "out/bls_calendar_$(Get-Date -Format yyyyMMdd_HHmmss).json"
python -m research.forward_bls_calendar --allow-network --days-forward 14 --out $cal
```

確認事項：研究用カレンダーを出力できても、実発注許可やフォワードテスト安全ゲートを解除しない。次は抽出したスケジュールと別ソースのBLS公式HTML発表予定との時間・日付照合を行う。
