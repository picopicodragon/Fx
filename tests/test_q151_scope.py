"""Q151: watchdog heartbeat stale strictly >6s, without delaying other fault channels."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Q151DecisionTests(unittest.TestCase):
    def test_provenance_and_choice(self):
        records = json.loads((ROOT / "specs/source_evidence.json").read_text(encoding="utf-8"))["records"]
        rec = next(row for row in records if row["question_id"] == "Q151")
        self.assertEqual(rec["source_kind"], "ORIGINAL")
        self.assertEqual(rec["verification"], "DIRECT_CHAT")
        self.assertEqual(rec["archive_locator_status"], "PENDING_LOCAL_ARCHIVE")
        self.assertFalse(rec["owner_approved_for_safety"])
        excerpt = (ROOT / rec["excerpt_path"]).read_text(encoding="utf-8")
        for word in (
            "第151問はBを採用する", "本人の直接発言ではない",
            "B：6秒超", "最後に正常なハートビートを確認した時点",
            "6秒ちょうどでは", "Windows電源イベント",
            "連続欠落回数", "未決",
        ):
            self.assertIn(word, excerpt)

    def test_threshold_scope_and_fail_closed(self):
        doc = (ROOT / "specs/safety_foundation.md").read_text(encoding="utf-8")
        q151 = doc.split("## Q151：", 1)[1].split("\n## ", 1)[0]
        for word in (
            "DD2%警告", "DD3%重点再評価", "独立ウォッチドッグ",
            "最後に正常なハートビート", "6秒超", "厳密に超えた",
            "6秒ちょうど", "Windows単調増加時計", "UTC",
            "通常2秒間隔", "異常判定", "連続欠落回数",
            "電源イベント", "6秒の経過を待たない", "Q149", "Q148",
            "2回連続成功を無効", "Q126の30分計測をリセット",
            "安全検証を最初から", "30分計測再開", "自動解除を禁止",
            "Q145〜Q147", "60秒以上",
            "Q133", "最大5分間有効・異常時即失効",
            "Q139〜Q143", "全体", "45秒", "並列測定",
            "DD4%・5%", "本人承認必須停止", "ほかの停止理由",
            "誤検知", "未決", "implementation_approved=false",
        ):
            self.assertIn(word, q151)

    def test_approval_flags_and_decision_uniqueness(self):
        reg = json.loads((ROOT / "specs/reconciliation_registry.json").read_text(encoding="utf-8"))
        pri = json.loads((ROOT / "specs/source_review_priority.json").read_text(encoding="utf-8"))
        a = next(x for x in reg["items"] if x["requirement_id"] == "FX-SAF-006")
        b = next(x for x in pri["items"] if x["requirement_id"] == "FX-SAF-006")
        self.assertIn("Q151", a["question_ids"])
        self.assertIn("Q151", b["question_ids"])
        self.assertFalse(a["implementation_approved"])
        self.assertIsNone(a["owner_approval"])
        self.assertFalse(b["human_safety_approval"])
        self.assertEqual(b["source_review"], "PENDING_ORIGINAL")
        decisions = (ROOT / "DECISIONS.md").read_text(encoding="utf-8")
        self.assertEqual(sum(line.startswith("| Q151 |") for line in decisions.splitlines()), 1)
        self.assertIn("v15.1", (ROOT / "MASTER_SPEC.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
