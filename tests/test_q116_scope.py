"""Q116 decision: document traceability without accidental safety authorization."""
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class Q116DecisionTests(unittest.TestCase):
    def test_evidence_and_decision_excerpt(self):
        evidence = json.loads((ROOT / "specs/source_evidence.json").read_text(encoding="utf-8"))
        q116 = next(record for record in evidence["records"] if record["question_id"] == "Q116")
        self.assertEqual(q116["source_kind"], "ORIGINAL")
        self.assertEqual(q116["verification"], "DIRECT_CHAT")
        self.assertFalse(q116["owner_approved_for_safety"])
        excerpt = (ROOT / q116["excerpt_path"]).read_text(encoding="utf-8")
        for expected in ("第116問はA", "既存ポジション", "未約定注文", "新規注文候補", "計算不能", "別途決定"):
            self.assertIn(expected, excerpt)

    def test_reconciliation_remains_unapproved(self):
        registry = json.loads((ROOT / "specs/reconciliation_registry.json").read_text(encoding="utf-8"))
        priority = json.loads((ROOT / "specs/source_review_priority.json").read_text(encoding="utf-8"))
        indexed = {i["requirement_id"]: i for i in priority["items"]}
        for entry in registry["items"]:
            if entry["requirement_id"] not in ("FX-SAF-001", "FX-SAF-002"):
                continue
            ident = entry["requirement_id"]
            self.assertIn("Q116", entry["question_ids"])
            self.assertIn("Q116", indexed[ident]["question_ids"])
            self.assertFalse(entry["implementation_approved"])
            self.assertFalse(indexed[ident]["human_safety_approval"])
            self.assertEqual(indexed[ident]["source_review"], "PENDING_ORIGINAL")

    def test_scope_is_documented_and_no_live_authorization(self):
        risk = (ROOT / "specs/safety_foundation.md").read_text(encoding="utf-8")
        self.assertIn("Q116：発注前リスク審査の対象範囲", risk)
        self.assertIn("合算", risk)
        self.assertIn("算定できない場合", risk)
        self.assertIn("未確定・実装用の承認待ち", risk)


if __name__ == "__main__":
    unittest.main()
