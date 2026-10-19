"""Q147: use monotonic elapsed clock for >=60s recovery validation spacing."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Q147DecisionTests(unittest.TestCase):
    def test_verbatim_direct_choice_and_unreviewed_local_archive(self):
        evidence = json.loads((ROOT / "specs/source_evidence.json").read_text(encoding="utf-8"))
        record = next(x for x in evidence["records"] if x["question_id"] == "Q147")
        self.assertEqual(record["source_kind"], "ORIGINAL")
        self.assertEqual(record["verification"], "DIRECT_CHAT")
        self.assertEqual(record["archive_locator_status"], "PENDING_LOCAL_ARCHIVE")
        self.assertFalse(record["owner_approved_for_safety"])
        excerpt = (ROOT / record["excerpt_path"]).read_text(encoding="utf-8")
        for term in (
            "第147問はA", "DD2%警告", "DD3%重点再評価",
            "第146問の60秒以上", "Windowsの単調増加時計",
            "UTCシステム時刻は別途記録",
            "同期状態と時計誤差を検証",
            "システム再起動", "計測の連続性喪失",
            "時計異常", "検証失敗", "結果失効",
            "2回連続成功を無効", "30分計測再開",
            "監視レベル自動解除を禁止", "時計API",
            "例外処理", "第126問", "第133問",
            "第139〜143問", "DD4%・5%",
        ):
            self.assertIn(term, excerpt)

    def test_fx_saf_006_stays_unapproved(self):
        registry = json.loads((ROOT / "specs/reconciliation_registry.json").read_text(encoding="utf-8"))
        priority = json.loads((ROOT / "specs/source_review_priority.json").read_text(encoding="utf-8"))
        a = next(x for x in registry["items"] if x["requirement_id"] == "FX-SAF-006")
        b = next(x for x in priority["items"] if x["requirement_id"] == "FX-SAF-006")
        self.assertIn("Q147", a["question_ids"])
        self.assertIn("Q147", b["question_ids"])
        self.assertFalse(a["implementation_approved"])
        self.assertIsNone(a["owner_approval"])
        self.assertFalse(b["human_safety_approval"])
        self.assertEqual(b["source_review"], "PENDING_ORIGINAL")

    def test_monotonic_elapsed_time_and_utc_verification_are_separate(self):
        doc = (ROOT / "specs/safety_foundation.md").read_text(encoding="utf-8")
        section = doc.split("## Q147：", 1)[1].split("\n## ", 1)[0]
        for term in (
            "Windowsの単調増加時計",
            "第1回の時計検証全体成功から第2回開始まで60秒以上",
            "UTCシステム時刻は別途記録",
            "UTC同期状態と時計誤差を検証",
            "システム再起動", "計測の連続性喪失",
            "時計異常", "検証失敗", "検証結果失効",
            "2回連続成功を無効",
            "30分計測の再開", "自動解除を禁止",
            "Q126", "30分計測リセット",
            "新たな有効測定", "ゼロから開始",
            "Q133", "最大5分間有効・異常時即失効",
            "Q139", "Q143", "全体45秒", "並列測定",
            "スリープ・再起動後の計時仕様",
            "具体的な時計API", "記録・異常検知",
            "例外処理", "未決", "DD4%・5%",
            "本人承認必須停止", "ほかの停止理由",
            "implementation_approved=false",
        ):
            self.assertIn(term, section)

    def test_decision_record_once(self):
        decisions = (ROOT / "DECISIONS.md").read_text(encoding="utf-8")
        self.assertEqual(sum(line.startswith("| Q147 |") for line in decisions.splitlines()), 1)
        self.assertIn("v14.7", (ROOT / "MASTER_SPEC.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
