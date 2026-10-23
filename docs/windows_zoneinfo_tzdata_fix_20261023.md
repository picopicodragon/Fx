# Windows: `zoneinfo` が `America/New_York` を取得できない場合

## 対象の実エラー（2026-10-23）

本人のWindows／pyenv-win Python 3.13.11で単体テスト321件を実行した結果、320件は成功し、`test_ny17_dst_converts_to_expected_jst`のみ以下の例外で終了した。

```text
ModuleNotFoundError: No module named 'tzdata'
zoneinfo._common.ZoneInfoNotFoundError: 'No time zone found with key America/New_York'
Ran 321 tests
FAILED (errors=1)
```

Pythonの`zoneinfo`自体は標準ライブラリだが、IANAタイムゾーンデータの実体は標準搭載されていない。Windowsは通常IANAのシステムデータベースを持たないため、[Python公式zoneinfo資料](https://docs.python.org/3/library/zoneinfo.html)の推奨どおり、**tzdataを依存に明記**する必要がある。LinuxのCI成功だけではWindowsの前提は確認できない。

## Windowsでの一回限りの環境修復

リポジトリルートで、**テストを実行するのと同じPython**に開発時依存をインストールする。

```powershell
python -m pip install -r requirements-dev.txt
python scripts/doctor_development_environment.py
python -m unittest discover -s tests -p "test*.py"
```

`requirements-dev.txt`はWindowsのときだけ `tzdata==2026.5`を導入する。2026-10-03公開のPython公式`tzdata`パッケージである。OSとPythonの違いによる予期しない更新を防ぐため開発テスト用の版を固定したが、**将来のIANAルール変更に追随する際は依存更新と日付境界テストを別途検証する**。

```powershell
python -c "from zoneinfo import ZoneInfo; print(ZoneInfo('America/New_York')); print(ZoneInfo('Asia/Tokyo'))"
```

必要なパッケージが取得できない完全オフライン環境では、別のネット接続環境で**公式の`tzdata==2026.5` wheel**を取得して、オフライン用の外部保存先からインストールする。wheelやキャッシュ/実行時の内部ファイルをGitHubリポジトリに入れない。タイムゾーンデータがない状態を日付計算の成功とみなす`skip`や固定UTCオフセットへの置換は行わない。

## 恒久的な再発防止

- `requirements-dev.txt`：Windows用のタイムゾーン依存を記録
- `scripts/doctor_development_environment.py`：`America/New_York`と`Asia/Tokyo`のIANA取得可否を検査。失敗したら具体的な`pip`コマンドとともに**非ゼロ終了**する
- `tests/test_doctor_development_environment.py`：タイムゾーン取得成功・片方欠落・両方欠落を合成ローダーで検査
- `.github/workflows/ci.yml`：従来のUbuntu Python 3.12に加え、Windows Python 3.13で依存をインストールした上で全単体テストを実行。追加のOSジョブのCIも成功してから手動マージする

この修正は**開発環境の依存関係と検証の修正**であり、NY17:00基準、DSTルール、FXリスク上限、DD監視・停止、再試行防止などの採用済み安全方針は変更していない。`forward_trading_enabled=false`、`implementation_approved=false`、`human_safety_approval=false`、`owner_approved_for_safety=false`、PHASE-1 BLOCKEDを維持する。単体テスト成功は安全実装の本人承認を意味しない。

## 2026-10-23追記：Windows Python 3.13の警告表示を是正

`tzdata`インストール後、本人Windows Python **3.13.11**で`324 tests / OK`、診断のIANA２ゾーンはPASS。それにもかかわらず開発環境診断は従来の**Linux Python 3.12のみ**をCI参照としたため、`WARN: Python 3.13 differs from CI reference 3.12`が表示されていた。これは実際の障害ではなく**CI対象プラットフォームごとの説明不足**である。

`scripts/doctor_development_environment.py`はCI構成と対応する`linux=Python 3.12`、`win32=Python 3.13`を区別して表示するよう更新。基準に含まれないOS・バージョンはWARNを維持し、**CI実行済みを完全な実行環境互換・発注安全性の保証に格上げしない**。CIのWindows/Ubuntuジョブは継続する。
