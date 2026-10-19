"""Q152: heartbeat elapsed time is decisive; missing-count is for diagnostics only."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Q152DecisionTests(unittest.TestCase):
    def test_source_keeps_user_verbatim_and_option_separate(self):
        rows = json.loads((ROOT / "specs/source_evidence.json").read_text(encoding="utf-8"))["records"]
        row = next(x for x in rows if x["question_id"] == "Q152")
        self.assertEqual(row["source_kind"], "ORIGINAL")
        self.assertEqual(row["verification"], "DIRECT_CHAT")
        self.assertEqual(row["archive_locator_status"], "PENDING_LOCAL_ARCHIVE")
        self.assertFalse(row["owner_approved_for_safety"])
        content = (ROOT / row["excerpt_path"]).read_text(encoding="utf-8")
        for term in ("第152問はAを採用する", "本人の直接発言ではない",
                     "経過時間優先型", "6秒超なら欠落回数に関係なく異常判定",
                     "未取得回数は記録・原因分析", "遅らせる条件にはしない"):
            self.assertIn(term, content)

    def test_safety_rules_retained(self):
        content = (ROOT / "specs/safety_foundation.md").read_text(encoding="utf-8")
        section = content.split("## Q152：", 1)[1].split("\n## ", 1)[0]
        for term in ("DD2%警告", "DD3%重点再評価", "独立ウォッチドッグ",
                     "厳密に6秒超", "欠落回数に関係なく異常判定",
                     "6秒ちょうど", "未取得回数は記録・原因分析",
                     "追加の必須条件にしない", "Q150", "通常2秒間隔",
                     "Q149", "Windows電源状態変更通知", "待たない",
                     "Q148", "2回連続成功を無効", "Q126の30分計測をリセット",
                     "安全検証を最初から", "30分計測再開", "自動解除を禁止",
                     "Q145〜Q147", "60秒以上", "Windows単調増加時計",
                     "Q133", "最大5分間有効・異常時即失効",
                     "Q139〜Q143", "45秒", "並列測定",
                     "DD4%・5%", "本人承認必須停止", "ほかの停止理由",
                     "未決", "implementation_approved=false"):
            self.assertIn(term, section)

    def test_safety_approvals_not_inferred(self):
        a = next(x for x in json.loads((ROOT / "specs/reconciliation_registry.json").read_text(
            encoding="utf-8"))["items"] if x["requirement_id"] == "FX-SAF-006")
        b = next(x for x in json.loads((ROOT / "specs/source_review_priority.json").read_text(
            encoding="utf-8"))["items"] if x["requirement_id"] == "FX-SAF-006")
        self.assertIn("Q152", a["question_ids"])
        self.assertIn("Q152", b["question_ids"])
        self.assertFalse(a["implementation_approved"])
        self.assertIsNone(a["owner_approval"])
        self.assertFalse(b["human_safety_approval"])
        self.assertEqual(b["source_review"], "PENDING_ORIGINAL")
        decisions = (ROOT / "DECISIONS.md").read_text(encoding="utf-8")
        self.assertEqual(sum(l.startswith("| Q152 |") for l in decisions.splitlines()), 1)
        self.assertIn("## Q152：", (ROOT / "MASTER_SPEC.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
