"""Q155: per-sender HMAC-SHA256 and Windows local access control are both mandatory."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Q155DecisionTests(unittest.TestCase):
    def test_direct_answer_and_option_appear_separately(self):
        rows = json.loads((ROOT / "specs/source_evidence.json").read_text(encoding="utf-8"))["records"]
        entry = next(x for x in rows if x["question_id"] == "Q155")
        self.assertEqual(entry["source_kind"], "ORIGINAL")
        self.assertEqual(entry["verification"], "DIRECT_CHAT")
        self.assertEqual(entry["archive_locator_status"], "PENDING_LOCAL_ARCHIVE")
        self.assertFalse(entry["owner_approved_for_safety"])
        excerpt = (ROOT / entry["excerpt_path"]).read_text(encoding="utf-8")
        for token in (
            "第155問はBを採用する", "本人の直接発言ではない",
            "送信元別HMAC-SHA256認証型", "送信元に別々の秘密鍵",
            "Windows側の通信アクセス制御も併用する", "未決",
        ):
            self.assertIn(token, excerpt)

    def test_safety_scope_and_approval_gates(self):
        text = (ROOT / "specs/safety_foundation.md").read_text(encoding="utf-8")
        section = text.split("## Q155：", 1)[1].split("\n## ", 1)[0]
        for token in (
            "DD2%警告", "DD3%重点再評価", "独立ウォッチドッグ",
            "HMAC-SHA256", "送信元別", "別個の秘密鍵", "メッセージ認証コード",
            "Windowsローカル通信のアクセス制御", "送信元ID", "認証不能",
            "検証失敗", "更新しない", "Q154",
            "形式", "連番", "鮮度", "重複・再送", "すべて合格",
            "Q153", "受信した瞬間", "Windows単調増加時計",
            "Q150", "通常2秒", "Q151", "厳密に6秒超",
            "Q152", "欠落回数", "Q149", "Windows電源イベント",
            "Q148", "2回連続成功を無効", "Q126の30分計測をリセット",
            "安全検証を最初から", "30分計測再開", "自動解除を禁止",
            "Q145〜Q147", "60秒以上", "UTC",
            "Q133", "最大5分間有効・異常時即失効",
            "Q139〜Q143", "45秒", "並列測定",
            "DD4%・5%", "本人承認必須停止", "ほかの停止理由",
            "鍵", "リポジトリ", "MT4/EA", "未決",
            "implementation_approved=false",
        ):
            self.assertIn(token, section)

        registry = json.loads((ROOT / "specs/reconciliation_registry.json").read_text(encoding="utf-8"))
        priority = json.loads((ROOT / "specs/source_review_priority.json").read_text(encoding="utf-8"))
        rr = next(x for x in registry["items"] if x["requirement_id"] == "FX-SAF-006")
        pr = next(x for x in priority["items"] if x["requirement_id"] == "FX-SAF-006")
        self.assertIn("Q155", rr["question_ids"])
        self.assertIn("Q155", pr["question_ids"])
        self.assertFalse(rr["implementation_approved"])
        self.assertIsNone(rr["owner_approval"])
        self.assertFalse(pr["human_safety_approval"])
        self.assertEqual(pr["source_review"], "PENDING_ORIGINAL")
        decisions = (ROOT / "DECISIONS.md").read_text(encoding="utf-8")
        self.assertEqual(sum(x.startswith("| Q155 |") for x in decisions.splitlines()), 1)
        self.assertIn("v15.5", (ROOT / "MASTER_SPEC.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
