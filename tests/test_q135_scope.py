"""Q135: independent primary and backup time-source selection, still unapproved."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Q135DecisionTests(unittest.TestCase):
    def test_original_choice_has_direct_chat_evidence(self):
        evidence = json.loads((ROOT / "specs/source_evidence.json").read_text(encoding="utf-8"))
        rec = next(x for x in evidence["records"] if x["question_id"] == "Q135")
        self.assertEqual(rec["source_kind"], "ORIGINAL")
        self.assertEqual(rec["verification"], "DIRECT_CHAT")
        self.assertEqual(rec["archive_locator_status"], "PENDING_LOCAL_ARCHIVE")
        self.assertFalse(rec["owner_approved_for_safety"])
        original = (ROOT / rec["excerpt_path"]).read_text(encoding="utf-8")
        for term in (
            "第135問はA", "DD2%警告", "DD3%重点再評価",
            "異なる運営主体", "異なる時刻提供インフラ",
            "事前に信頼性確認・登録", "UTC同期状態",
            "第131問", "再検証", "ネットワーク経路の独立性",
            "時刻不一致", "第133問", "第126問",
            "DD4%・5%", "別途決定",
        ):
            self.assertIn(term, original)

    def test_fx_saf_006_stays_unapproved(self):
        registry = json.loads((ROOT / "specs/reconciliation_registry.json").read_text(encoding="utf-8"))
        priority = json.loads((ROOT / "specs/source_review_priority.json").read_text(encoding="utf-8"))
        a = next(x for x in registry["items"] if x["requirement_id"] == "FX-SAF-006")
        b = next(x for x in priority["items"] if x["requirement_id"] == "FX-SAF-006")
        self.assertIn("Q135", a["question_ids"])
        self.assertIn("Q135", b["question_ids"])
        self.assertFalse(a["implementation_approved"])
        self.assertIsNone(a["owner_approval"])
        self.assertFalse(b["human_safety_approval"])
        self.assertEqual(b["source_review"], "PENDING_ORIGINAL")

    def test_independent_sources_do_not_allow_unsafe_release(self):
        doc = (ROOT / "specs/safety_foundation.md").read_text(encoding="utf-8")
        sec = doc.split("## Q135：", 1)[1].split("\n## ", 1)[0]
        for term in (
            "異なる運営主体", "異なる時刻提供インフラ",
            "事前に信頼性確認・登録", "Q131",
            "UTC同期状態", "再検証", "Q134", "Q133", "Q126",
            "ネットワーク経路の独立性", "時刻不一致",
            "未決", "DD4%・5%", "本人承認必須停止",
            "implementation_approved=false",
        ):
            self.assertIn(term, sec)


if __name__ == "__main__":
    unittest.main()
