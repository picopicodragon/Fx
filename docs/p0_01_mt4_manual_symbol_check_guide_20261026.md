# P0-01：MT4「気配値 → 仕様」の読取専用・手動確認手順

> 2026-10-26に楽天証券とMetaQuotesの公開資料を確認したが、**ユーザーのMT4端末の実値はまだ取得していない**。この手順はMT4の画面に表示された数値だけを人間が読取り、Gitリポジトリ外で保管するもの。**EA、MQL4スクリプト、ログイン自動化、発注・注文変更、API接続は行わない。**

公式参照：
- [楽天MT4公式取引ルール](https://www.rakuten-sec.co.jp/web/fx/mt4/rule.html)
- [MetaTrader 4のContract Specification](https://www.metatrader4.com/en/trading-platform/help/service/symbol_spec)
- [MetaQuotes MQL4 Symbol Properties](https://docs.mql4.com/constants/environment_state/marketinfoconstants)

## 1. 端末で見る場所

MT4が**インストールされていて、画面の確認が可能な状態になった場合のみ**、以下を実施する。インストール/ログインしていない段階では**未確認のままでよい**。認証情報・口座番号は本プロジェクトのGitHubに書かない。

1. MT4のメニュー「表示」→「気配値表示（Market Watch）」を開く（標準ショートカット`Ctrl+M`）。
2. 対象通貨ペア`USD/JPY`、`EUR/JPY`、`GBP/USD`、`AUD/USD`を順番に選ぶ。MT4内の実際のシンボル名に接尾辞・表示の差があれば、強制的に同一と決めつけず別途照合する。
3. シンボルの右クリックから「仕様（Specification）」を開く。**「新規注文」「売り」「買い」「ワンクリック注文」は触れない。**
4. 画面で実際に確認できる項目だけを、リポジトリ外のJSONに手入力する。表示されない属性は`null`のままにする。数字は例`"0.01"`のような**文字列**にする（浮動小数点の四捨五入を避けるため）。
5. 取得した値の照合は**ローカルのオフラインスクリプトのみ**で行い、個別の本人承認や本番注文へつながる操作はしない。

画面に表示される項目とMQL4 APIの`MODE_*`列挙は完全には一致しない。特に`MODE_TICKVALUE`、`MODE_TIME`、`MODE_BID`/ `MODE_ASK`等を画面から読めないなら**空欄のまま**にする。**画面上の値を推測したり、スクリーンショットにある口座情報をGitHubに送ったりしない。**

## 2. 入力先は必ずGitの外

`specs/p0_01_mt4_manual_symbol_template.json`は**全て未入力（null）の公開テンプレート**。実際の観測結果をGitHubにコミットしない。WindowsのFxリポジトリルートから以下を実行する。

```powershell
$reviewDir = Join-Path $env:USERPROFILE "Documents\FxLocalReview"
New-Item -ItemType Directory -Force -Path $reviewDir | Out-Null
$reviewFile = Join-Path $reviewDir "mt4_symbols_local.json"
if (-not (Test-Path $reviewFile)) {
    Copy-Item .\specs\p0_01_mt4_manual_symbol_template.json $reviewFile
}
notepad $reviewFile
python scripts/validate_mt4_manual_symbol_specs.py --input $reviewFile
```

既存の観測ファイルがある場合は、条件分岐により**上書きしない**。観測の再入力や更新は本人の意思によるものとする。

本スクリプトはローカルファイルを読み取り、本人が入力した**数値を表示せずに**、`INCOMPLETE`/ `REVIEW_REQUIRED`/ `COMPARED_FIELDS_ONLY`と該当フィールド名だけを表示する。原本や口座情報をGitHubに転送せず、ブローカーに接続せず、ファイルを書き換えない。

| 状態 | 意味 | 終了コード |
|---|---|---:|
| `INCOMPLETE` | 必須比較項目が`null`または未確認 | 2 |
| `REVIEW_REQUIRED` | 数値の不正や、公開ルールとの差・矛盾がある | 1 |
| `COMPARED_FIELDS_ONLY` | **入力された一部の数値**の形式と公開ルールへの整合のみを確認 | 0 |

終了コード0でも**口座契約の真正性、価格の新鮮さ、約定損失換算の正しさ、SL制限の最終確認や本番取引の可否を証明しない**。価格・ティック値やスプレッドは取引条件や時間帯等で変動し得る。実際のMQL4 APIの読取が必要になる項目は`FORM-01`/`FORM-03`の後続の個別計画で判断する。

## 3. 対応するフィールドの区別

| JSON項目 | 対応する概念 | 注意 |
|---|---|---|
| `lot_size_base_units` | `MODE_LOTSIZE`、1ロットの通貨数量 | 公開説明：100,000通貨 |
| `min_lot`, `lot_step`, `max_lot` | `MODE_MINLOT`/ `MODE_LOTSTEP`/ `MODE_MAXLOT` | 公開の0.01ロットを端末へ無条件に推測入力しない |
| `point_quote`, `digits` | `MODE_POINT`/ `MODE_DIGITS` | 円建て0.001、USD建て0.00001が公開説明 |
| `tick_size_points` | `MODE_TICKSIZE` | **ポイント単位**でのティック幅。価格値との混同禁止 |
| `tick_value_deposit_currency` | `MODE_TICKVALUE` | 口座通貨建てのAPI項目。画面にない場合は`null` |
| `stop_level_points` | `MODE_STOPLEVEL` | 0でも**動的な停止価格制限がある可能性** |
| `freeze_level_points` | `MODE_FREEZELEVEL` | 決済/変更に制限があり得る |
| `spread_points` | `MODE_SPREAD` | **観測した時点の動的な値**。過去値を恒久的契約値にしない |

この資料は**入力済みデータを自動提出する運用にはしない**。次工程では非機密の観測結果の本人要約に基づき、契約単位・円換算・最小ロットが0.5%想定損失限度を満たし得るかを、独立した数学的/技術的テストで比較する。

**安全状態不変：** `forward_trading_enabled=false`、`implementation_approved=false`、`human_safety_approval=false`、`owner_approved_for_safety=false`、PHASE-1 BLOCKED。**ライブ注文・注文の安全許可は与えない。**
