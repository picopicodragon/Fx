# FX-FWD-014〜017: 複数観測周期の研究用フォワード監査

## 実装範囲
- **FWD-014**: `forward_shadow_cycle` が各時点で出した品質・ペーパー結果を複数周期まとめて評価する。`research/forward_multicycle.py`。
- **FWD-015**: 一つの仮説に紐づく連続した仮想純資産推移を作り、`forward_risk_timeline.evaluate` へ渡す。NY17時切り替え/DD警告を再利用する。
- **FWD-016**: 欠損、時刻逆行、観測件数ロールバック、同一周期重複、仮説混在、全ペアの価格鮮度をフェイルクローズ／安全保留として報告。
- **FWD-017 (運用準備)**: Windowsローカルで安全な手動定期実行に使う下記コマンドおよび台帳契約を明文化。タスクスケジューラの登録は行わず、価格や証券口座には接続しない。

**重要**: 各周期のペーパーレポートは観測の全履歴を最初から再生した「独立したas-ofスナップショット」である。各周期の`hypothetical_pnl_jpy`を足すことは禁止。最新スナップショットの仮想損益を使用する。したがって別の仮説に切り替わった場合、個別の連結利益は作成せず停止する。

## Windows CLI
先にFWD-005A `research.forward_shadow_cycle`を周期ごとに実行して、欠けのない品質・仮想レポートを生成する。実行には利用者が事前に研究データを用意する必要がある。プログラムは価格源やAI推論を自動取得しない。

```powershell
# 例：out/ に以下の2組が存在する場合
# cycle001_quality.json, cycle001_paper.json
# cycle002_quality.json, cycle002_paper.json
@'
{
  "schema": "fx_forward_multicycle_v1",
  "cycles": ["cycle001", "cycle002"]
}
'@ | Set-Content -Encoding utf8 out/multicycle_manifest.json

python -m research.forward_multicycle `
  --manifest out/multicycle_manifest.json `
  --reports-dir out `
  --out out/multicycle_report_001.json `
  --max-gap-seconds 300
```

各周期のスナップショットが同じ`asof_utc`を持つこと、進行が単調であること、品質/ペーパーの`NO_GO`安全フラグが維持されることを検証する。レポートSHA-256を保存するが、ハッシュは元ファイルの真正性や操作権限の証明ではない。周期間隔上限300秒は**研究上の閾値**で、公式安全閾値ではない。

## 依然未実装のもの
1. ローカル観測ジャーナルとの**厳密な周期ごとの記録ハッシュ紐づけ**。現段階は各レポートに含まれる証拠件数・検証状態と、レポート自体のSHAに限定。証拠件数が増えていても、新たな有効価格が届いたと確認した意味ではない。
2. 同一時刻複数ペア・複数建玉に対する正式な売買/ポジションライフサイクル、取引サイズ、決済履歴、手数料・スリッページ・証拠金・含み損の認定。
3. 口座の完全なNY17時日次資金台帳。日次初回サンプルが区切り時刻と一致しない場合、日次損失が過小評価される可能性がある。
4. 公的マクロ情報の網羅、価格ライセンスと真正性、Windows時刻独立同期、MT4実機コンパイルと一方向出力の運用検証。
5. Windowsタスクの自動登録、24時間監視・障害通知、デモ注文許可、承認・本番実行。

## 不変安全条件
現段階の`NO_GO` / `safety_hold_latched=true` / `real_orders_permitted=false`は固定。デモ口座・実口座の注文は送信せず、MT4操作や自動承認にも接続しない。単一仮想ポジションの再評価値の推移は将来利益や実際の約定品質の証拠ではない。
