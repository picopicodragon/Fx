"""Q124 DD2/3% monitor-release thresholds, not a trade authorization."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Q124DecisionTests(unittest.TestCase):
    def test_exact_user_source_choice_is_referenced(self):
        data = json.loads((ROOT / "specs/source_evidence.json").read_text(encoding="utf-8"))
        q = next(row for row in data["records"] if row["question_id"] == "Q124")
        self.assertEqual(q["source_kind"], "ORIGINAL")
        self.assertEqual(q["verification"], "DIRECT_CHAT")
        self.assertEqual(q["archive_locator_status"], "PENDING_LOCAL_ARCHIVE")
        self.assertFalse(q["owner_approved_for_safety"])
        excerpt = (ROOT / q["excerpt_path"]).read_text(encoding="utf-8")
        for term in (
            "第124問はA", "DD2%警告", "DD1.5%未満",
            "DD3%重点再評価", "DD2.5%未満", "一定時間",
            "安全確認", "DD4%・5%", "別途決定",
        ):
            self.assertIn(term, excerpt)

    def test_dd_level_requirement_still_unapproved(self):
        reg = json.loads((ROOT / "specs/reconciliation_registry.json").read_text(encoding="utf-8"))
        pri = json.loads((ROOT / "specs/source_review_priority.json").read_text(encoding="utf-8"))
        r = next(row for row in reg["items"] if row["requirement_id"] == "FX-SAF-006")
        p = next(row for row in pri["items"] if row["requirement_id"] == "FX-SAF-006")
        self.assertIn("Q124", r["question_ids"])
        self.assertIn("Q124", p["question_ids"])
        self.assertFalse(r["implementation_approved"])
        self.assertIsNone(r["owner_approval"])
        self.assertFalse(p["human_safety_approval"])
        self.assertEqual(p["source_review"], "PENDING_ORIGINAL")

    def test_both_release_limits_are_strict_and_stops_remain_latched(self):
        doc = (ROOT / "specs/safety_foundation.md").read_text(encoding="utf-8")
        section = doc.split("## Q124：", 1)[1].split("\n## ", 1)[0]
        for term in (
            "DD < 1.5%", "DD < 2.5%", "厳密な不等号",
            "継続確認期間", "安全確認", "DD4%/5%", "本人承認必須",
            "Q121/Q122", "未決", "implementation_approved=false",
        ):
            self.assertIn(term, section)


if __name__ == "__main__":
    unittest.main()
