"""Q121 must remain a directly evidenced design decision, never implementation authorization."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELEVANT = {
    "FX-SAF-003", "FX-SAF-004", "FX-SAF-005", "FX-SAF-006",
    "FX-SAF-011", "FX-SAF-013",
}


class Q121DecisionTests(unittest.TestCase):
    def test_exact_user_choice_is_tracked_as_direct_chat_only(self):
        evidence = json.loads((ROOT / "specs/source_evidence.json").read_text(encoding="utf-8"))
        record = next(r for r in evidence["records"] if r["question_id"] == "Q121")
        self.assertEqual(record["source_kind"], "ORIGINAL")
        self.assertEqual(record["verification"], "DIRECT_CHAT")
        self.assertEqual(record["archive_locator_status"], "PENDING_LOCAL_ARCHIVE")
        self.assertFalse(record["owner_approved_for_safety"])
        excerpt = (ROOT / record["excerpt_path"]).read_text(encoding="utf-8")
        for phrase in (
            "第121問はA", "日次損失", "通信障害", "DD4%・DD5%", "戦略悪化",
            "解除条件", "人間承認", "再起動後も保持", "状態不明", "別途決定",
        ):
            self.assertIn(phrase, excerpt)

    def test_all_affected_safety_requirements_remain_unapproved(self):
        registry = json.loads((ROOT / "specs/reconciliation_registry.json").read_text(encoding="utf-8"))
        priority = json.loads((ROOT / "specs/source_review_priority.json").read_text(encoding="utf-8"))
        recon_by_id = {x["requirement_id"]: x for x in registry["items"]}
        prior_by_id = {x["requirement_id"]: x for x in priority["items"]}
        for ident in RELEVANT:
            r, p = recon_by_id[ident], prior_by_id[ident]
            self.assertIn("Q121", r["question_ids"])
            self.assertIn("Q121", p["question_ids"])
            self.assertFalse(r["implementation_approved"])
            self.assertIsNone(r["owner_approval"])
            self.assertFalse(p["human_safety_approval"])
            self.assertEqual(p["source_review"], "PENDING_ORIGINAL")

    def test_fail_closed_stop_model_documented_but_not_implemented(self):
        doc = (ROOT / "specs/safety_foundation.md").read_text(encoding="utf-8")
        section = doc.split("## Q121：", 1)[1].split("\n## ", 1)[0]
        for item in (
            "個別状態", "全停止理由", "人間承認必須", "再起動後",
            "新規注文を禁止", "未決", "implementation_approved=false",
        ):
            self.assertIn(item, section)


if __name__ == "__main__":
    unittest.main()
