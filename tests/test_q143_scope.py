"""Q143: independent parallel time-source verification retains fail-closed DD gates."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Q143DecisionTests(unittest.TestCase):
    def test_user_choice_is_direct_and_historical_archive_pending(self):
        evidence = json.loads((ROOT / "specs/source_evidence.json").read_text(encoding="utf-8"))
        rec = next(x for x in evidence["records"] if x["question_id"] == "Q143")
        self.assertEqual(rec["source_kind"], "ORIGINAL")
        self.assertEqual(rec["verification"], "DIRECT_CHAT")
        self.assertEqual(rec["archive_locator_status"], "PENDING_LOCAL_ARCHIVE")
        self.assertFalse(rec["owner_approved_for_safety"])
        excerpt = (ROOT / rec["excerpt_path"]).read_text(encoding="utf-8")
        for s in (
            "第143問はA", "DD2%警告", "DD3%重点再評価",
            "測定を同時期に開始", "各系独立に往復時刻測定",
            "並列測定方式", "第142問", "45秒上限",
            "第141問", "タイムアウト2秒", "測定間隔1秒",
            "第140問", "最大5回試行", "第139問",
            "最低3回の有効測定", "第137〜138問",
            "自動解除を禁止", "第126問", "30分計測をリセット",
            "予備切替と両系有効測定必須条件の整合",
            "実行スケジューリング", "第133問",
            "DD4%・5%", "別途決定",
        ):
            self.assertIn(s, excerpt)

    def test_safety_registry_approval_not_granted(self):
        registry = json.loads((ROOT / "specs/reconciliation_registry.json").read_text(encoding="utf-8"))
        priority = json.loads((ROOT / "specs/source_review_priority.json").read_text(encoding="utf-8"))
        a = next(x for x in registry["items"] if x["requirement_id"] == "FX-SAF-006")
        b = next(x for x in priority["items"] if x["requirement_id"] == "FX-SAF-006")
        self.assertIn("Q143", a["question_ids"])
        self.assertIn("Q143", b["question_ids"])
        self.assertFalse(a["implementation_approved"])
        self.assertIsNone(a["owner_approval"])
        self.assertFalse(b["human_safety_approval"])
        self.assertEqual(b["source_review"], "PENDING_ORIGINAL")

    def test_parallel_only_does_not_bypass_validation_or_human_stops(self):
        doc = (ROOT / "specs/safety_foundation.md").read_text(encoding="utf-8")
        sec = doc.split("## Q143：", 1)[1].split("\n## ", 1)[0]
        for s in (
            "測定を同時期に開始", "各系独立に往復時刻測定",
            "並列測定方式", "Q142", "45秒上限",
            "Q141", "タイムアウト2秒", "測定間隔1秒",
            "Q140", "最大5回試行", "Q139", "最低3回の有効測定",
            "Q138", "測定不確かさ", "2秒超",
            "検証不能", "自動解除を禁止", "Q126", "30分計測をリセット",
            "主系障害時の予備切替", "両系有効測定必須条件の整合",
            "実行スケジューリング", "未決", "Q133", "即失効",
            "DD4%・5%", "本人承認必須停止", "ほかの停止理由",
            "implementation_approved=false",
        ):
            self.assertIn(s, sec)


if __name__ == "__main__":
    unittest.main()
