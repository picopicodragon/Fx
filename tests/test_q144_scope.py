"""Q144: backup time source may be used for clock recovery, never unilateral DD release."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Q144DecisionTests(unittest.TestCase):
    def test_direct_user_choice_archived_but_historical_cross_check_pending(self):
        evidence = json.loads((ROOT / "specs/source_evidence.json").read_text(encoding="utf-8"))
        rec = next(x for x in evidence["records"] if x["question_id"] == "Q144")
        self.assertEqual(rec["source_kind"], "ORIGINAL")
        self.assertEqual(rec["verification"], "DIRECT_CHAT")
        self.assertEqual(rec["archive_locator_status"], "PENDING_LOCAL_ARCHIVE")
        self.assertFalse(rec["owner_approved_for_safety"])
        excerpt = (ROOT / rec["excerpt_path"]).read_text(encoding="utf-8")
        for value in (
            "第144問はA", "DD2%警告", "DD3%重点再評価",
            "主時刻サーバーの障害時", "第134問",
            "予備時刻サーバーへ自動切替", "第139問",
            "主・予備それぞれ最低3回の有効測定",
            "監視レベルの自動解除を禁止", "UTC時計誤差・時刻一致性",
            "30分計測を再開せず", "第126問", "計測をリセット",
            "時計管理・障害復旧", "自動解除許可とはしない",
            "主系復旧判定", "予備側の継続運用", "通知",
            "第133問", "即失効条件", "第142問",
            "45秒全体上限", "DD4%・5%", "別途決定",
        ):
            self.assertIn(value, excerpt)

    def test_safety_requirement_still_unapproved(self):
        reg = json.loads((ROOT / "specs/reconciliation_registry.json").read_text(encoding="utf-8"))
        priority = json.loads((ROOT / "specs/source_review_priority.json").read_text(encoding="utf-8"))
        a = next(x for x in reg["items"] if x["requirement_id"] == "FX-SAF-006")
        b = next(x for x in priority["items"] if x["requirement_id"] == "FX-SAF-006")
        self.assertIn("Q144", a["question_ids"])
        self.assertIn("Q144", b["question_ids"])
        self.assertFalse(a["implementation_approved"])
        self.assertIsNone(a["owner_approval"])
        self.assertFalse(b["human_safety_approval"])
        self.assertEqual(b["source_review"], "PENDING_ORIGINAL")

    def test_backup_switching_cannot_bypass_both_source_measurements(self):
        doc = (ROOT / "specs/safety_foundation.md").read_text(encoding="utf-8")
        sec = doc.split("## Q144：", 1)[1].split("\n## ", 1)[0]
        for term in (
            "主系障害時", "予備時刻サーバーへの自動切替",
            "時計管理・障害復旧", "Q134", "Q139",
            "主系・予備系それぞれ最低3回の有効測定",
            "UTC時計誤差・時刻一致性の安全確認",
            "自動解除を禁止", "30分計測を再開しない",
            "検証不能時はQ126に従って30分計測をリセット",
            "Q133", "異常時即失効", "Q142", "全体45秒上限",
            "主系復旧判定", "予備側の継続運用", "通知",
            "未決", "DD4%・5%", "本人承認必須停止",
            "ほかの停止理由", "implementation_approved=false",
        ):
            self.assertIn(term, sec)

    def test_q143_parallel_measurements_still_required(self):
        doc = (ROOT / "specs/safety_foundation.md").read_text(encoding="utf-8")
        sec = doc.split("## Q143：", 1)[1].split("\n## ", 1)[0]
        self.assertIn("並列測定方式", sec)
        self.assertIn("両系有効測定必須条件の整合", sec)
        self.assertIn("Q144で決定", sec)


if __name__ == "__main__":
    unittest.main()
