# FINAL-AUTO：AI判断・安全ゲート・仮想実行・円予算の最終統合

2026-11-20、GitHubソースとCI用。稼働中のWindows/Rakuten MT4 DEMO
および既存Python監視は変更しない。人間承認・現場切替・追加課金未実施。

## 一括実装

- MT4の3通貨の実CSV / 120本H1 / 公式ニュース → マクロ分析AI →
  別モデルの検証AI → 次の実価格周期でのみ仮想売買する。
- 旧10万円仮想資金、単一0.5%、合計1%、日次1.5%、
  DD4%新規停止、DD5%全仮想決済、人間承認を維持。
- 米/EU/日銀の高重要イベント前後15分は新規停止。
  不完全calendar、不正consensus、時計異常、spread拡大、
  未認証MT4 V2、期限切れ証拠なら新規AIとエントリーを禁止。
- 保守的swap JPY/lot/dayをLONG/SHORT別に予約し、
  最大14暦日のcarry費用を新規建玉リスクに含む。
  NY17日替り時には仮想cashから保守的swapを控除。
  14日で仮想強制決済。実際のbroker約定原価の保証ではない。
- 旧AI6/6は維持。新しい2モデルの有料推論は、
  独立した本人承認、別のJPY予約journal、モデル別料金原本が必要。
  月額の新予約上限は3000JPY以下。
- API送信前に2件分の予約をexclusive create+fsync。
  応答/請求不明は自動再試行なし。完成台帳とpacket SHA一致時のみ
  SETTLEDを記録。paper journalとの照合失敗は新規停止。
- 元の価格観測モードは既存のまま。新モードは専用CLI明示選択。
  brokerへの注文送信機能は一切追加しない。

## 現在の実機証拠

2026-11-20の既存観測V1は、75秒のPython同一プロセス、
MT4 1、journal711→712、公式6原本のローカルSHA一致、
AI6/6、通信ラッチtrue、仮想建玉0、発注0を確認。
過去の3020原本のうちtick時刻逆転4件は永久に保全。
本統合PRは、これを勝手に解除したり修復したことにはしない。

## HUMAN-only エントリー証拠パケット

schema=fx_final_paper_auto_entry_evidence_v1。
個別のオペレーター署名済みパケットを別途用意する。
開発者は許可を自動で生成しない。

必須キー：schema,scope,operator_approval,approved_at_utc,
expires_at_utc,bound_journal_sha256,official_archive_manifest_sha256,
sources,clock,calendar,consensus,cost,mt4,human_evidence_review。

scope=RAKUTEN_MT4_DEMO_INTERNAL_VIRTUAL_ONLY。
approval=APPROVE_FINAL_PAPER_VIRTUAL_ENTRY_EVIDENCE_FOR_THIS_JOURNAL。
直近journal head SHAに結び、有効期限最大24時間。既存セッションで
ファイル内容を差替えた場合は停止。

sourcesの8つの原本ID:
official_us / official_eur / official_jpy /
independent_utc_clock / broker_clock / pre_release_consensus /
cost_model / mt4_v2_experts_log。
原本名・SHA256を照合。BLS/ECB/BOJの元公式資料は既存6原本manifest
から照合。ExpertsログにはFXPAPER-CLOCKFREEZE-20261120-V2が必要。
MetaEditorでのコンパイル0 errors、旧EA停止と新EA唯一稼働、
DEMO口座を本人が確認する。GitHubのPythonテストはMQL4実機コンパイル
を証明しない。

clock：独立NTP/UTC、broker時計を別資料で記録し、
PC・broker時刻誤差各±2sの有人確認。独立時計証拠24時間以内。
新規CSVはbroker-PCオフセットも各周期±2s照合する。
2026-11-20時点で+7200秒が観測されたが、これは独立証明ではない。

calendar：USD/EUR/JPYの公式予定とHIGH/CRITICALのUTC予定時刻、
イベントID/通貨/公式URL/元資料IDを人間が網羅確認する。
±15分では新規取引停止。consensus原本は発表前に保存した時刻証拠が必要。
cost：各通貨の最大spread、LONG/SHORT別の保守的swap円/lot/day、
片側1pip slippageのモデル確認を要する。
ローカルSHAや本人の入力だけでは公表元や予想時刻の独立真実性は
自動保証されない。原本を実際にレビューするまで署名禁止。

## HUMAN-only 新AI予算

schema=fx_final_paper_auto_budget_authorization_v1。
operator_approval =
APPROVE_SEPARATE_FINAL_PAPER_PAID_AI_BUDGET_WITH_JPY_RESERVES。

新AIモデル2種類、旧6/6確認、月次上限3000JPY以内、追加呼び出し数
2〜120の偶数、2モデル1組の予約JPYを指定。provider pricing原本SHA、
model別の入力/出力JPY百万tokenレートを証明書に保存。
60000入力/1800出力token、さらに2倍係数から保守的予約を算出する。
このJPY予約は**実際のprovider請求金額ではない**。
provider側の請求明細、料金変動や請求上限は別途確認する。

## HUMAN-only 今回の通信停止解除

まず既存Python監視を本人が明示的に停止し、Windowsでプロセスゼロ
と元journal/lockを確認する。全ての600秒超gapとjournal headの
fingerprintを読み取り専用で取得：

    python -m research.final_paper_current_comm_release --state-root <state-root> --preview

本人が今回の停止原因・ギャップ・0ポジション・他ラッチなしを確認したら、
別途今回限定の承認をステージする：

    python -m research.final_paper_current_comm_release --state-root <state-root> --stage --operator-approval APPROVE_CURRENT_FX_PAPER_COMMUNICATION_LATCH_RELEASE_ONLY --gap-fingerprint <preview-hash> --supervisor-absence-checked

stage単体ではラッチを解除しない。実際に新しいfresh quoteに
遭遇したときだけ1回限りの解除になり、DD等は解除しない。
今回はまだstageを実行していない。

## Windowsでの将来のFINAL-AUTO起動

上記の真正原本、MetaEditor V2、個別通信停止承認、
追加AI予算承認と実料金監視が整った場合のみ実施する。
既存監視を勝手に停止/二重起動せず、Windowsプロセス確認後
新ブランチのレビュー用worktreeから以下を実行する。
括弧内のパスとモデルIDは説明用で、実際の値に置き換えること。

    .\scripts\final_paper_start_full_auto_virtual_only.ps1 -Mt4FilesDirectory $mt4Files -NewsBundle @('<original official news archive>') -EntryEvidenceFile '<approved entry evidence>' -OfficialArchiveDirectory $official -BudgetAuthorizationFile '<approved new paid budget>' -AnalystModel '<confirmed model A>' -ReviewerModel '<different confirmed model B>' -OperatorPaidConsent 'I_ACCEPT_NEW_PAID_AI_USAGE_FROM_APPROVED_JPY_BUDGET'

Windows scriptは二重Python supervisorと元lockを拒否。
APIの実課金を伴うため、ユーザーの別途明示承認なしに実行してはならない。

## 受入条件

全Linux3.12/Windows3.13回帰テスト、PS構文PASS。
旧monitorの6/6及び通信ラッチの安全性を維持。
証拠がない場合0追加API、0新規仮想建玉、0broker発注。
モデルは別々、APPROVEDだけ、次quote以降に仮想売買。
過去未承認の発注/課金への昇格・単純なtrueフラグ偽装は禁止。
本PRではmainマージ、現場EA差替え、通信ラッチ解除、
新たなOpenAI API課金、実機仮想売買開始を実施していない。
