"""Q149: scope of Windows power-event plus independent watchdog safety design."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Q149DecisionTests(unittest.TestCase):
    def test_verbatim_answer_separated_from_assistant_option(self):
        data = json.loads((ROOT / "specs/source_evidence.json").read_text(encoding="utf-8"))
        rec = next(x for x in data["records"] if x["question_id"] == "Q149")
        self.assertEqual(rec["source_kind"], "ORIGINAL")
        self.assertEqual(rec["verification"], "DIRECT_CHAT")
        self.assertEqual(rec["archive_locator_status"], "PENDING_LOCAL_ARCHIVE")
        self.assertFalse(rec["owner_approved_for_safety"])
        excerpt = (ROOT / rec["excerpt_path"]).read_text(encoding="utf-8")
        for term in (
            "第149問はAを採用する", "本人の直接発言ではない",
            "Windows電源イベント＋独立監視の複合検知型",
            "Windowsの電源状態変更通知", "独立ウォッチドッグ",
            "どちらか一方で異常を検知すれば安全リセット",
            "判定不能時も安全側に倒す",
        ):
            self.assertIn(term, excerpt)

    def test_fail_closed_combined_detection_and_existing_invariants(self):
        doc = (ROOT / "specs/safety_foundation.md").read_text(encoding="utf-8")
        section = doc.split("## Q149：", 1)[1].split("\n## ", 1)[0]
        for term in (
            "DD2%警告", "DD3%重点再評価",
            "Windows電源状態変更通知", "独立ウォッチドッグ",
            "監視間隔", "計測連続性", "どちらか一方",
            "判定不能", "安全側",
            "2回連続成功を無効", "Q126の30分計測をリセット",
            "復帰後", "安全検証を最初から",
            "30分計測再開", "監視レベル自動解除を禁止",
            "Q145〜Q147", "60秒以上", "Windows単調増加時計",
            "Q133", "最大5分間有効・異常時即失効",
            "Q139〜Q143", "45秒", "並列測定",
            "DD4%・5%", "本人承認必須停止",
            "具体的", "閾値", "例外", "未決",
            "implementation_approved=false",
        ):
            self.assertIn(term, section)

    def test_registry_and_approval_gates(self):
        reg = json.loads((ROOT / "specs/reconciliation_registry.json").read_text(encoding="utf-8"))
        pri = json.loads((ROOT / "specs/source_review_priority.json").read_text(encoding="utf-8"))
        a = next(x for x in reg["items"] if x["requirement_id"] == "FX-SAF-006")
        b = next(x for x in pri["items"] if x["requirement_id"] == "FX-SAF-006")
        self.assertIn("Q149", a["question_ids"])
        self.assertIn("Q149", b["question_ids"])
        self.assertFalse(a["implementation_approved"])
        self.assertIsNone(a["owner_approval"])
        self.assertFalse(b["human_safety_approval"])
        self.assertEqual(b["source_review"], "PENDING_ORIGINAL")
        decisions = (ROOT / "DECISIONS.md").read_text(encoding="utf-8")
        self.assertEqual(sum(line.startswith("| Q149 |") for line in decisions.splitlines()), 1)
        self.assertIn("## Q149：", (ROOT / "MASTER_SPEC.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
