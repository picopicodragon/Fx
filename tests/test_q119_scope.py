"""Q119 adopted unitized DD approach, but remains an unapproved implementation."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Q119DecisionTests(unittest.TestCase):
    def test_source_excerpt_has_exact_decision_and_no_approval(self):
        data = json.loads((ROOT / "specs/source_evidence.json").read_text(encoding="utf-8"))
        record = next(x for x in data["records"] if x["question_id"] == "Q119")
        self.assertEqual(record["source_kind"], "ORIGINAL")
        self.assertEqual(record["verification"], "DIRECT_CHAT")
        self.assertEqual(record["archive_locator_status"], "PENDING_LOCAL_ARCHIVE")
        self.assertFalse(record["owner_approved_for_safety"])
        excerpt = (ROOT / record["excerpt_path"]).read_text(encoding="utf-8")
        for text in ("第119問はA", "仮想口数", "単位当たり純資産方式", "DD2%・3%・4%・5%", "別途決定"):
            self.assertIn(text, excerpt)

    def test_both_dd_safety_requirements_remain_unapproved(self):
        r = json.loads((ROOT / "specs/reconciliation_registry.json").read_text(encoding="utf-8"))
        p = json.loads((ROOT / "specs/source_review_priority.json").read_text(encoding="utf-8"))
        p_by_id = {x["requirement_id"]: x for x in p["items"]}
        for entry in r["items"]:
            if entry["requirement_id"] not in {"FX-SAF-005", "FX-SAF-006"}:
                continue
            self.assertIn("Q119", entry["question_ids"])
            self.assertFalse(entry["implementation_approved"])
            item = p_by_id[entry["requirement_id"]]
            self.assertIn("Q119", item["question_ids"])
            self.assertEqual(item["source_review"], "PENDING_ORIGINAL")
            self.assertFalse(item["human_safety_approval"])

    def test_base_risk_spec_does_not_change_thresholds(self):
        c = (ROOT / "specs/safety_foundation.md").read_text(encoding="utf-8")
        self.assertIn("## Q119", c)
        self.assertIn("DD2%警告", c)
        self.assertIn("3%重点再評価", c)
        self.assertIn("4%新規停止", c)
        self.assertIn("5%到達時", c)
        self.assertIn("未決", c)


if __name__ == "__main__":
    unittest.main()
