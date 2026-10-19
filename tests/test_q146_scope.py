"""Q146: enforce 60 seconds between full clock recovery validation successes."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Q146DecisionTests(unittest.TestCase):
    def test_direct_original_is_preserved_and_local_archive_still_pending(self):
        evidence = json.loads((ROOT / "specs/source_evidence.json").read_text(encoding="utf-8"))
        rec = next(x for x in evidence["records"] if x["question_id"] == "Q146")
        self.assertEqual(rec["source_kind"], "ORIGINAL")
        self.assertEqual(rec["verification"], "DIRECT_CHAT")
        self.assertEqual(rec["archive_locator_status"], "PENDING_LOCAL_ARCHIVE")
        self.assertFalse(rec["owner_approved_for_safety"])
        excerpt = (ROOT / rec["excerpt_path"]).read_text(encoding="utf-8")
        for word in (
            "第146問はA", "DD2%警告", "DD3%重点再評価",
            "1回目の検証成功から2回目の検証開始まで60秒以上",
            "主・予備両系の新たな有効測定",
            "UTC時計誤差・時刻一致性・測定不確かさの再評価",
            "時計異常", "検証失敗", "有効期限切れ",
            "連続成功と扱わず", "30分計測の再開",
            "監視レベル自動解除を禁止",
            "第126問", "30分計測をゼロから開始",
            "検証スケジューリング", "障害再発時の例外",
            "第133問", "第139〜143問", "DD4%・5%", "別途決定",
        ):
            self.assertIn(word, excerpt)

    def test_critical_requirement_remains_unapproved(self):
        registry = json.loads((ROOT / "specs/reconciliation_registry.json").read_text(encoding="utf-8"))
        priority = json.loads((ROOT / "specs/source_review_priority.json").read_text(encoding="utf-8"))
        reg = next(x for x in registry["items"] if x["requirement_id"] == "FX-SAF-006")
        pri = next(x for x in priority["items"] if x["requirement_id"] == "FX-SAF-006")
        self.assertIn("Q146", reg["question_ids"])
        self.assertIn("Q146", pri["question_ids"])
        self.assertFalse(reg["implementation_approved"])
        self.assertIsNone(reg["owner_approval"])
        self.assertFalse(pri["human_safety_approval"])
        self.assertEqual(pri["source_review"], "PENDING_ORIGINAL")

    def test_safe_gap_and_fresh_second_measurements(self):
        doc = (ROOT / "specs/safety_foundation.md").read_text(encoding="utf-8")
        section = doc.split("## Q146：", 1)[1].split("\n## ", 1)[0]
        for word in (
            "第1回の時計検証全体が成功した時点",
            "第2回の時計検証全体を開始するまで60秒以上",
            "主・予備両系の新たな有効測定",
            "UTC時計誤差・時刻一致性・測定不確かさを再評価",
            "時計異常・時計検証失敗・有効期限切れ等",
            "2回連続成功と扱わず",
            "30分計測の再開", "監視レベルの自動解除を禁止",
            "Q126", "30分計測をゼロから開始",
            "Q133", "最大5分間有効・異常時即失効",
            "Q139", "Q143", "全体45秒上限",
            "連続成功の有効性確認", "検証スケジューリング",
            "障害再発時の例外", "通知", "未決",
            "DD4%・5%", "本人承認必須停止",
            "ほかの停止理由", "implementation_approved=false",
        ):
            self.assertIn(word, section)

    def test_decision_log_has_unique_q145_q146_rows(self):
        doc = (ROOT / "DECISIONS.md").read_text(encoding="utf-8")
        self.assertEqual(sum(line.startswith("| Q145 |") for line in doc.splitlines()), 1)
        self.assertEqual(sum(line.startswith("| Q146 |") for line in doc.splitlines()), 1)
        self.assertEqual(sum(line.startswith("- **Q145追加：**") for line in doc.splitlines()), 1)


if __name__ == "__main__":
    unittest.main()
