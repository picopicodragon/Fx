"""Q125 records 30-min sustained DD monitor recovery, not trading approval."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Q125DecisionTests(unittest.TestCase):
    def test_exact_user_choice_has_direct_chat_evidence(self):
        sources = json.loads((ROOT / "specs/source_evidence.json").read_text(encoding="utf-8"))
        record = next(r for r in sources["records"] if r["question_id"] == "Q125")
        self.assertEqual(record["source_kind"], "ORIGINAL")
        self.assertEqual(record["verification"], "DIRECT_CHAT")
        self.assertEqual(record["archive_locator_status"], "PENDING_LOCAL_ARCHIVE")
        self.assertFalse(record["owner_approved_for_safety"])
        excerpt = (ROOT / record["excerpt_path"]).read_text(encoding="utf-8")
        for phrase in (
            "第125問はA", "DD2%警告", "DD3%重点再評価", "30分間連続",
            "安全確認", "観測頻度", "途中悪化", "データ欠落",
            "再起動時", "DD4%・5%", "別途決定",
        ):
            self.assertIn(phrase, excerpt)

    def test_safety_requirement_stays_unapproved(self):
        recon = json.loads((ROOT / "specs/reconciliation_registry.json").read_text(encoding="utf-8"))
        priority = json.loads((ROOT / "specs/source_review_priority.json").read_text(encoding="utf-8"))
        a = next(r for r in recon["items"] if r["requirement_id"] == "FX-SAF-006")
        b = next(r for r in priority["items"] if r["requirement_id"] == "FX-SAF-006")
        self.assertIn("Q125", a["question_ids"])
        self.assertIn("Q125", b["question_ids"])
        self.assertFalse(a["implementation_approved"])
        self.assertIsNone(a["owner_approval"])
        self.assertFalse(b["human_safety_approval"])
        self.assertEqual(b["source_review"], "PENDING_ORIGINAL")

    def test_30_minutes_does_not_override_human_latched_trading_stop(self):
        c = (ROOT / "specs/safety_foundation.md").read_text(encoding="utf-8")
        section = c.split("## Q125：", 1)[1].split("\n## ", 1)[0]
        for phrase in (
            "1.5%未満", "2.5%未満", "30分間", "安全確認",
            "DD4%・5%", "本人の明示承認", "Q121",
            "未決", "implementation_approved=false",
        ):
            self.assertIn(phrase, section)


if __name__ == "__main__":
    unittest.main()
