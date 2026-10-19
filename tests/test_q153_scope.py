"""Q153: last valid heartbeat timestamp must be reception-time Windows monotonic."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Q153DecisionTests(unittest.TestCase):
    def test_exact_answer_distinguished_from_option(self):
        data = json.loads((ROOT / "specs/source_evidence.json").read_text(encoding="utf-8"))
        rec = next(r for r in data["records"] if r["question_id"] == "Q153")
        self.assertEqual(rec["source_kind"], "ORIGINAL")
        self.assertEqual(rec["verification"], "DIRECT_CHAT")
        self.assertEqual(rec["archive_locator_status"], "PENDING_LOCAL_ARCHIVE")
        self.assertFalse(rec["owner_approved_for_safety"])
        quote = (ROOT / rec["excerpt_path"]).read_text(encoding="utf-8")
        for term in ("第153問はAを採用する", "本人の直接発言ではない",
                     "受信時のWindows単調増加時計型", "受信した瞬間",
                     "正常性検証に合格した場合だけ", "検証失敗時は更新しない"):
            self.assertIn(term, quote)

    def test_reception_time_accepted_only_if_valid_and_prior_safety(self):
        doc = (ROOT / "specs/safety_foundation.md").read_text(encoding="utf-8")
        section = doc.split("## Q153：", 1)[1].split("\n## ", 1)[0]
        for term in (
            "DD2%警告", "DD3%重点再評価", "独立ウォッチドッグ",
            "受信した瞬間のWindows単調増加時計", "受信時刻",
            "正常性検証に合格した場合だけ", "検証完了時刻",
            "検証失敗・検証不能", "更新しない",
            "Q150", "通常2秒間隔", "Q151", "厳密に6秒超", "6秒ちょうど",
            "Q152", "欠落回数", "ログ", "UTC",
            "Q149", "Windows電源イベント", "Q148", "2回連続成功を無効",
            "Q126の30分計測をリセット", "安全検証を最初から",
            "30分計測再開", "自動解除を禁止",
            "Q145〜Q147", "60秒以上", "Q133", "最大5分間有効・異常時即失効",
            "Q139〜Q143", "45秒", "並列測定",
            "DD4%・5%", "本人承認必須停止", "ほかの停止理由",
            "認証", "連番", "鮮度", "未決",
            "implementation_approved=false",
        ):
            self.assertIn(term, section)

    def test_reconciliation_and_approval_gates_unchanged(self):
        reg = json.loads((ROOT / "specs/reconciliation_registry.json").read_text(encoding="utf-8"))
        pri = json.loads((ROOT / "specs/source_review_priority.json").read_text(encoding="utf-8"))
        a = next(x for x in reg["items"] if x["requirement_id"] == "FX-SAF-006")
        b = next(x for x in pri["items"] if x["requirement_id"] == "FX-SAF-006")
        self.assertIn("Q153", a["question_ids"])
        self.assertIn("Q153", b["question_ids"])
        self.assertFalse(a["implementation_approved"])
        self.assertIsNone(a["owner_approval"])
        self.assertFalse(b["human_safety_approval"])
        self.assertEqual(b["source_review"], "PENDING_ORIGINAL")
        decisions = (ROOT / "DECISIONS.md").read_text(encoding="utf-8")
        self.assertEqual(sum(x.startswith("| Q153 |") for x in decisions.splitlines()), 1)
        self.assertIn("## Q153：", (ROOT / "MASTER_SPEC.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
