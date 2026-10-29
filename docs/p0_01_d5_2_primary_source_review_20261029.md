# P0-01 D5-2: 公式一次資料の照合と独立デモ環境No-Go判定
調査日: 2026-10-29。公開一次資料を閲覧した机上レビュー。口座、MT4、既存注文・建玉には接触していない。

## 公式一次資料と判断
1. 楽天証券 MT4デモ口座 https://www.rakuten-sec.co.jp/web/fx/mt4/demo-account.html
   - デモ口座を何度でも作成できる旨の記載あり。初期仮想証拠金は500万円、レバレッジ25倍。
   - **記載されていない**：異なる複数のデモ口座を同時に保持できる保証、追加作成時に旧デモ口座・旧建玉・注文が無効化されない保証、同時ログインの可否。
   - 「繰り返し作成可能」≠「独立口座を同時保持可能」。G1/PF1は未解決。
2. 楽天証券 MT4導入 https://www.rakuten-sec.co.jp/web/fx/mt4/download/
   - デモ接続先RakutenSecurities-Demo、本番接続先RakutenSecurities-Liveを区別。インストール完了後にMT4が自動起動する説明あり。従ってインストール自体も現在は実施しない。
3. MetaTrader 4公式インストール https://www.metatrader4.com/ja/trading-platform/help/userguide/installation
   - 複数口座の端末を同時に使うには、別々のディレクトリに端末をインストールする必要がある。
4. MetaTrader 4公式データ構造 https://www.metatrader4.com/en/trading-platform/help/userguide/start_comm
   - 一般的にはインストールディレクトリとは別のユーザーデータフォルダに保存。インストールパスを元にしたインスタンス別データフォルダとFile > Open Data Folderが記載。インストール先の分離だけでデータ・設定の完全隔離を推定しない。
5. 楽天証券MT4本番口座案内 https://www.rakuten-sec.co.jp/web/fx/mt4/account.html
   - 本番口座のログインパスワード発行でログアウトが起きる注意事項あり。デモ口座にも同じ仕様とは断定しない。本番の操作は対象外。

## 重要な未解決項目と判断
- E1: デモ口座AとBの**同時保持可否**: NOT_ESTABLISHED。公開記載なし。
- E2: Bの新規作成がAの口座・既存注文/建玉に**悪影響を与えない保証**: NOT_ESTABLISHED。公開記載なし。
- E3: **同時ログイン可能性**: NOT_ESTABLISHED。公開記載なし。
- E4: 端末を別ディレクトリへインストールする設計: DOCUMENTED。ただし口座分離や実測の認証とは独立。
- E5: データフォルダ構造と現地識別手順: DOCUMENTED_DESIGN_ONLY。現地での端末起動とデータフォルダ確認は未承認。
- E6: 本番・デモのサーバー表示の識別: DOCUMENTED_DESIGN_ONLY。ログイン操作は未承認。

## Fail-closed決定
`G1=BLOCKED_EXTERNAL_POLICY`、`PF1=BLOCKED`。Bの口座作成、MT4インストール・起動、ログイン切替、EA/EX4配置・実行、MarketInfo等の照会、注文操作は一切禁止。Aに装着済みのMACD Sample、既存建玉・未約定注文、AutoTrading状態を変更しない。

楽天証券が公式文書で同時保持と非影響を明示しない場合、**無理に口座を追加せずオフライン合成モックで継続**。追加で公式資料を読むことは可能。サポートが案内対象外の場合も未確認を「確認済み」に昇格しない。

## 移行判断
D5-2の公開資料照合は完了。ただしG1/PF1の解除に必要な証拠は得られていない。D5-1の安全条件、`PHASE-1 BLOCKED`、`runtime_go_no_go=NO_GO`を維持。PRのCI成功とマージは本番/デモ実行承認に該当しない。
