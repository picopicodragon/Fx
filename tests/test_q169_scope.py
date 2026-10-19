"""Q169: at most one second of cancellation confirmation within total 25s."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Q169DecisionTests(unittest.TestCase):
    def test_source_and_spec(self):
        evidence = json.loads((ROOT / "specs/source_evidence.json").read_text(encoding="utf-8"))
        record = next(x for x in evidence["records"] if x["question_id"] == "Q169")
        self.assertEqual(record["verification"], "DIRECT_CHAT")
        self.assertFalse(record["owner_approved_for_safety"])
        excerpt = (ROOT / record["excerpt_path"]).read_text(encoding="utf-8")
        self.assertIn("第169問はBを採用する", excerpt)
        self.assertIn("本人の直接発言ではない", excerpt)
        section = (ROOT / "specs/safety_foundation.md").read_text(encoding="utf-8").split("## Q169：", 1)[1].split("\n## ", 1)[0]
        for token in (
            "最大1秒", "キャンセル要求発行時", "試行ID", "旧試行",
            "未完了の通信処理", "無効化", "隔離", "確認不能",
            "総復旧25秒", "試行最大2秒", "3秒へ延長しない",
            "残余時間", "追加試行", "正常認定", "既存の障害停止",
            "Q168", "Q167", "Q166", "Q165", "Q164",
            "最大4回", "1秒", "2秒", "4秒", "8秒",
            "Q163", "リプレイ防止", "Q162", "段階的受信",
            "Q161", "20 KiB", "Q160", "UINT32BE",
            "Q159", "16 KiB", "4 KiB", "Q158", "Q157",
            "Q156", "Q155", "HMAC-SHA256", "Q154", "全検証合格",
            "Q153", "Windows単調増加時計", "更新しない",
            "Q150", "通常2秒", "Q151", "厳密に6秒超",
            "Q152", "欠落回数", "60秒", "10分", "自動再起動最大3回",
            "Q149", "Windows電源イベント", "Q148",
            "Q126の30分計測をリセット", "Q133", "Q139〜Q143",
            "Q145〜Q147", "60秒以上", "UTC", "DD4%・5%",
            "本人承認必須停止", "implementation_approved=false", "未決"
        ):
            self.assertIn(token, section)

    def test_approval_and_history(self):
        r = json.loads((ROOT / "specs/reconciliation_registry.json").read_text(encoding="utf-8"))
        p = json.loads((ROOT / "specs/source_review_priority.json").read_text(encoding="utf-8"))
        a = next(x for x in r["items"] if x["requirement_id"] == "FX-SAF-006")
        b = next(x for x in p["items"] if x["requirement_id"] == "FX-SAF-006")
        self.assertIn("Q169", a["question_ids"])
        self.assertIn("Q169", b["question_ids"])
        self.assertFalse(a["implementation_approved"])
        self.assertIsNone(a["owner_approval"])
        self.assertFalse(b["human_safety_approval"])
        self.assertEqual(b["source_review"], "PENDING_ORIGINAL")
        decisions = (ROOT / "DECISIONS.md").read_text(encoding="utf-8")
        self.assertEqual(sum(x.startswith("| Q169 |") for x in decisions.splitlines()), 1)
        self.assertIn("v16.9", (ROOT / "MASTER_SPEC.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
