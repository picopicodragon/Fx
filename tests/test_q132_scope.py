"""Q132: 5-minute clock checks with event-based revalidation; no trading approval."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Q132DecisionTests(unittest.TestCase):
    def test_direct_chat_decision_and_archive_pending(self):
        evidence = json.loads((ROOT / "specs/source_evidence.json").read_text(encoding="utf-8"))
        rec = next(x for x in evidence["records"] if x["question_id"] == "Q132")
        self.assertEqual(rec["source_kind"], "ORIGINAL")
        self.assertEqual(rec["verification"], "DIRECT_CHAT")
        self.assertEqual(rec["archive_locator_status"], "PENDING_LOCAL_ARCHIVE")
        self.assertFalse(rec["owner_approved_for_safety"])
        excerpt = (ROOT / rec["excerpt_path"]).read_text(encoding="utf-8")
        for term in (
            "第132問はB", "DD2%警告", "DD3%重点再評価",
            "原則5分周期", "システム再起動", "時計変更", "同期状態異常",
            "追加検証", "誤差超過", "欠測扱い", "30分計測",
            "検証結果の有効期限", "DD4%・5%",
        ):
            self.assertIn(term, excerpt)

    def test_fx_saf_006_approval_remains_pending(self):
        registry = json.loads((ROOT / "specs/reconciliation_registry.json").read_text(encoding="utf-8"))
        priority = json.loads((ROOT / "specs/source_review_priority.json").read_text(encoding="utf-8"))
        a = next(x for x in registry["items"] if x["requirement_id"] == "FX-SAF-006")
        b = next(x for x in priority["items"] if x["requirement_id"] == "FX-SAF-006")
        self.assertIn("Q132", a["question_ids"])
        self.assertIn("Q132", b["question_ids"])
        self.assertFalse(a["implementation_approved"])
        self.assertIsNone(a["owner_approval"])
        self.assertFalse(b["human_safety_approval"])
        self.assertEqual(b["source_review"], "PENDING_ORIGINAL")

    def test_clock_interval_does_not_override_data_freshness_or_stops(self):
        doc = (ROOT / "specs/safety_foundation.md").read_text(encoding="utf-8")
        section = doc.split("## Q132：", 1)[1].split("\n## ", 1)[0]
        for term in (
            "原則5分周期", "システム再起動", "時計変更",
            "追加検証", "絶対値1秒以内", "検証不能", "欠測扱い",
            "Q126", "30分計測", "10秒周期", "鮮度上限15秒",
            "検証結果の有効期限", "未決", "DD4%・5%",
            "ほかの停止理由", "implementation_approved=false",
        ):
            self.assertIn(term, section)


if __name__ == "__main__":
    unittest.main()
