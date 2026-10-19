"""Q166: each reconnect attempt <=2s, total <=25s, watchdog never extended."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Q166DecisionTests(unittest.TestCase):
    def test_source_vs_presented_option(self):
        records = json.loads((ROOT / "specs/source_evidence.json").read_text(encoding="utf-8"))["records"]
        rec = next(r for r in records if r["question_id"] == "Q166")
        self.assertEqual(rec["source_kind"], "ORIGINAL")
        self.assertEqual(rec["verification"], "DIRECT_CHAT")
        self.assertEqual(rec["archive_locator_status"], "PENDING_LOCAL_ARCHIVE")
        self.assertFalse(rec["owner_approved_for_safety"])
        e = (ROOT / rec["excerpt_path"]).read_text(encoding="utf-8")
        for term in (
            "第166問はBを採用する", "本人の直接発言ではない",
            "2秒・標準タイムアウト型", "待機合計15秒", "試行最大8秒",
            "総復旧25秒は絶対上限", "未決",
        ):
            self.assertIn(term, e)

    def test_two_seconds_and_retained_safety_scope(self):
        doc = (ROOT / "specs/safety_foundation.md").read_text(encoding="utf-8")
        sec = doc.split("## Q166：", 1)[1].split("\n## ", 1)[0]
        for term in (
            "DD2%警告", "DD3%重点再評価", "独立ウォッチドッグ",
            "試行1回あたり最大2秒", "最大4回", "1秒", "2秒", "4秒", "8秒",
            "15秒", "8秒", "23秒", "総復旧25秒", "残余時間",
            "タイムアウト", "中断", "キャンセル", "API", "未決",
            "連続60秒", "連続10分", "自動再起動最大3回",
            "Q165", "段階的バックオフ", "Q164", "Q163",
            "断片", "安全停止理由", "リプレイ防止", "Q162", "段階的受信",
            "Q161", "20 KiB", "Q160", "UINT32BE", "事前長さ検証",
            "Q159", "16 KiB", "4 KiB", "Q158", "Q157", "固定順序",
            "Q156", "プロトコル版", "送信元ID", "セッション識別子",
            "連番", "鮮度検証用時刻", "ハートビート本文",
            "Q155", "HMAC-SHA256", "Windowsローカル通信のアクセス制御",
            "Q154", "形式", "鮮度", "重複・再送", "全検証合格",
            "Q153", "受信した瞬間", "Windows単調増加時計", "更新しない",
            "Q150", "通常2秒", "Q151", "厳密に6秒超",
            "Q152", "欠落回数", "Q149", "Windows電源イベント",
            "Q148", "2回連続成功を無効", "Q126の30分計測をリセット",
            "安全検証を最初から", "30分計測再開", "自動解除を禁止",
            "Q145〜Q147", "60秒以上", "UTC", "Q133",
            "最大5分間有効・異常時即失効", "Q139〜Q143", "45秒",
            "並列測定", "DD4%・5%", "本人承認必須停止",
            "ほかの停止理由", "implementation_approved=false",
        ):
            self.assertIn(term, sec)

    def test_unapproved_and_unique_decision(self):
        reg = json.loads((ROOT / "specs/reconciliation_registry.json").read_text(encoding="utf-8"))
        pri = json.loads((ROOT / "specs/source_review_priority.json").read_text(encoding="utf-8"))
        a = next(x for x in reg["items"] if x["requirement_id"] == "FX-SAF-006")
        b = next(x for x in pri["items"] if x["requirement_id"] == "FX-SAF-006")
        self.assertIn("Q166", a["question_ids"])
        self.assertIn("Q166", b["question_ids"])
        self.assertFalse(a["implementation_approved"])
        self.assertIsNone(a["owner_approval"])
        self.assertFalse(b["human_safety_approval"])
        self.assertEqual(b["source_review"], "PENDING_ORIGINAL")
        dec = (ROOT / "DECISIONS.md").read_text(encoding="utf-8")
        self.assertEqual(sum(x.startswith("| Q166 |") for x in dec.splitlines()), 1)
        self.assertIn("## Q166：", (ROOT / "MASTER_SPEC.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
