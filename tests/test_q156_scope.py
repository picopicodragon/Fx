"""Q156: all replay/auth security fields are HMAC authenticated as one logical message."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Q156DecisionTests(unittest.TestCase):
    def test_verbatim_choice_is_separate_from_presented_option(self):
        records = json.loads((ROOT / "specs/source_evidence.json").read_text(encoding="utf-8"))["records"]
        row = next(x for x in records if x["question_id"] == "Q156")
        self.assertEqual(row["source_kind"], "ORIGINAL")
        self.assertEqual(row["verification"], "DIRECT_CHAT")
        self.assertEqual(row["archive_locator_status"], "PENDING_LOCAL_ARCHIVE")
        self.assertFalse(row["owner_approved_for_safety"])
        e = (ROOT / row["excerpt_path"]).read_text(encoding="utf-8")
        for term in ("第156問はBを採用する", "本人の直接発言ではない",
                     "認証・再送防止に必要な全フィールド型",
                     "プロトコル版", "送信元ID", "セッション識別子",
                     "連番", "鮮度検証用時刻", "ハートビート本文",
                     "HMACだけで再送を防げるわけではありません"):
            self.assertIn(term, e)

    def test_all_six_fields_and_retained_fail_closed_constraints(self):
        doc = (ROOT / "specs/safety_foundation.md").read_text(encoding="utf-8")
        s = doc.split("## Q156：", 1)[1].split("\n## ", 1)[0]
        for term in (
            "DD2%警告", "DD3%重点再評価", "独立ウォッチドッグ",
            "プロトコル版", "送信元ID", "セッション識別子",
            "連番", "鮮度検証用時刻", "ハートビート本文",
            "全6項目", "HMAC-SHA256", "一体として認証",
            "HMACタグ", "再送防止を保証しない", "シリアライズ", "未決",
            "Q155", "送信元別秘密鍵", "Windowsローカル通信のアクセス制御",
            "Q154", "形式", "鮮度", "重複・再送", "全検証合格",
            "Q153", "受信した瞬間", "Windows単調増加時計",
            "更新しない", "Q150", "通常2秒", "Q151", "厳密に6秒超",
            "Q152", "欠落回数", "Q149", "Windows電源イベント",
            "Q148", "2回連続成功を無効", "Q126の30分計測をリセット",
            "安全検証を最初から", "30分計測再開", "自動解除を禁止",
            "Q145〜Q147", "60秒以上", "UTC", "Q133",
            "最大5分間有効・異常時即失効", "Q139〜Q143", "45秒", "並列測定",
            "DD4%・5%", "本人承認必須停止", "ほかの停止理由",
            "implementation_approved=false",
        ):
            self.assertIn(term, s)

    def test_safety_approval_and_record_uniqueness(self):
        r = json.loads((ROOT / "specs/reconciliation_registry.json").read_text(encoding="utf-8"))
        p = json.loads((ROOT / "specs/source_review_priority.json").read_text(encoding="utf-8"))
        a = next(x for x in r["items"] if x["requirement_id"] == "FX-SAF-006")
        b = next(x for x in p["items"] if x["requirement_id"] == "FX-SAF-006")
        self.assertIn("Q156", a["question_ids"])
        self.assertIn("Q156", b["question_ids"])
        self.assertFalse(a["implementation_approved"])
        self.assertIsNone(a["owner_approval"])
        self.assertFalse(b["human_safety_approval"])
        self.assertEqual(b["source_review"], "PENDING_ORIGINAL")
        decisions = (ROOT / "DECISIONS.md").read_text(encoding="utf-8")
        self.assertEqual(sum(line.startswith("| Q156 |") for line in decisions.splitlines()), 1)
        self.assertIn("## Q156：", (ROOT / "MASTER_SPEC.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
