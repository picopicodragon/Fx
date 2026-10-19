"""Q159: 4 KiB per field and 16 KiB total inclusive of 24 prefix bytes."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Q159DecisionTests(unittest.TestCase):
    def test_source_exact_answer_and_choice_separated(self):
        evidence = json.loads((ROOT / "specs/source_evidence.json").read_text(encoding="utf-8"))
        row = next(r for r in evidence["records"] if r["question_id"] == "Q159")
        self.assertEqual(row["source_kind"], "ORIGINAL")
        self.assertEqual(row["verification"], "DIRECT_CHAT")
        self.assertEqual(row["archive_locator_status"], "PENDING_LOCAL_ARCHIVE")
        self.assertFalse(row["owner_approved_for_safety"])
        e = (ROOT / row["excerpt_path"]).read_text(encoding="utf-8")
        for term in ("第159問はBを採用する", "本人の直接発言ではない",
                     "標準制限型", "各フィールド最大4 KiB",
                     "認証対象全体最大16 KiB", "長さプレフィックス計24バイト",
                     "4,096バイト", "16,384バイト", "未決"):
            self.assertIn(term, e)

    def test_limits_boundaries_and_all_prior_safety(self):
        doc = (ROOT / "specs/safety_foundation.md").read_text(encoding="utf-8")
        s = doc.split("## Q159：", 1)[1].split("\n## ", 1)[0]
        for term in (
            "DD2%警告", "DD3%重点再評価", "独立ウォッチドッグ",
            "4 KiB", "4,096バイト", "4,097バイト",
            "16 KiB", "16,384バイト", "16,385バイト",
            "24バイト", "両方の上限", "バイト数", "上限超過",
            "Q158", "UINT32BE", "固定4バイト", "Q157", "固定順序",
            "Q156", "プロトコル版", "送信元ID", "セッション識別子",
            "連番", "鮮度検証用時刻", "ハートビート本文",
            "Q155", "HMAC-SHA256", "Windowsローカル通信のアクセス制御",
            "Q154", "形式", "鮮度", "重複・再送", "全検証合格",
            "Q153", "受信した瞬間", "Windows単調増加時計", "更新しない",
            "Q150", "通常2秒", "Q151", "厳密に6秒超",
            "Q152", "欠落回数", "Q149", "Windows電源イベント",
            "Q148", "2回連続成功を無効", "Q126の30分計測をリセット",
            "安全検証を最初から", "30分計測再開", "自動解除を禁止",
            "Q145〜Q147", "60秒以上", "UTC", "Q133",
            "最大5分間有効・異常時即失効", "Q139〜Q143", "45秒", "並列測定",
            "DD4%・5%", "本人承認必須停止", "ほかの停止理由",
            "implementation_approved=false", "未決",
        ):
            self.assertIn(term, s)

    def test_registry_approvals_and_decision_uniqueness(self):
        registry = json.loads((ROOT / "specs/reconciliation_registry.json").read_text(encoding="utf-8"))
        priority = json.loads((ROOT / "specs/source_review_priority.json").read_text(encoding="utf-8"))
        r = next(x for x in registry["items"] if x["requirement_id"] == "FX-SAF-006")
        p = next(x for x in priority["items"] if x["requirement_id"] == "FX-SAF-006")
        self.assertIn("Q159", r["question_ids"])
        self.assertIn("Q159", p["question_ids"])
        self.assertFalse(r["implementation_approved"])
        self.assertIsNone(r["owner_approval"])
        self.assertFalse(p["human_safety_approval"])
        self.assertEqual(p["source_review"], "PENDING_ORIGINAL")
        d = (ROOT / "DECISIONS.md").read_text(encoding="utf-8")
        self.assertEqual(sum(line.startswith("| Q159 |") for line in d.splitlines()), 1)
        self.assertIn("v15.9", (ROOT / "MASTER_SPEC.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
