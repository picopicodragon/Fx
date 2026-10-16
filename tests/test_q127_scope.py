"""Q127 records 10-second DD monitoring for *warning release*, not emergency stop detection."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Q127DecisionTests(unittest.TestCase):
    def test_direct_chat_choice_is_recorded(self):
        evidence = json.loads((ROOT / "specs/source_evidence.json").read_text(encoding="utf-8"))
        item = next(x for x in evidence["records"] if x["question_id"] == "Q127")
        self.assertEqual(item["source_kind"], "ORIGINAL")
        self.assertEqual(item["verification"], "DIRECT_CHAT")
        self.assertEqual(item["archive_locator_status"], "PENDING_LOCAL_ARCHIVE")
        self.assertFalse(item["owner_approved_for_safety"])
        excerpt = (ROOT / item["excerpt_path"]).read_text(encoding="utf-8")
        for term in (
            "第127問はA", "DD2%警告", "DD3%重点再評価", "30分間",
            "10秒周期", "有効なDDデータ", "第126問", "リセット",
            "データ有効期限", "欠測判定", "DD4%・5%",
        ):
            self.assertIn(term, excerpt)

    def test_fx_saf_006_remains_unapproved(self):
        registry = json.loads((ROOT / "specs/reconciliation_registry.json").read_text(encoding="utf-8"))
        priority = json.loads((ROOT / "specs/source_review_priority.json").read_text(encoding="utf-8"))
        a = next(x for x in registry["items"] if x["requirement_id"] == "FX-SAF-006")
        b = next(x for x in priority["items"] if x["requirement_id"] == "FX-SAF-006")
        self.assertIn("Q127", a["question_ids"])
        self.assertIn("Q127", b["question_ids"])
        self.assertFalse(a["implementation_approved"])
        self.assertIsNone(a["owner_approval"])
        self.assertFalse(b["human_safety_approval"])
        self.assertEqual(b["source_review"], "PENDING_ORIGINAL")

    def test_scope_is_warning_release_only(self):
        doc = (ROOT / "specs/safety_foundation.md").read_text(encoding="utf-8")
        section = doc.split("## Q127：", 1)[1].split("\n## ", 1)[0]
        for term in (
            "原則10秒周期", "30分間", "DD1.5%未満", "DD2.5%未満",
            "Q126", "リセット", "Q121/Q122", "DD4%・5%",
            "データ有効期限", "欠測判定", "観測間", "未決",
            "実装", "implementation_approved=false",
        ):
            self.assertIn(term, section)
        self.assertIn("停止発動検知頻度ではない", doc)


if __name__ == "__main__":
    unittest.main()
