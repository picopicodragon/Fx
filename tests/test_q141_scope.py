"""Q141 regression coverage for clock-query time limits and pending approvals."""
import json
import unittest
from pathlib import Path
R = Path(__file__).resolve().parents[1]
class Q141Tests(unittest.TestCase):
    def test_source_and_safety_state(self):
        e = json.loads((R / "specs/source_evidence.json").read_text(encoding="utf-8"))
        x = next(i for i in e["records"] if i["question_id"] == "Q141")
        self.assertEqual(x["verification"], "DIRECT_CHAT")
        self.assertEqual(x["archive_locator_status"], "PENDING_LOCAL_ARCHIVE")
        self.assertFalse(x["owner_approved_for_safety"])
        a = json.loads((R / "specs/reconciliation_registry.json").read_text(encoding="utf-8"))
        s = next(i for i in a["items"] if i["requirement_id"] == "FX-SAF-006")
        self.assertIn("Q141", s["question_ids"])
        self.assertFalse(s["implementation_approved"])
        self.assertIsNone(s["owner_approval"])
    def test_timing_and_fail_closed(self):
        q = (R / "specs/source_excerpts/Q141.md").read_text(encoding="utf-8")
        d = (R / "specs/safety_foundation.md").read_text(encoding="utf-8")
        sec = d.split("## Q141：")[1].split("\n## ")[0]
        for v in ("タイムアウトを2秒", "待機間隔を1秒", "最大5回試行",
                  "最低3回の有効測定", "30分計測をリセット", "DD4%・5%"):
            self.assertIn(v, q)
        for v in ("タイムアウトは2秒", "待機間隔は1秒", "無効測定",
                  "最大5回試行", "最低3回の有効測定", "自動解除を禁止",
                  "30分計測をリセット", "未決", "implementation_approved=false"):
            self.assertIn(v, sec)
if __name__ == "__main__":
    unittest.main()
