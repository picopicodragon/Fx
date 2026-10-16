"""Q126: reset DD warning recovery timer when continuous verification is lost."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Q126DecisionTests(unittest.TestCase):
    def test_direct_user_choice_is_captured_without_safety_approval(self):
        manifest = json.loads((ROOT / "specs/source_evidence.json").read_text(encoding="utf-8"))
        q126 = next(r for r in manifest["records"] if r["question_id"] == "Q126")
        self.assertEqual(q126["source_kind"], "ORIGINAL")
        self.assertEqual(q126["verification"], "DIRECT_CHAT")
        self.assertEqual(q126["archive_locator_status"], "PENDING_LOCAL_ARCHIVE")
        self.assertFalse(q126["owner_approved_for_safety"])
        excerpt = (ROOT / q126["excerpt_path"]).read_text(encoding="utf-8")
        for phrase in (
            "第126問はA", "DD2%警告", "DD3%重点再評価",
            "30分間", "解除基準以上", "データ欠落", "通信障害",
            "再起動", "リセット", "再取得", "安全確認",
            "DD4%・5%", "別途決定",
        ):
            self.assertIn(phrase, excerpt)

    def test_saf006_remains_unapproved(self):
        registry = json.loads((ROOT / "specs/reconciliation_registry.json").read_text(encoding="utf-8"))
        priority = json.loads((ROOT / "specs/source_review_priority.json").read_text(encoding="utf-8"))
        r = next(x for x in registry["items"] if x["requirement_id"] == "FX-SAF-006")
        p = next(x for x in priority["items"] if x["requirement_id"] == "FX-SAF-006")
        self.assertIn("Q126", r["question_ids"])
        self.assertIn("Q126", p["question_ids"])
        self.assertFalse(r["implementation_approved"])
        self.assertIsNone(r["owner_approval"])
        self.assertFalse(p["human_safety_approval"])
        self.assertEqual(p["source_review"], "PENDING_ORIGINAL")

    def test_stop_flags_not_cleared_by_monitoring_clock_reset(self):
        doc = (ROOT / "specs/safety_foundation.md").read_text(encoding="utf-8")
        section = doc.split("## Q126：", 1)[1].split("\n## ", 1)[0]
        for phrase in (
            "解除基準以上", "データ欠落", "通信障害", "再起動",
            "リセット", "正常なDDデータ", "安全確認",
            "最初からやり直す", "DD4%・5%", "ほかの停止理由",
            "観測頻度", "未決", "implementation_approved=false",
        ):
            self.assertIn(phrase, section)


if __name__ == "__main__":
    unittest.main()
