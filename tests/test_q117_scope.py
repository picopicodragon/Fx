"""Q117 decision evidence and safe unresolved denominator."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Q117DecisionTests(unittest.TestCase):
    def test_direct_choice_excerpt(self):
        evidence = json.loads((ROOT / "specs/source_evidence.json").read_text(encoding="utf-8"))
        q = next(item for item in evidence["records"] if item["question_id"] == "Q117")
        self.assertEqual(q["verification"], "DIRECT_CHAT")
        self.assertFalse(q["owner_approved_for_safety"])
        excerpt = (ROOT / q["excerpt_path"]).read_text(encoding="utf-8")
        for phrase in ("第117問はA", "ニューヨーク17:00", "口座純資産", "外部入出金", "独立照合", "別途決定"):
            self.assertIn(phrase, excerpt)

    def test_fx_saf_003_unapproved_and_denominator_pending(self):
        recon = json.loads((ROOT / "specs/reconciliation_registry.json").read_text(encoding="utf-8"))
        prio = json.loads((ROOT / "specs/source_review_priority.json").read_text(encoding="utf-8"))
        a = next(item for item in recon["items"] if item["requirement_id"] == "FX-SAF-003")
        b = next(item for item in prio["items"] if item["requirement_id"] == "FX-SAF-003")
        self.assertIn("Q117", a["question_ids"])
        self.assertIn("Q117", b["question_ids"])
        self.assertFalse(a["implementation_approved"])
        self.assertFalse(b["human_safety_approval"])
        self.assertEqual(b["source_review"], "PENDING_ORIGINAL")
        foundation = (ROOT / "specs/safety_foundation.md").read_text(encoding="utf-8")
        self.assertIn("Q117：日次損失の主計算方式", foundation)
        self.assertIn("Q118", foundation)
        self.assertIn("未決", foundation)


if __name__ == "__main__":
    unittest.main()
