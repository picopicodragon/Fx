"""Q136: time-source disagreement must fail closed for DD warning release."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Q136DecisionTests(unittest.TestCase):
    def test_direct_decision_is_saved_with_unverified_archive_flag(self):
        evidence = json.loads((ROOT / "specs/source_evidence.json").read_text(encoding="utf-8"))
        rec = next(x for x in evidence["records"] if x["question_id"] == "Q136")
        self.assertEqual(rec["source_kind"], "ORIGINAL")
        self.assertEqual(rec["verification"], "DIRECT_CHAT")
        self.assertEqual(rec["archive_locator_status"], "PENDING_LOCAL_ARCHIVE")
        self.assertFalse(rec["owner_approved_for_safety"])
        excerpt = (ROOT / rec["excerpt_path"]).read_text(encoding="utf-8")
        for term in (
            "第136問はA", "DD2%警告", "DD3%重点再評価",
            "主時刻サーバー", "予備時刻サーバー", "所定の判定条件",
            "安全側停止型", "時計検証結果を無効", "自動解除を禁止",
            "第126問", "30分計測をリセット", "回復するまで再計測しない",
            "具体的な閾値", "測定不確かさ", "第133問",
            "DD4%・5%", "別途決定",
        ):
            self.assertIn(term, excerpt)

    def test_fx_saf_006_stays_unapproved(self):
        reg = json.loads((ROOT / "specs/reconciliation_registry.json").read_text(encoding="utf-8"))
        priority = json.loads((ROOT / "specs/source_review_priority.json").read_text(encoding="utf-8"))
        a = next(x for x in reg["items"] if x["requirement_id"] == "FX-SAF-006")
        b = next(x for x in priority["items"] if x["requirement_id"] == "FX-SAF-006")
        self.assertIn("Q136", a["question_ids"])
        self.assertIn("Q136", b["question_ids"])
        self.assertFalse(a["implementation_approved"])
        self.assertIsNone(a["owner_approval"])
        self.assertFalse(b["human_safety_approval"])
        self.assertEqual(b["source_review"], "PENDING_ORIGINAL")

    def test_disagreement_fail_closed_and_human_stops_preserved(self):
        doc = (ROOT / "specs/safety_foundation.md").read_text(encoding="utf-8")
        sec = doc.split("## Q136：", 1)[1].split("\n## ", 1)[0]
        for term in (
            "時刻不一致", "所定の判定条件", "時計検証結果を無効化",
            "監視レベルの自動解除を禁止", "Q126", "30分計測をリセット",
            "安全確認が回復するまで再計測しない", "絶対値1秒以内",
            "Q133", "即失効", "具体的な閾値", "測定不確かさ",
            "未決", "DD4%・5%", "本人承認必須停止",
            "ほかの停止理由", "implementation_approved=false",
        ):
            self.assertIn(term, sec)


if __name__ == "__main__":
    unittest.main()
