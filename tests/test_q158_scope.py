"""Q158: four-byte unsigned big-endian length prefixes; representation != allowed payload."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Q158DecisionTests(unittest.TestCase):
    def test_source_and_owner_approval_hold(self):
        records = json.loads((ROOT / "specs/source_evidence.json").read_text(encoding="utf-8"))["records"]
        r = next(x for x in records if x["question_id"] == "Q158")
        self.assertEqual(r["source_kind"], "ORIGINAL")
        self.assertEqual(r["verification"], "DIRECT_CHAT")
        self.assertEqual(r["archive_locator_status"], "PENDING_LOCAL_ARCHIVE")
        self.assertFalse(r["owner_approved_for_safety"])
        quote = (ROOT / r["excerpt_path"]).read_text(encoding="utf-8")
        for term in ("第158問はBを採用する", "本人の直接発言ではない",
                     "符号なし32ビット・ビッグエンディアン型",
                     "固定4バイト", "最大長まで受信を許可するという意味ではありません"):
            self.assertIn(term, quote)

    def test_length_encoding_and_prior_safety_scope(self):
        safety = (ROOT / "specs/safety_foundation.md").read_text(encoding="utf-8")
        s = safety.split("## Q158：", 1)[1].split("\n## ", 1)[0]
        for token in (
            "DD2%警告", "DD3%重点再評価", "独立ウォッチドッグ",
            "符号なし32ビット", "ビッグエンディアン", "固定4バイト",
            "UINT32BE", "バイト数", "4,294,967,295", "許容長", "未決",
            "Q157", "固定順序", "長さプレフィックス",
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
            "implementation_approved=false",
        ):
            self.assertIn(token, s)

    def test_registry_and_unapproved_status(self):
        rr = json.loads((ROOT / "specs/reconciliation_registry.json").read_text(encoding="utf-8"))
        sr = json.loads((ROOT / "specs/source_review_priority.json").read_text(encoding="utf-8"))
        a = next(x for x in rr["items"] if x["requirement_id"] == "FX-SAF-006")
        b = next(x for x in sr["items"] if x["requirement_id"] == "FX-SAF-006")
        self.assertIn("Q158", a["question_ids"])
        self.assertIn("Q158", b["question_ids"])
        self.assertFalse(a["implementation_approved"])
        self.assertIsNone(a["owner_approval"])
        self.assertFalse(b["human_safety_approval"])
        self.assertEqual(b["source_review"], "PENDING_ORIGINAL")
        doc = (ROOT / "DECISIONS.md").read_text(encoding="utf-8")
        self.assertEqual(sum(x.startswith("| Q158 |") for x in doc.splitlines()), 1)
        self.assertIn("## Q158：", (ROOT / "MASTER_SPEC.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
