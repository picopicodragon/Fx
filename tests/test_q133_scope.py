"""Q133: clock verification validity and early invalidation for DD monitor release."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Q133DecisionTests(unittest.TestCase):
    def test_direct_user_choice_is_recorded(self):
        evidence = json.loads((ROOT / "specs/source_evidence.json").read_text(encoding="utf-8"))
        rec = next(x for x in evidence["records"] if x["question_id"] == "Q133")
        self.assertEqual(rec["source_kind"], "ORIGINAL")
        self.assertEqual(rec["verification"], "DIRECT_CHAT")
        self.assertEqual(rec["archive_locator_status"], "PENDING_LOCAL_ARCHIVE")
        self.assertFalse(rec["owner_approved_for_safety"])
        excerpt = (ROOT / rec["excerpt_path"]).read_text(encoding="utf-8")
        for term in (
            "第133問はA", "DD2%警告", "DD3%重点再評価",
            "最大5分間", "システム再起動", "時計変更", "同期異常",
            "直ちに失効", "追加検証", "再検証が成功しない",
            "無効・不明", "欠測扱い", "30分計測", "第126問",
            "測定不確かさ", "外部時刻サーバー障害", "DD4%・5%",
        ):
            self.assertIn(term, excerpt)

    def test_fx_saf_006_stays_unapproved(self):
        registry = json.loads((ROOT / "specs/reconciliation_registry.json").read_text(encoding="utf-8"))
        priority = json.loads((ROOT / "specs/source_review_priority.json").read_text(encoding="utf-8"))
        a = next(x for x in registry["items"] if x["requirement_id"] == "FX-SAF-006")
        b = next(x for x in priority["items"] if x["requirement_id"] == "FX-SAF-006")
        self.assertIn("Q133", a["question_ids"])
        self.assertIn("Q133", b["question_ids"])
        self.assertFalse(a["implementation_approved"])
        self.assertIsNone(a["owner_approval"])
        self.assertFalse(b["human_safety_approval"])
        self.assertEqual(b["source_review"], "PENDING_ORIGINAL")

    def test_clock_validity_cannot_override_dd_stop_or_data_freshness(self):
        doc = (ROOT / "specs/safety_foundation.md").read_text(encoding="utf-8")
        section = doc.split("## Q133：", 1)[1].split("\n## ", 1)[0]
        for term in (
            "最大5分間", "システム再起動", "時計変更", "同期状態の異常",
            "直ちに失効", "追加検証", "再検証が成功しない",
            "無効・不明", "欠測扱い", "Q126", "30分計測",
            "5分周期", "絶対値1秒以内", "15秒データ鮮度",
            "10秒DD観測", "DD4%・5%", "本人承認必須停止",
            "未決", "implementation_approved=false",
        ):
            self.assertIn(term, section)


if __name__ == "__main__":
    unittest.main()
