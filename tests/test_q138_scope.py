"""Q138: latency-aware round-trip clock comparison with measurement uncertainty."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Q138DecisionTests(unittest.TestCase):
    def test_verbatim_choice_and_unverified_original_archive(self):
        evidence = json.loads((ROOT / "specs/source_evidence.json").read_text(encoding="utf-8"))
        rec = next(x for x in evidence["records"] if x["question_id"] == "Q138")
        self.assertEqual(rec["source_kind"], "ORIGINAL")
        self.assertEqual(rec["verification"], "DIRECT_CHAT")
        self.assertEqual(rec["archive_locator_status"], "PENDING_LOCAL_ARCHIVE")
        self.assertFalse(rec["owner_approved_for_safety"])
        excerpt = (ROOT / rec["excerpt_path"]).read_text(encoding="utf-8")
        for term in (
            "第138問はA", "DD2%警告", "DD3%重点再評価",
            "往復通信の送受信時刻", "時刻源の応答時刻",
            "通信遅延", "同一基準時点", "UTC時刻差",
            "測定不確かさも評価", "第137問", "2秒超",
            "検証不能", "監視レベル自動解除を禁止", "第126問",
            "30分計測をリセット", "測定回数", "遅延上限",
            "補正算法", "不確かさの算定・許容条件",
            "第133問", "DD4%・5%",
        ):
            self.assertIn(term, excerpt)

    def test_critical_requirement_remains_unapproved(self):
        registry = json.loads((ROOT / "specs/reconciliation_registry.json").read_text(encoding="utf-8"))
        priority = json.loads((ROOT / "specs/source_review_priority.json").read_text(encoding="utf-8"))
        a = next(x for x in registry["items"] if x["requirement_id"] == "FX-SAF-006")
        b = next(x for x in priority["items"] if x["requirement_id"] == "FX-SAF-006")
        self.assertIn("Q138", a["question_ids"])
        self.assertIn("Q138", b["question_ids"])
        self.assertFalse(a["implementation_approved"])
        self.assertIsNone(a["owner_approval"])
        self.assertFalse(b["human_safety_approval"])
        self.assertEqual(b["source_review"], "PENDING_ORIGINAL")

    def test_uncertain_two_second_comparison_disables_release(self):
        doc = (ROOT / "specs/safety_foundation.md").read_text(encoding="utf-8")
        sec = doc.split("## Q138：", 1)[1].split("\n## ", 1)[0]
        for term in (
            "往復通信の送信時刻・受信時刻", "時刻源の応答時刻",
            "通信遅延", "同一基準時点", "測定不確かさも評価",
            "2秒超", "検証不能", "自動解除を禁止",
            "Q126", "30分計測をリセット", "Q133", "即失効",
            "測定回数", "遅延上限", "補正算法", "算定方法・許容条件",
            "未決", "DD4%・5%", "本人承認必須停止",
            "ほかの停止理由", "implementation_approved=false",
        ):
            self.assertIn(term, sec)


if __name__ == "__main__":
    unittest.main()
