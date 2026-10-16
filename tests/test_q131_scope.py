"""Q131: one-second clock error threshold for DD warning release, not trading approval."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Q131DecisionTests(unittest.TestCase):
    def test_original_choice_is_recorded_with_pending_archive_verification(self):
        manifest = json.loads((ROOT / "specs/source_evidence.json").read_text(encoding="utf-8"))
        rec = next(x for x in manifest["records"] if x["question_id"] == "Q131")
        self.assertEqual(rec["source_kind"], "ORIGINAL")
        self.assertEqual(rec["verification"], "DIRECT_CHAT")
        self.assertEqual(rec["archive_locator_status"], "PENDING_LOCAL_ARCHIVE")
        self.assertFalse(rec["owner_approved_for_safety"])
        quote = (ROOT / rec["excerpt_path"]).read_text(encoding="utf-8")
        for term in (
            "第131問はA", "DD2%警告", "DD3%重点再評価", "UTC基準",
            "絶対値を1秒以内", "1秒を超える場合", "同期状態",
            "欠測扱い", "30分計測", "測定不確かさ", "MT4サーバー時刻",
            "DD4%・5%", "別途決定",
        ):
            self.assertIn(term, quote)

    def test_fx_saf_006_remains_unapproved(self):
        registry = json.loads((ROOT / "specs/reconciliation_registry.json").read_text(encoding="utf-8"))
        priority = json.loads((ROOT / "specs/source_review_priority.json").read_text(encoding="utf-8"))
        a = next(x for x in registry["items"] if x["requirement_id"] == "FX-SAF-006")
        b = next(x for x in priority["items"] if x["requirement_id"] == "FX-SAF-006")
        self.assertIn("Q131", a["question_ids"])
        self.assertIn("Q131", b["question_ids"])
        self.assertFalse(a["implementation_approved"])
        self.assertIsNone(a["owner_approval"])
        self.assertFalse(b["human_safety_approval"])
        self.assertEqual(b["source_review"], "PENDING_ORIGINAL")

    def test_clock_tolerance_does_not_release_human_latched_stop(self):
        doc = (ROOT / "specs/safety_foundation.md").read_text(encoding="utf-8")
        sec = doc.split("## Q131：", 1)[1].split("\n## ", 1)[0]
        for term in (
            "UTC基準", "絶対値1秒以内", "1秒を超えた場合",
            "同期状態", "時計誤差", "欠測", "Q126", "30分計測",
            "15秒", "10秒", "DD4%・5%", "本人承認必須停止",
            "測定不確かさ", "同期確認頻度", "MT4サーバー時刻",
            "未決", "implementation_approved=false",
        ):
            self.assertIn(term, sec)


if __name__ == "__main__":
    unittest.main()
