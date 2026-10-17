"""Q139 minimum three valid measurements per each UTC time source."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Q139DecisionTests(unittest.TestCase):
    def test_original_direct_choice_preserved_and_approval_pending(self):
        manifest = json.loads((ROOT / "specs/source_evidence.json").read_text(encoding="utf-8"))
        rec = next(x for x in manifest["records"] if x["question_id"] == "Q139")
        self.assertEqual(rec["source_kind"], "ORIGINAL")
        self.assertEqual(rec["verification"], "DIRECT_CHAT")
        self.assertEqual(rec["archive_locator_status"], "PENDING_LOCAL_ARCHIVE")
        self.assertFalse(rec["owner_approved_for_safety"])
        excerpt = (ROOT / rec["excerpt_path"]).read_text(encoding="utf-8")
        for term in (
            "第139問はA", "DD2%警告", "DD3%重点再評価",
            "主時刻サーバーと予備時刻サーバーのそれぞれ",
            "最低3回の有効な往復時刻測定", "有効測定回数を確保できない",
            "第138問", "測定不確かさ", "第137問", "2秒超",
            "検証不能", "自動解除を禁止", "第126問",
            "30分計測をリセット", "測定間隔", "最大試行回数",
            "サンプル品質", "採用・除外方法", "遅延上限",
            "第133問", "DD4%・5%", "別途決定",
        ):
            self.assertIn(term, excerpt)

    def test_fx_saf_006_still_lacks_safety_approvals(self):
        registry = json.loads((ROOT / "specs/reconciliation_registry.json").read_text(encoding="utf-8"))
        priority = json.loads((ROOT / "specs/source_review_priority.json").read_text(encoding="utf-8"))
        a = next(x for x in registry["items"] if x["requirement_id"] == "FX-SAF-006")
        b = next(x for x in priority["items"] if x["requirement_id"] == "FX-SAF-006")
        self.assertIn("Q139", a["question_ids"])
        self.assertIn("Q139", b["question_ids"])
        self.assertFalse(a["implementation_approved"])
        self.assertIsNone(a["owner_approval"])
        self.assertFalse(b["human_safety_approval"])
        self.assertEqual(b["source_review"], "PENDING_ORIGINAL")

    def test_sample_minimum_per_source_does_not_auto_approve_release(self):
        doc = (ROOT / "specs/safety_foundation.md").read_text(encoding="utf-8")
        sec = doc.split("## Q139：", 1)[1].split("\n## ", 1)[0]
        for term in (
            "主時刻サーバーと予備時刻サーバーそれぞれ",
            "最低3回の有効な往復時刻測定", "合計が3回",
            "有効測定", "検証不能", "測定不確かさ",
            "2秒超", "自動解除を禁止", "Q126",
            "30分計測をリセット", "Q133", "即失効",
            "測定間隔", "最大試行回数", "サンプル品質",
            "採用・除外方法", "遅延上限", "未決",
            "DD4%・5%", "本人承認必須停止",
            "ほかの停止理由", "implementation_approved=false",
        ):
            self.assertIn(term, sec)


if __name__ == "__main__":
    unittest.main()
