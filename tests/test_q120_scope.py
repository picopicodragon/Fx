"""Q120 tracks fail-safe liquidation reattempt selection but never grants trading approval."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Q120DecisionTests(unittest.TestCase):
    def test_user_message_saved_with_precise_pending_fields(self):
        evidence = json.loads((ROOT / "specs/source_evidence.json").read_text(encoding="utf-8"))
        rec = next(x for x in evidence["records"] if x["question_id"] == "Q120")
        self.assertEqual(rec["source_kind"], "ORIGINAL")
        self.assertEqual(rec["verification"], "DIRECT_CHAT")
        self.assertEqual(rec["archive_locator_status"], "PENDING_LOCAL_ARCHIVE")
        self.assertFalse(rec["owner_approved_for_safety"])
        excerpt = (ROOT / rec["excerpt_path"]).read_text(encoding="utf-8")
        for phrase in ("第120問はA", "新規注文停止", "残存ポジション", "注文状態", "SL", "重複決済", "重大障害通知", "別途決定"):
            self.assertIn(phrase, excerpt)

    def test_safety_specs_unapproved(self):
        reg = json.loads((ROOT / "specs/reconciliation_registry.json").read_text(encoding="utf-8"))
        pri = json.loads((ROOT / "specs/source_review_priority.json").read_text(encoding="utf-8"))
        p_by_id = {x["requirement_id"]: x for x in pri["items"]}
        for entry in reg["items"]:
            if entry["requirement_id"] not in {"FX-SAF-003", "FX-SAF-005"}:
                continue
            self.assertIn("Q120", entry["question_ids"])
            self.assertFalse(entry["implementation_approved"])
            item = p_by_id[entry["requirement_id"]]
            self.assertIn("Q120", item["question_ids"])
            self.assertFalse(item["human_safety_approval"])
            self.assertEqual(item["source_review"], "PENDING_ORIGINAL")
        safety = (ROOT / "specs/safety_foundation.md").read_text(encoding="utf-8")
        self.assertIn("## Q120", safety)
        self.assertIn("重複決済", safety)
        self.assertIn("未決", safety)


if __name__ == "__main__":
    unittest.main()
