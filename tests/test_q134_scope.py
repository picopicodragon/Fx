"""Q134: backup UTC time server failover decision with no safety implementation approval."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Q134DecisionTests(unittest.TestCase):
    def test_direct_user_choice_and_pending_archive_verification(self):
        evidence = json.loads((ROOT / "specs/source_evidence.json").read_text(encoding="utf-8"))
        rec = next(x for x in evidence["records"] if x["question_id"] == "Q134")
        self.assertEqual(rec["source_kind"], "ORIGINAL")
        self.assertEqual(rec["verification"], "DIRECT_CHAT")
        self.assertEqual(rec["archive_locator_status"], "PENDING_LOCAL_ARCHIVE")
        self.assertFalse(rec["owner_approved_for_safety"])
        excerpt = (ROOT / rec["excerpt_path"]).read_text(encoding="utf-8")
        for term in (
            "第134問はA", "DD2%警告", "DD3%重点再評価",
            "主時刻サーバーに障害", "予備時刻サーバーへ自動切替",
            "UTC同期状態", "第131問", "予備側でも検証できない",
            "第133問", "期限切れ・無効・不明", "欠測扱い",
            "30分計測", "第126問", "独立性", "時刻不一致",
            "DD4%・5%", "別途決定",
        ):
            self.assertIn(term, excerpt)

    def test_fx_saf_006_remains_unapproved(self):
        registry = json.loads((ROOT / "specs/reconciliation_registry.json").read_text(encoding="utf-8"))
        priority = json.loads((ROOT / "specs/source_review_priority.json").read_text(encoding="utf-8"))
        a = next(x for x in registry["items"] if x["requirement_id"] == "FX-SAF-006")
        b = next(x for x in priority["items"] if x["requirement_id"] == "FX-SAF-006")
        self.assertIn("Q134", a["question_ids"])
        self.assertIn("Q134", b["question_ids"])
        self.assertFalse(a["implementation_approved"])
        self.assertIsNone(a["owner_approval"])
        self.assertFalse(b["human_safety_approval"])
        self.assertEqual(b["source_review"], "PENDING_ORIGINAL")

    def test_fallback_does_not_bypass_stale_clock_or_human_stops(self):
        doc = (ROOT / "specs/safety_foundation.md").read_text(encoding="utf-8")
        sec = doc.split("## Q134：", 1)[1].split("\n## ", 1)[0]
        for term in (
            "予備時刻サーバーへ自動切替", "UTC同期状態", "Q131",
            "再検証", "Q133", "最大5分", "即失効",
            "期限切れ・無効・不明", "欠測扱い", "Q126", "30分計測",
            "15秒", "10秒", "独立性", "時刻不一致", "未決",
            "DD4%・5%", "本人承認必須停止", "implementation_approved=false",
        ):
            self.assertIn(term, sec)


if __name__ == "__main__":
    unittest.main()
