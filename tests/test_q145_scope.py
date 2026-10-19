"""Q145: independent twice-successful full clock verification before restarting DD monitor window."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Q145DecisionTests(unittest.TestCase):
    def test_verbatim_direct_choice_and_historical_archive_pending(self):
        data = json.loads((ROOT / "specs/source_evidence.json").read_text(encoding="utf-8"))
        rec = next(x for x in data["records"] if x["question_id"] == "Q145")
        self.assertEqual(rec["source_kind"], "ORIGINAL")
        self.assertEqual(rec["verification"], "DIRECT_CHAT")
        self.assertEqual(rec["archive_locator_status"], "PENDING_LOCAL_ARCHIVE")
        self.assertFalse(rec["owner_approved_for_safety"])
        excerpt = (ROOT / rec["excerpt_path"]).read_text(encoding="utf-8")
        for term in (
            "第145問はA", "DD2%警告", "DD3%重点再評価",
            "主・予備の両系有効測定", "UTC時計誤差",
            "時刻一致性", "測定不確かさの評価",
            "独立した2回の検証で連続成功", "30分計測の再開",
            "監視レベルの自動解除を禁止", "第126問",
            "30分計測をゼロから開始", "ほかの安全条件を全て",
            "検証間隔", "連続成功の有効性確認",
            "復旧異常時の例外", "通知", "第133問",
            "第139〜143問", "DD4%・5%", "別途決定",
        ):
            self.assertIn(term, excerpt)

    def test_safety_approval_not_granted(self):
        reg = json.loads((ROOT / "specs/reconciliation_registry.json").read_text(encoding="utf-8"))
        pri = json.loads((ROOT / "specs/source_review_priority.json").read_text(encoding="utf-8"))
        a = next(x for x in reg["items"] if x["requirement_id"] == "FX-SAF-006")
        b = next(x for x in pri["items"] if x["requirement_id"] == "FX-SAF-006")
        self.assertIn("Q145", a["question_ids"])
        self.assertIn("Q145", b["question_ids"])
        self.assertFalse(a["implementation_approved"])
        self.assertIsNone(a["owner_approval"])
        self.assertFalse(b["human_safety_approval"])
        self.assertEqual(b["source_review"], "PENDING_ORIGINAL")

    def test_two_independent_complete_validations_required_before_timer_restart(self):
        doc = (ROOT / "specs/safety_foundation.md").read_text(encoding="utf-8")
        sec = doc.split("## Q145：", 1)[1].split("\n## ", 1)[0]
        for term in (
            "独立した2回の時計検証全体の連続成功",
            "主系・予備系の両系有効測定",
            "UTC時計誤差", "時刻一致性",
            "測定不確かさの評価",
            "2回の検証", "30分計測の再開",
            "監視レベルの自動解除を禁止",
            "Q126", "30分計測をゼロから開始",
            "Q133", "最大5分間有効", "異常時即失効",
            "Q139", "最低3回の有効測定",
            "Q143", "45秒上限", "並列測定",
            "検証間隔", "連続成功の有効性確認",
            "復旧異常時の例外", "通知", "未決",
            "DD4%・5%", "本人承認必須停止",
            "ほかの停止理由", "implementation_approved=false",
        ):
            self.assertIn(term, sec)


if __name__ == "__main__":
    unittest.main()
