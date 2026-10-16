"""Q128 decision: 15-second freshness for DD warning-release observations only."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Q128DecisionTests(unittest.TestCase):
    def test_direct_user_excerpt_has_scope_and_pending_exceptions(self):
        data = json.loads((ROOT / "specs/source_evidence.json").read_text(encoding="utf-8"))
        q = next(x for x in data["records"] if x["question_id"] == "Q128")
        self.assertEqual(q["source_kind"], "ORIGINAL")
        self.assertEqual(q["verification"], "DIRECT_CHAT")
        self.assertEqual(q["archive_locator_status"], "PENDING_LOCAL_ARCHIVE")
        self.assertFalse(q["owner_approved_for_safety"])
        original = (ROOT / q["excerpt_path"]).read_text(encoding="utf-8")
        for term in (
            "第128問はA", "DD2%警告", "DD3%重点再評価", "30分間",
            "15秒", "10秒周期", "鮮度・有効性", "欠測扱い",
            "第126問", "リセット", "元データ時刻", "時刻管理",
            "DD4%・5%", "別途決定",
        ):
            self.assertIn(term, original)

    def test_saf_006_has_no_implementation_approval(self):
        registry = json.loads((ROOT / "specs/reconciliation_registry.json").read_text(encoding="utf-8"))
        priority = json.loads((ROOT / "specs/source_review_priority.json").read_text(encoding="utf-8"))
        r = next(x for x in registry["items"] if x["requirement_id"] == "FX-SAF-006")
        p = next(x for x in priority["items"] if x["requirement_id"] == "FX-SAF-006")
        self.assertIn("Q128", r["question_ids"])
        self.assertIn("Q128", p["question_ids"])
        self.assertFalse(r["implementation_approved"])
        self.assertIsNone(r["owner_approval"])
        self.assertFalse(p["human_safety_approval"])
        self.assertEqual(p["source_review"], "PENDING_ORIGINAL")

    def test_15s_data_freshness_remains_warning_release_only(self):
        doc = (ROOT / "specs/safety_foundation.md").read_text(encoding="utf-8")
        sec = doc.split("## Q128：", 1)[1].split("\n## ", 1)[0]
        for term in (
            "DD2%警告", "DD3%重点再評価", "10秒周期", "15秒",
            "欠測", "Q126", "リセット", "時刻管理", "未決",
            "DD4%・5%", "他の停止理由", "implementation_approved=false",
        ):
            self.assertIn(term, sec)


if __name__ == "__main__":
    unittest.main()
