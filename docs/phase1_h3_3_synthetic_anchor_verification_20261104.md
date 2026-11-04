# H3-3: 独立Witness CAS / WORMのオフライン状態遷移検証

作成：2026-11-04。参照：PR #168・#169・#170、H3-2、G6/G7/G8、Q109〜115、FX-SAF-001〜015。

> OFFLINE SYNTHETIC ONLY。AWS/Azure接続・契約・鍵生成・独立Trust Anchorの実在・OS障害・MT4注文・G6実証を行わない。

## 成果物
- 純粋関数のモデル：scripts/phase1_h3_synthetic_anchor.py
- 単体試験：tests/test_phase1_h3_synthetic_anchor.py
- specs/traceability.json にオフライン参照を追加。production_authorized=false。
- local / witness / auditを別の合成スナップショットとし、模擬した一意の更新・監査証跡・復旧照合を行う。これらの実際の独立性は未証明。

## 合成状態遷移
| 状態 | 前提 | 異常時 |
| --- | --- | --- |
| IDLE/VERIFIED | local/witness/audit一致、発行者有効 | 不一致・失効で新処理拒否 |
| PREPARED | request_id、候補digestが正しい | 重複準備で拒否 |
| WITNESS_COMMITTED | 模擬CASのCOMMITTED | UNKNOWN/UNAVAILABLEはUNKNOWN、競合/失効は隔離 |
| AUDIT_COMMITTED | 同じrequest_idで模擬WORM受領 | 片側成功/証跡欠落・矛盾では隔離 |
| VERIFIED | 最新Journal・Witness・WORMが3者一致、両方到達可、STOP墓標あり | 古いsnapshot・時刻/世代相違・未到達・墓標欠落で隔離 |

**VERIFIEDも合成値の内部一致のみ。実取引・停止解除・G6実受入ではない。** 全Reviewの安全出力は runtime_go_no_go=NO_GO / phase_1=BLOCKED / safety_hold_latched=true / order_allowed=false / stop_release_allowed=false / automatic_retry_allowed=false / verified_values=null。

## 拒否テストの範囲
- Witness不達・結果不明、競合、失効、重複CAS試行、無効な発行者世代
- WORMのreceipt不明・遅延・不一致、WORMだけ未コミット、誤request_id
- ローカル・Witness・WORMそれぞれの旧Snapshot、異なるepoch/digest/sequence
- 停止墓標喪失、観測可用性欠落、無効な型、改変された状態
- 模擬証拠が一致しても注文権限/再試行/停止解除が常に禁止されること

## 明示的に未実施の範囲
外部CASの原子性、AWS/Azureのアクセス権分離、クラウド監査保全、管理者による巻戻し、物理電源断、実ストレージのflush/fsync、実署名・鍵回転、Windows復元、MT4/EA操作・注文は試験していない。二つのクラウドストアをまたぐ原子的な一括コミットも仮定していない。故障時には証拠を確定できないまま許可や自動再送をしない。

## 既存ゲートと次の工程
G1〜G9 UNRESOLVED、D537-WPの実受入0/15、FX-SAF-001〜015未承認、PHASE-1 BLOCKED、runtime NO_GO、停止ラッチを維持。H1欠落原議探索は保留中であり承認済み扱いにしない。

3通貨ペア USD/JPY・EUR/JPY・EUR/USD の通貨別ネット/グロス合算リスクを扱う RISK-3P-01 は次の独立工程で検証する。数値閾値や実装権限を本PRで作らない。

## 実行確認コマンド
- python -m unittest tests.test_phase1_h3_synthetic_anchor -v
- python -m unittest discover -s tests -p "test*.py"
- python scripts/check_traceability.py
- python scripts/check_repository.py
- python scripts/check_phase1_way_e.py

実際のテスト結果はCIのログで確認する。本文は試験の成功を先取りしない。