"""Q137: cross-source clock time difference exceeding 2s must fail closed."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Q137DecisionTests(unittest.TestCase):
    def test_verbatim_user_decision_and_unreviewed_historic_archive(self):
        ev = json.loads((ROOT / "specs/source_evidence.json").read_text(encoding="utf-8"))
        record = next(x for x in ev["records"] if x["question_id"] == "Q137")
        self.assertEqual(record["source_kind"], "ORIGINAL")
        self.assertEqual(record["verification"], "DIRECT_CHAT")
        self.assertEqual(record["archive_locator_status"], "PENDING_LOCAL_ARCHIVE")
        self.assertFalse(record["owner_approved_for_safety"])
        excerpt = (ROOT / record["excerpt_path"]).read_text(encoding="utf-8")
        for term in (
            "第137問はA", "DD2%警告", "DD3%重点再評価",
            "同一基準時点", "絶対値が2秒を超えた場合",
            "第136問", "時計検証結果を無効化", "自動解除を禁止",
            "30分計測をリセット", "再計測しない",
            "通信遅延補正", "測定不確かさ", "別途決定",
            "第133問", "DD4%・5%",
        ):
            self.assertIn(term, excerpt)

    def test_fx_saf_006_stays_explicitly_unapproved(self):
        registry = json.loads((ROOT / "specs/reconciliation_registry.json").read_text(encoding="utf-8"))
        priority = json.loads((ROOT / "specs/source_review_priority.json").read_text(encoding="utf-8"))
        a = next(x for x in registry["items"] if x["requirement_id"] == "FX-SAF-006")
        b = next(x for x in priority["items"] if x["requirement_id"] == "FX-SAF-006")
        self.assertIn("Q137", a["question_ids"])
        self.assertIn("Q137", b["question_ids"])
        self.assertFalse(a["implementation_approved"])
        self.assertIsNone(a["owner_approval"])
        self.assertFalse(b["human_safety_approval"])
        self.assertEqual(b["source_review"], "PENDING_ORIGINAL")

    def test_two_second_exclusive_threshold_and_fail_closed_release(self):
        doc = (ROOT / "specs/safety_foundation.md").read_text(encoding="utf-8")
        sec = doc.split("## Q137：", 1)[1].split("\n## ", 1)[0]
        for term in (
            "同一基準時点", "時刻差の絶対値が2秒を超えた場合",
            "2秒ちょうど", "時計検証結果無効化",
            "自動解除禁止", "Q126", "30分計測をリセット",
            "安全確認が回復するまで再計測しない",
            "絶対値1秒以内", "Q133", "即失効",
            "測定方法", "通信遅延補正", "測定不確かさ",
            "未決", "DD4%・5%", "本人承認必須停止",
            "implementation_approved=false",
        ):
            self.assertIn(term, sec)


if __name__ == "__main__":
    unittest.main()
