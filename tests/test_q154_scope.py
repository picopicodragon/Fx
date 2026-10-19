"""Q154: heartbeat format, origin auth, sequence, freshness and replay all mandatory."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Q154DecisionTests(unittest.TestCase):
    def test_direct_answer_separate_from_presented_option(self):
        rows = json.loads((ROOT / "specs/source_evidence.json").read_text(encoding="utf-8"))["records"]
        rec = next(x for x in rows if x["question_id"] == "Q154")
        self.assertEqual(rec["source_kind"], "ORIGINAL")
        self.assertEqual(rec["verification"], "DIRECT_CHAT")
        self.assertEqual(rec["archive_locator_status"], "PENDING_LOCAL_ARCHIVE")
        self.assertFalse(rec["owner_approved_for_safety"])
        excerpt = (ROOT / rec["excerpt_path"]).read_text(encoding="utf-8")
        for token in (
            "第154問はBを採用する", "本人の直接発言ではない",
            "認証・連番・鮮度検証型", "送信元の認証",
            "連番の正当性", "データの鮮度", "重複・再送",
            "すべて合格した場合だけ正常",
        ):
            self.assertIn(token, excerpt)

    def test_required_checks_and_reception_time_gates(self):
        safety = (ROOT / "specs/safety_foundation.md").read_text(encoding="utf-8")
        section = safety.split("## Q154：", 1)[1].split("\n## ", 1)[0]
        for token in (
            "DD2%警告", "DD3%重点再評価", "独立ウォッチドッグ",
            "形式", "必須項目", "送信元認証", "連番の正当性",
            "鮮度", "重複・再送", "すべて合格",
            "Windows単調増加時計", "受信した瞬間", "受信時刻",
            "検証失敗・不能・タイムアウト", "更新しない", "Q153",
            "Q150", "通常2秒", "Q151", "厳密に6秒超",
            "Q152", "欠落回数", "Q149", "Windows電源イベント",
            "Q148", "2回連続成功を無効", "Q126の30分計測をリセット",
            "安全検証を最初から", "30分計測再開", "自動解除を禁止",
            "Q145〜Q147", "60秒以上", "UTC",
            "Q133", "最大5分間有効・異常時即失効",
            "Q139〜Q143", "45秒", "並列測定",
            "DD4%・5%", "本人承認必須停止", "ほかの停止理由",
            "未決", "implementation_approved=false",
        ):
            self.assertIn(token, section)

    def test_registry_flags_and_unique_decision(self):
        reg = json.loads((ROOT / "specs/reconciliation_registry.json").read_text(encoding="utf-8"))
        pri = json.loads((ROOT / "specs/source_review_priority.json").read_text(encoding="utf-8"))
        a = next(x for x in reg["items"] if x["requirement_id"] == "FX-SAF-006")
        b = next(x for x in pri["items"] if x["requirement_id"] == "FX-SAF-006")
        self.assertIn("Q154", a["question_ids"])
        self.assertIn("Q154", b["question_ids"])
        self.assertFalse(a["implementation_approved"])
        self.assertIsNone(a["owner_approval"])
        self.assertFalse(b["human_safety_approval"])
        self.assertEqual(b["source_review"], "PENDING_ORIGINAL")
        dec = (ROOT / "DECISIONS.md").read_text(encoding="utf-8")
        self.assertEqual(sum(x.startswith("| Q154 |") for x in dec.splitlines()), 1)
        self.assertIn("## Q154：", (ROOT / "MASTER_SPEC.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
