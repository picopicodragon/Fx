"""Q130 documents UTC clock sync requirement for DD monitoring release only."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Q130DecisionTests(unittest.TestCase):
    def test_direct_user_choice_is_captured_without_safety_approval(self):
        evidence = json.loads((ROOT / "specs/source_evidence.json").read_text(encoding="utf-8"))
        record = next(x for x in evidence["records"] if x["question_id"] == "Q130")
        self.assertEqual(record["source_kind"], "ORIGINAL")
        self.assertEqual(record["verification"], "DIRECT_CHAT")
        self.assertEqual(record["archive_locator_status"], "PENDING_LOCAL_ARCHIVE")
        self.assertFalse(record["owner_approved_for_safety"])
        excerpt = (ROOT / record["excerpt_path"]).read_text(encoding="utf-8")
        for term in (
            "第130問はA", "DD2%警告", "DD3%重点再評価",
            "UTC基準", "Windowsの時刻同期機能",
            "外部時刻サーバー", "同期状態と誤差",
            "検証できない", "欠測扱い", "30分計測",
            "許容時計誤差", "同期確認頻度", "MT4サーバー時刻",
            "DD4%・5%", "別途決定",
        ):
            self.assertIn(term, excerpt)

    def test_fx_saf_006_stays_unapproved(self):
        registry = json.loads((ROOT / "specs/reconciliation_registry.json").read_text(encoding="utf-8"))
        priority = json.loads((ROOT / "specs/source_review_priority.json").read_text(encoding="utf-8"))
        a = next(x for x in registry["items"] if x["requirement_id"] == "FX-SAF-006")
        b = next(x for x in priority["items"] if x["requirement_id"] == "FX-SAF-006")
        self.assertIn("Q130", a["question_ids"])
        self.assertIn("Q130", b["question_ids"])
        self.assertFalse(a["implementation_approved"])
        self.assertIsNone(a["owner_approval"])
        self.assertFalse(b["human_safety_approval"])
        self.assertEqual(b["source_review"], "PENDING_ORIGINAL")

    def test_utc_synchronization_failure_is_fail_closed(self):
        s = (ROOT / "specs/safety_foundation.md").read_text(encoding="utf-8")
        q = s.split("## Q130：", 1)[1].split("\n## ", 1)[0]
        for term in (
            "UTC", "Windowsの時刻同期機能", "外部時刻サーバー",
            "同期状態", "時計誤差", "検証できない",
            "欠測扱い", "Q126", "30分計測", "リセット",
            "15秒", "10秒", "DD4%・5%", "未決",
            "MT4サーバー時刻", "implementation_approved=false",
        ):
            self.assertIn(term, q)


if __name__ == "__main__":
    unittest.main()
