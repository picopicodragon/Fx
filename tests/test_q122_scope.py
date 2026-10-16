"""Q122 records conditional DD monitor-level release without trading approval."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IDS = {"FX-SAF-005", "FX-SAF-006"}


class Q122DecisionTests(unittest.TestCase):
    def test_direct_chat_evidence_and_exact_selection(self):
        manifest = json.loads((ROOT / "specs/source_evidence.json").read_text(encoding="utf-8"))
        rec = next(x for x in manifest["records"] if x["question_id"] == "Q122")
        self.assertEqual(rec["source_kind"], "ORIGINAL")
        self.assertEqual(rec["verification"], "DIRECT_CHAT")
        self.assertEqual(rec["archive_locator_status"], "PENDING_LOCAL_ARCHIVE")
        self.assertFalse(rec["owner_approved_for_safety"])
        excerpt = (ROOT / rec["excerpt_path"]).read_text(encoding="utf-8")
        for expected in (
            "第122問はA", "DD2%", "3%", "DD4%・5%", "安全確認",
            "自動解除", "人間の明示承認", "ほかの停止理由", "別途決定",
        ):
            self.assertIn(expected, excerpt)

    def test_dd_requirements_are_unapproved(self):
        registry = json.loads((ROOT / "specs/reconciliation_registry.json").read_text(encoding="utf-8"))
        priority = json.loads((ROOT / "specs/source_review_priority.json").read_text(encoding="utf-8"))
        a = {x["requirement_id"]: x for x in registry["items"]}
        b = {x["requirement_id"]: x for x in priority["items"]}
        for ident in IDS:
            self.assertIn("Q122", a[ident]["question_ids"])
            self.assertIn("Q122", b[ident]["question_ids"])
            self.assertFalse(a[ident]["implementation_approved"])
            self.assertIsNone(a[ident]["owner_approval"])
            self.assertFalse(b[ident]["human_safety_approval"])
            self.assertEqual(b[ident]["source_review"], "PENDING_ORIGINAL")

    def test_warning_release_is_not_trade_stop_release(self):
        doc = (ROOT / "specs/safety_foundation.md").read_text(encoding="utf-8")
        section = doc.split("## Q122：", 1)[1].split("\n## ", 1)[0]
        for term in (
            "DD改善", "監視レベルを自動解除可能", "自動解除禁止", "本人の明示承認",
            "Q121", "独立", "未決", "implementation_approved=false",
        ):
            self.assertIn(term, section)
        self.assertIn("4%新規停止", doc)
        self.assertIn("5%で", doc)


if __name__ == "__main__":
    unittest.main()
