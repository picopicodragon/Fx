"""Q162 incremental real-byte frame accounting before storing and valid-heartbeat update."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Q162DecisionTests(unittest.TestCase):
    def test_answer_and_presented_option_distinguished(self):
        evidence = json.loads((ROOT / "specs/source_evidence.json").read_text(encoding="utf-8"))
        r = next(x for x in evidence["records"] if x["question_id"] == "Q162")
        self.assertEqual(r["source_kind"], "ORIGINAL")
        self.assertEqual(r["verification"], "DIRECT_CHAT")
        self.assertEqual(r["archive_locator_status"], "PENDING_LOCAL_ARCHIVE")
        self.assertFalse(r["owner_approved_for_safety"])
        quote = (ROOT / r["excerpt_path"]).read_text(encoding="utf-8")
        for term in (
            "第162問はBを採用する", "本人の直接発言ではない",
            "段階的受信＋累積サイズ監視型", "実際に受信したバイト数",
            "申告長も検証", "受信を打ち切り", "未決",
        ):
            self.assertIn(term, quote)

    def test_recv_staging_and_all_prior_constraints(self):
        safety = (ROOT / "specs/safety_foundation.md").read_text(encoding="utf-8")
        section = safety.split("## Q162：", 1)[1].split("\n## ", 1)[0]
        for term in (
            "DD2%警告", "DD3%重点再評価", "独立ウォッチドッグ",
            "段階的受信＋累積サイズ監視", "小さな単位", "実受信バイト数",
            "申告長", "事前検証", "20 KiB", "20,480バイト",
            "20,481バイト", "超過", "打ち切り", "拒否",
            "整数オーバーフロー", "格納前", "チャンクサイズ", "未決",
            "Q161", "通信フレーム全体", "HMACタグ", "通信管理情報",
            "Q160", "段階的・事前長さ検証", "UINT32BE",
            "Q159", "16 KiB", "16,384バイト", "24バイト",
            "4 KiB", "4,096バイト", "Q158", "Q157", "固定順序",
            "Q156", "プロトコル版", "送信元ID", "セッション識別子",
            "連番", "鮮度検証用時刻", "ハートビート本文",
            "Q155", "HMAC-SHA256", "Windowsローカル通信のアクセス制御",
            "Q154", "形式", "鮮度", "重複・再送", "全検証合格",
            "Q153", "受信した瞬間", "Windows単調増加時計",
            "更新しない", "Q150", "通常2秒", "Q151", "厳密に6秒超",
            "Q152", "欠落回数", "Q149", "Windows電源イベント",
            "Q148", "2回連続成功を無効", "Q126の30分計測をリセット",
            "安全検証を最初から", "30分計測再開", "自動解除を禁止",
            "Q145〜Q147", "60秒以上", "UTC", "Q133",
            "最大5分間有効・異常時即失効", "Q139〜Q143", "45秒",
            "並列測定", "DD4%・5%", "本人承認必須停止",
            "ほかの停止理由", "implementation_approved=false",
        ):
            self.assertIn(term, section)

    def test_review_flags_remain_unapproved(self):
        reg = json.loads((ROOT / "specs/reconciliation_registry.json").read_text(encoding="utf-8"))
        pri = json.loads((ROOT / "specs/source_review_priority.json").read_text(encoding="utf-8"))
        a = next(x for x in reg["items"] if x["requirement_id"] == "FX-SAF-006")
        b = next(x for x in pri["items"] if x["requirement_id"] == "FX-SAF-006")
        self.assertIn("Q162", a["question_ids"])
        self.assertIn("Q162", b["question_ids"])
        self.assertFalse(a["implementation_approved"])
        self.assertIsNone(a["owner_approval"])
        self.assertFalse(b["human_safety_approval"])
        self.assertEqual(b["source_review"], "PENDING_ORIGINAL")
        decisions = (ROOT / "DECISIONS.md").read_text(encoding="utf-8")
        self.assertEqual(sum(line.startswith("| Q162 |") for line in decisions.splitlines()), 1)
        self.assertIn("## Q162：", (ROOT / "MASTER_SPEC.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
