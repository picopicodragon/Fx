# RISK-3P-127〜132：架空リスク計算器の上流辞書キーとペア属性の安全性

作成日：2026-11-06 JST。PR #196のmainへのマージをGitHubで確認後、方式Eの新ブランチで実装。

## 見つかった問題

前工程RISK-3P-121〜126では、損切り損失とポートフォリオ申告損失の**引継ぎ照合**について、架空の3ペア辞書を集合に変換する前にキーの厳密な文字列型を調べるようにした。

一方、引継ぎ以前に呼び出される次の**元の合成計算器**には、同じ未検査の`set(dict)`が残っていた。

- `scripts/phase1_three_pair_synthetic_risk.py`の`review_synthetic_portfolio`（架空価格`quotes`）。
- `scripts/phase1_three_pair_synthetic_stop_conversion.py`の`review_synthetic_stop_risk`（架空契約`contracts`と架空価格`quotes`）。

辞書キーに独自の`__hash__`や`__eq__`を持つPythonオブジェクトが混入すると、`set(dict)`でそれが実行される可能性があった。また、これら2モジュールの架空`Quote.pair`、`Contract.pair`は`dataclass`の型注釈だけで、実行時には独自比較処理を持つ値を注入可能であり、`pair != expected`で処理される可能性があった。

## 今回の工程

| 工程 | 実装・検証 |
|---|---|
| RISK-3P-127 | 合成ポートフォリオ計算の`quotes`を、既存`_mock_plain_three_pair_map`でexact dict・キーexact str・3ペア一致と検査する。集合化は型確認後に限定 |
| RISK-3P-128 | 合成損切り計算の`contracts`／`quotes`にも同等の厳密キー検査を実装。両モジュールの`Quote.pair`と損切り`Contract.pair`も型確認してから比較 |
| RISK-3P-129 | 悪意あるstrサブクラス・独自オブジェクトキーのハッシュ／等価比較を、受取後の合成計算処理で呼び出さず拒否するテスト |
| RISK-3P-130 | 架空`Quote.pair`／`Contract.pair`に不審な比較オブジェクトを注入しても比較しないことを検証 |
| RISK-3P-131 | 3ペアの欠落・追加・別ペア、Python bool/int等のキー、dictサブクラス、悪条件の価格・数量を拒否し、既存NO_GOを維持 |
| RISK-3P-132 | 新規29件の回帰テスト、既存2ソースへのQ109テスト紐付け、RISK-3P-02厳格な移行監査のテスト対応を更新。PRとWindows/Repository CIを確認 |

## 対応範囲と限界

この改修は、**既に構築された組込み辞書内のキーを、集合化・ハッシュ・値の比較より先に検査する**という限定された防御である。辞書へ任意オブジェクトを**挿入する瞬間**のPython動作を防止したり、任意の外部コードを完全に隔離するものではない。

この検証は、合成用の3ペアUSD/JPY・EUR/JPY・EUR/USDの架空価格・架空契約・架空候補／建玉／未約定注文だけを利用する。過去に指定された本番取引4ペアの要件を変更するものではない。

成功時も`runtime_go_no_go=NO_GO`、`phase_1=BLOCKED`、`safety_hold_latched=true`、`order_allowed=false`とする。非運用Q109ソース45件、`production_authorized=false`を維持する。

## 維持するリスク・承認境界

**P05 0/8 BLOCKED、G1実値0/15、FX-SAF原議0/15、FORM承認0/43、PHASE-1 BLOCKED、runtime NO_GO、安全停止ラッチtrue、verified_values=null**を維持。

1取引損失上限0.5%、同時合計1.0%、日次1.5%、DD4%新規停止／5%全決済と人間承認、NY17:00取引区切り、通信断・時計異常、単一デモ口座、既存EAの無干渉方針に変更なし。

楽天MT4・EA・実口座・実建玉・未約定注文・Windowsの非公開ログ・秘密値へのアクセス、発注、停止解除、mainへの自動マージは行わない。方式Eとして承認不要のオフライン開発をPRとCIまで連続実施する。
