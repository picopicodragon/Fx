"""Q129 requires dual timestamp validation for DD monitor-release data."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Q129DecisionTests(unittest.TestCase):
    def test_direct_decision_and_pending_exceptions(self):
        evidence = json.loads((ROOT / "specs/source_evidence.json").read_text(encoding="utf-8"))
        q = next(x for x in evidence["records"] if x["question_id"] == "Q129")
        self.assertEqual(q["source_kind"], "ORIGINAL")
        self.assertEqual(q["verification"], "DIRECT_CHAT")
        self.assertEqual(q["archive_locator_status"], "PENDING_LOCAL_ARCHIVE")
        self.assertFalse(q["owner_approved_for_safety"])
        excerpt = (ROOT / q["excerpt_path"]).read_text(encoding="utf-8")
        for phrase in (
            "第129問はA", "DD2%警告", "DD3%重点再評価",
            "元データの生成・更新時刻", "システム受信時刻",
            "15秒を超える", "時刻が不明", "時刻整合性",
            "欠測扱い", "30分計測", "時計誤差", "別途決定",
        ):
            self.assertIn(phrase, excerpt)

    def test_fx_saf_006_stays_unapproved(self):
        reg = json.loads((ROOT / "specs/reconciliation_registry.json").read_text(encoding="utf-8"))
        pri = json.loads((ROOT / "specs/source_review_priority.json").read_text(encoding="utf-8"))
        r = next(x for x in reg["items"] if x["requirement_id"] == "FX-SAF-006")
        p = next(x for x in pri["items"] if x["requirement_id"] == "FX-SAF-006")
        self.assertIn("Q129", r["question_ids"])
        self.assertIn("Q129", p["question_ids"])
        self.assertFalse(r["implementation_approved"])
        self.assertIsNone(r["owner_approval"])
        self.assertFalse(p["human_safety_approval"])
        self.assertEqual(p["source_review"], "PENDING_ORIGINAL")

    def test_two_times_and_reset_do_not_clear_stops(self):
        doc = (ROOT / "specs/safety_foundation.md").read_text(encoding="utf-8")
        sec = doc.split("## Q129：", 1)[1].split("\n## ", 1)[0]
        for term in (
            "元データの生成・更新時刻", "システム受信時刻", "両方検証",
            "15秒を超える", "時刻", "欠測扱い", "Q126",
            "リセット", "10秒", "DD4%・5%", "本人承認",
            "未決", "implementation_approved=false",
        ):
            self.assertIn(term, sec)


if __name__ == "__main__":
    unittest.main()
