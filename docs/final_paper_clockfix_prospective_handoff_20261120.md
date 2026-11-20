# FINAL-PAPER-164〜169：時刻逆転4件の原本固定とV2観測比較

## 2026-11-20 14:01 JST実測

読み取り専用MT4 DEMOの原本CSV3,020件中、strict valid3,016件、
不適合4件（0.132%）。全4原本の不適合はTICK_TIME_AFTER_BROKER_TIME。
USDJPY4件、EURJPY1件、EURUSD0件、最大先行1秒。
NY17観測区分3、90秒超gap14、600秒超gap0、最大連続valid891件。
保存チェーンSHA256：
759374e5043be39ebe14ba3c38512832900895a44921f52d29b859c3838e6ef5

異常原本の日時は2026-11-19 UTCで
03:51:52、05:03:52、19:55:55、20:13:55。
原本のSHA256、ファイル名、順番を変更しない。

ソースコード上は、旧MQL4 EAがTimeCurrentを取得後にMODE_TIMEを検証し、
CSV書き込み時にMODE_TIMEを再取得していたため、tick更新による
TOCTOU競合が有力候補。実際のtick到着順序の独立立証は未達。

## 実装済み

1. MT4候補ソースのOnInit/OnDeinitログに
   FXPAPER-CLOCKFREEZE-20261120-V2 バージョン識別子を追加。
   EAの3通貨時刻キャッシュと確定値のCSV書込はPR #300で修正。
   現Windowsの稼働中EAには未反映。
2. research/final_paper_clockfix_prospective.py：
   保存済み14:01のbaseline報告の件数・NY17集計・4原本SHAを照合し、
   元3,020ファイルの名前+SHA256の全ハッシュ連鎖を再計算。
   欠損・改変・過去への追加はFAIL_CLOSED。
3. オペレーター指定のV2導入UTC時刻以降の元CSVだけを別に走査。
   3通貨bid/ask、atomic capture、broker/tick時刻、契約条件を厳格照合。
   異常数と最初25件の原本SHAを記録して研究停止。
   90秒/600秒gap、NY17日数、未来tick通貨別件数を記録。
4. 120周期かつ2 NY17観測日以上は研究用サンプル量の条件のみ。
   たとえ異常0件でもEAを実機で交換した独立証拠、
   時計の独立証明、スリッページや全イベントは未立証。
   全ての結果はNO_GO、売買も追加課金も許可しない。
5. Windows PowerShell一回の読み取り専用確認コマンドと
   Linux/Windows全件回帰テストを追加。

## V2を実機導入する前の有人確認

- 現MT4はデモ、USDJPY H1、EA1個、AutoTrading OFF、
  注文タブが空であることを確認。
- 旧EAの停止、旧source/EX4とExpertsログの保全、意図的な
  価格CSV中断、MetaEditorの候補版MQL4手動コンパイル0 errors、
  新EAを1個だけデモ端末へ接続する計画は別途本人承認が必要。
- 新EAの起動ログに上記build tagがあることを見届け、
  実際の開始UTC時刻を保存。二重EA/二重Python supervisorは禁止。
- 現行Python監視・通信ラッチは自動変更しない。
- GitHub Python CIはMetaEditor/MQL4コンパイルと同義でない。

## 将来、実機の切替後にだけ実行する読み取り専用検査

    .\scripts\final_paper_clockfix_prospective_once.ps1 -Mt4FilesDirectory $mt4Files -CutoverUtc <実際のEA起動日時のISO8601 UTC文字列>

上記の時刻は自動生成しない。未切替時の実行は導入後検証にならない。

## 安全方針

通信停止ラッチ未解除。AI6/6消費済み。重要イベント・事前consensus、
独立時刻認証、約定コスト証明、新規AI判断未完。
新規仮想エントリー、ブローカーdemo/real発注、課金API追加利用は禁止。
mainマージには人間承認が必要。
