"""Q118: daily loss threshold basis decision, never risk implementation approval."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Q118DecisionTests(unittest.TestCase):
    def test_evidence_matches_user_choice(self):
        evidence = json.loads((ROOT / "specs/source_evidence.json").read_text(encoding="utf-8"))
        record = next(x for x in evidence["records"] if x["question_id"] == "Q118")
        self.assertEqual(record["source_kind"], "ORIGINAL")
        self.assertEqual(record["verification"], "DIRECT_CHAT")
        self.assertFalse(record["owner_approved_for_safety"])
        self.assertEqual(record["archive_locator_status"], "PENDING_LOCAL_ARCHIVE")
        excerpt = (ROOT / record["excerpt_path"]).read_text(encoding="utf-8")
        for expected in ("第118問はA", "ニューヨーク17:00", "1.5%", "口座純資産", "翌取引日", "外部入出金", "別途決定"):
            self.assertIn(expected, excerpt)

    def test_traceability_and_unapproved_implementation(self):
        reconciliation = json.loads((ROOT / "specs/reconciliation_registry.json").read_text(encoding="utf-8"))
        priority = json.loads((ROOT / "specs/source_review_priority.json").read_text(encoding="utf-8"))
        r = next(x for x in reconciliation["items"] if x["requirement_id"] == "FX-SAF-003")
        p = next(x for x in priority["items"] if x["requirement_id"] == "FX-SAF-003")
        self.assertIn("Q118", r["question_ids"])
        self.assertIn("Q118", p["question_ids"])
        self.assertFalse(r["implementation_approved"])
        self.assertFalse(p["human_safety_approval"])
        self.assertEqual(p["source_review"], "PENDING_ORIGINAL")
        foundation = (ROOT / "specs/safety_foundation.md").read_text(encoding="utf-8")
        self.assertIn("Q118：日次1.5%損失上限の基準純資産と固定期間", foundation)
        self.assertIn("翌取引日", foundation)
        self.assertIn("未決", foundation)


if __name__ == "__main__":
    unittest.main()
