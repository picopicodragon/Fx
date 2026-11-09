# FX-AI-ARCH-003: 2025年25イベント、3系統AI比較と不一致監査

## 達成範囲と制約

OpenAI Responses、TypeSafe Jev、OpenAI Decisionsの既存研究用`FX-AI-ARCH-002`アダプターを使い、**2025年の同じ25イベント × USD/JPY × 3プロバイダー = 75件**の有限選択研究用判断を比較できる専用パイプラインを実装した。

- 入力は`research/datasets/official_2025_macro_evidence_seed.json`。イベントごとに同じas-of公開資料と質問を提供する。UTC時刻・入力SHA-256で同一性確認。
- `priority`: HIGH/MEDIUM/LOW/UNKNOWN、`reanalysis`: YES/NO/UNKNOWN。
- 既存1イベントの実APIレポートを`--seed`で再利用し、**検証一致した場合だけ先頭イベントの3リクエストを省略**する。この場合、追加72リクエストで全件比較できる。
- **有料API呼び出し前にチェックポイント**を書き込み、完了時に原子的に結果保存。API障害・プロセス中断で応答成否が不明な場合は未確定リクエストを記録して停止、**再実行しても重複課金の恐れがあるリクエストを自動再送しない**。これはAPI側のExactly Onceや支払い確定を保証するものではない。
- クレデンシャルはWindows側の環境変数`OPENAI_API_KEY`、`TYPESAFE_API_KEY`のみ。GitHubへ提出しない。ネットワークの呼び出し許可は`--allow-external-api`かつ`--max-api-calls`で明示。
- 金額ベースの自動停止は未実装。月額開発API予算3,000円（Q100）を実費で管理する必要があるため、**呼び出し回数上限=請求金額上限ではない**。料金が不明な状態で全件実行を自動認可しない。

## Windows操作（最初の実測1イベントを再利用）

### 1. ブランチ取得

```powershell
cd C:\Users\Suzuki\Documents\ChatGPT\Fx
git fetch origin
git switch --detach origin/feat/ai-2025-25-event-disagreement-audit
python -m unittest discover -s tests -p "test*.py"
```

### 2. **課金なしの初期化と先頭1イベントの再利用**

先ほど取得済みの`out/ai_triage_compare_2025_1.json`をそのまま読み込む。**このレポートにはAPIキーを保存していないことを確認して扱う**。初回の実測では重要度3系統ともHIGH、追加分析Responses/JeVがNO、DecisionsがYESだった。

```powershell
python -m research.ai_provider_annual_audit `
  --evidence research/datasets/official_2025_macro_evidence_seed.json `
  --seed out/ai_triage_compare_2025_1.json `
  --journal out/ai_provider_2025_25_journal.json `
  --report out/ai_provider_2025_seed_audit.json
```

成功すると`completed_event_groups=1`、`completed_api_decisions=3`、`disagreement_event_groups=1`の**部分監査**になる。このとき外部APIリクエストは0回。元レポートが先頭イベント・モデル契約と一致しなければ安全停止する。ファイルが既にある場合は絶対上書きしない。

### 3. **実費を確認後、有料APIで残72件を比較**

**事前にOpenAIとTypeSafeの請求画面で利用枠・利用単価・今月の残り予算を確認すること。** チャットにキー文字列を貼らず、同じPowerShellセッションに両APIキーを設定する。

追加72回を一括実行するには：

```powershell
python -m research.ai_provider_annual_audit `
  --evidence research/datasets/official_2025_macro_evidence_seed.json `
  --journal out/ai_provider_2025_25_journal.json `
  --resume `
  --max-api-calls 72 `
  --allow-external-api
```

**一度に72回の費用が不明・予算を超えそうな場合、より小さい回数で分割可能**。たとえば`--max-api-calls 3`は次の1イベントの3系統を処理する。次回も`--resume`で別の連続3呼び出しを処理でき、既に記録済みの結果は再請求しない。

異常停止時は`pending_request`を含むjournalを改変・削除せず、発生したAPI課金/応答の有無を検証するまで止める。途中停止からの無条件リトライはサポートしない。

### 4. **課金なしの全25イベント監査レポート生成**

```powershell
python -m research.ai_provider_annual_audit `
  --evidence research/datasets/official_2025_macro_evidence_seed.json `
  --journal out/ai_provider_2025_25_journal.json `
  --audit-only `
  --report out/ai_provider_2025_25_disagreement_report.json
```

```powershell
$r = Get-Content out/ai_provider_2025_25_disagreement_report.json -Raw | ConvertFrom-Json
$r | Select-Object source_events, completed_event_groups, completed_api_decisions, disagreement_event_groups, unanimous_event_groups
$r.disagreement_details | Select-Object event_id, disagreement_types, candidate_evidence_quality_flags | Format-Table -Wrap
$r.provider_summary | ConvertTo-Json -Depth 10
```

このレポートは全25イベントを処理したときにのみ`ANNUAL_PROVIDER_DISAGREEMENT_AUDIT_COMPLETE_NO_GO`となる。残りがあれば`PARTIAL_NO_GO`。

## 不一致の「原因分析」で分かることと分からないこと

報告書の各イベントに次の**観測と仮説**を分けて出力する。

| 判定 | 意味 |
|---|---|
| `PRIORITY_DIFFERENCE` | 同一入力でも重要度の有限選択が不一致 |
| `REANALYSIS_DIFFERENCE` | 追加調査要否が不一致 |
| `UNKNOWN_IN_ONE_OR_MORE_RESPONSES` | 不明と答えたプロバイダーが存在 |
| `MISSING_PRE_RELEASE_CONSENSUS` | イベント資料に事前コンセンサスが欠ける（潜在的な説明変数） |
| `NO_HUMAN_VERIFIED_TRIAGE_LABEL` | 人的正解ラベルが未整備、どれが正しいか未判定 |

不一致の**直接原因は、このラベル集計だけでは特定できない**。各モデルの内部推論や回答根拠はAPI仕様に応じて可観測性が異なるため、JSON choiceとconfidenceだけから、なぜYES/NOと判断したかを断定しない。現段階では`verified_causal_explanation=null`、`causation_identified=false`を明記し、専門家の独立ラベルと複数回の再現性試験へ引き渡す。多数決やconfidenceの最大値を売買に反映しない。

対象の25イベントについて、一次資料に対して独立検証済みでない市場予想と当時の価格データ真正性の課題は残る。**1イベントの結果をそのまま年間優劣へ一般化しない**。

## 安全・承認の状態

売買権限は引き続き`runtime_go_no_go=NO_GO`、`safety_hold_latched=true`、`real_orders_permitted=false`。本研究はモデル選定Q92〜98、承認Q107、FX-SAF、G1〜G9、PHASE-1の実口座認可を変更しない。コード/テスト/PRが完成しても本番採用や取引権限は得られない。
