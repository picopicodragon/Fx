"""Q157: fixed order and length-prefixed HMAC input, other byte details TBD."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Q157DecisionTests(unittest.TestCase):
    def test_answer_vs_presented_option_and_pending_original_archive(self):
        records = json.loads((ROOT / "specs/source_evidence.json").read_text(encoding="utf-8"))["records"]
        rec = next(x for x in records if x["question_id"] == "Q157")
        self.assertEqual(rec["source_kind"], "ORIGINAL")
        self.assertEqual(rec["verification"], "DIRECT_CHAT")
        self.assertEqual(rec["archive_locator_status"], "PENDING_LOCAL_ARCHIVE")
        self.assertFalse(rec["owner_approved_for_safety"])
        excerpt = (ROOT / rec["excerpt_path"]).read_text(encoding="utf-8")
        for term in (
            "第157問はBを採用する", "本人の直接発言ではない",
            "固定順序＋長さプレフィックス型", "各項目の長さと内容",
            "数値のバイト順", "文字コード", "未決",
        ):
            self.assertIn(term, excerpt)

    def test_fixed_order_length_prefix_and_no_implicit_byte_encoding(self):
        doc = (ROOT / "specs/safety_foundation.md").read_text(encoding="utf-8")
        sec = doc.split("## Q157：", 1)[1].split("\n## ", 1)[0]
        for term in (
            "DD2%警告", "DD3%重点再評価", "独立ウォッチドッグ",
            "固定順序＋長さプレフィックス", "HMAC-SHA256",
            "プロトコル版", "送信元ID", "セッション識別子",
            "連番", "鮮度検証用時刻", "ハートビート本文",
            "全6項目", "各項目の長さ", "内容バイト列",
            "同じバイト列", "エンディアン", "文字コード", "未決",
            "HMACタグ", "区切り文字",
            "Q156", "Q155", "送信元別秘密鍵", "Windowsローカル通信のアクセス制御",
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
            self.assertIn(term, sec)

    def test_reconciliation_and_human_approval_still_pending(self):
        registry = json.loads((ROOT / "specs/reconciliation_registry.json").read_text(encoding="utf-8"))
        review = json.loads((ROOT / "specs/source_review_priority.json").read_text(encoding="utf-8"))
        rr = next(x for x in registry["items"] if x["requirement_id"] == "FX-SAF-006")
        pri = next(x for x in review["items"] if x["requirement_id"] == "FX-SAF-006")
        self.assertIn("Q157", rr["question_ids"])
        self.assertIn("Q157", pri["question_ids"])
        self.assertFalse(rr["implementation_approved"])
        self.assertIsNone(rr["owner_approval"])
        self.assertFalse(pri["human_safety_approval"])
        self.assertEqual(pri["source_review"], "PENDING_ORIGINAL")
        decisions = (ROOT / "DECISIONS.md").read_text(encoding="utf-8")
        self.assertEqual(sum(line.startswith("| Q157 |") for line in decisions.splitlines()), 1)
        self.assertIn("v15.7", (ROOT / "MASTER_SPEC.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
