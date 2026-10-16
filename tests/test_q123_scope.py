"""Q123 records DD monitoring hysteresis; never grants DD stop release or trading approval."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Q123DecisionTests(unittest.TestCase):
    def test_exact_user_choice_has_direct_evidence(self):
        manifest = json.loads((ROOT / "specs/source_evidence.json").read_text(encoding="utf-8"))
        rec = next(x for x in manifest["records"] if x["question_id"] == "Q123")
        self.assertEqual(rec["source_kind"], "ORIGINAL")
        self.assertEqual(rec["verification"], "DIRECT_CHAT")
        self.assertEqual(rec["archive_locator_status"], "PENDING_LOCAL_ARCHIVE")
        self.assertFalse(rec["owner_approved_for_safety"])
        excerpt = (ROOT / rec["excerpt_path"]).read_text(encoding="utf-8")
        for word in (
            "第123問はA", "DD2%・3%", "ヒステリシス方式",
            "一定期間継続", "安全確認", "解除基準値", "継続時間",
            "DD4%・5%", "別途決定",
        ):
            self.assertIn(word, excerpt)

    def test_fx_saf_006_remains_unapproved(self):
        reg = json.loads((ROOT / "specs/reconciliation_registry.json").read_text(encoding="utf-8"))
        pri = json.loads((ROOT / "specs/source_review_priority.json").read_text(encoding="utf-8"))
        r = next(x for x in reg["items"] if x["requirement_id"] == "FX-SAF-006")
        p = next(x for x in pri["items"] if x["requirement_id"] == "FX-SAF-006")
        self.assertIn("Q123", r["question_ids"])
        self.assertIn("Q123", p["question_ids"])
        self.assertFalse(r["implementation_approved"])
        self.assertIsNone(r["owner_approval"])
        self.assertFalse(p["human_safety_approval"])
        self.assertEqual(p["source_review"], "PENDING_ORIGINAL")

    def test_warning_auto_release_not_human_latched_stop_release(self):
        doc = (ROOT / "specs/safety_foundation.md").read_text(encoding="utf-8")
        section = doc.split("## Q123：", 1)[1].split("\n## ", 1)[0]
        for term in (
            "ヒステリシス", "発動閾値", "一定期間継続", "安全確認",
            "DD4%/5%", "本人の明示承認", "他の停止理由",
            "未決", "implementation_approved=false",
        ):
            self.assertIn(term, section)


if __name__ == "__main__":
    unittest.main()
