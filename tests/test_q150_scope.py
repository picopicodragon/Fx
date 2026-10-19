"""Q150: two-second normal watchdog poll, not a failure threshold."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Q150DecisionTests(unittest.TestCase):
    def test_original_choice_and_option_recorded_separately(self):
        evidence = json.loads((ROOT / "specs/source_evidence.json").read_text(encoding="utf-8"))
        rec = next(x for x in evidence["records"] if x["question_id"] == "Q150")
        self.assertEqual(rec["source_kind"], "ORIGINAL")
        self.assertEqual(rec["verification"], "DIRECT_CHAT")
        self.assertEqual(rec["archive_locator_status"], "PENDING_LOCAL_ARCHIVE")
        self.assertFalse(rec["owner_approved_for_safety"])
        excerpt = (ROOT / rec["excerpt_path"]).read_text(encoding="utf-8")
        for term in (
            "第150問はBを採用する", "本人の直接発言ではない",
            "B：2秒間隔", "ハートビート", "計測連続性",
            "異常判定の時間閾値", "未決定",
        ):
            self.assertIn(term, excerpt)

    def test_poll_frequency_not_misread_as_failure_threshold(self):
        doc = (ROOT / "specs/safety_foundation.md").read_text(encoding="utf-8")
        section = doc.split("## Q150：", 1)[1].split("\n## ", 1)[0]
        for term in (
            "DD2%警告", "DD3%重点再評価",
            "独立ウォッチドッグ", "通常監視間隔を2秒",
            "Python", "EA", "ハートビート", "計測連続性",
            "Windows電源状態変更通知", "監視実行周期",
            "異常判定閾値ではない", "許容遅延", "欠落回数",
            "Q149", "判定不能", "Q148",
            "2回連続成功を無効", "Q126の30分計測をリセット",
            "安全検証を最初から", "30分計測再開", "自動解除を禁止",
            "Q145〜Q147", "60秒以上", "Windows単調増加時計",
            "Q133", "最大5分間有効・異常時即失効",
            "Q139〜Q143", "全体45秒", "並列測定",
            "DD4%・5%", "本人承認必須停止", "ほかの停止理由",
            "未決", "implementation_approved=false",
        ):
            self.assertIn(term, section)

    def test_approvals_stay_false_and_decision_unique(self):
        reg = json.loads((ROOT / "specs/reconciliation_registry.json").read_text(encoding="utf-8"))
        pri = json.loads((ROOT / "specs/source_review_priority.json").read_text(encoding="utf-8"))
        a = next(x for x in reg["items"] if x["requirement_id"] == "FX-SAF-006")
        b = next(x for x in pri["items"] if x["requirement_id"] == "FX-SAF-006")
        self.assertIn("Q150", a["question_ids"])
        self.assertIn("Q150", b["question_ids"])
        self.assertFalse(a["implementation_approved"])
        self.assertIsNone(a["owner_approval"])
        self.assertFalse(b["human_safety_approval"])
        self.assertEqual(b["source_review"], "PENDING_ORIGINAL")
        doc = (ROOT / "DECISIONS.md").read_text(encoding="utf-8")
        self.assertEqual(sum(x.startswith("| Q150 |") for x in doc.splitlines()), 1)
        self.assertIn("v15.0", (ROOT / "MASTER_SPEC.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
