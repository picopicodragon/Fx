"""Q161: 20 KiB complete frame, 16 KiB authenticated input, 4 KiB fields retained."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Q161DecisionTests(unittest.TestCase):
    def test_user_verbatim_and_presented_option_separated(self):
        records = json.loads((ROOT / "specs/source_evidence.json").read_text(encoding="utf-8"))["records"]
        rec = next(x for x in records if x["question_id"] == "Q161")
        self.assertEqual(rec["source_kind"], "ORIGINAL")
        self.assertEqual(rec["verification"], "DIRECT_CHAT")
        self.assertEqual(rec["archive_locator_status"], "PENDING_LOCAL_ARCHIVE")
        self.assertFalse(rec["owner_approved_for_safety"])
        text = (ROOT / rec["excerpt_path"]).read_text(encoding="utf-8")
        for term in ("第161問はBを採用する", "本人の直接発言ではない",
                     "20 KiB・標準制限型", "最大4 KiBの余地",
                     "無条件に20 KiBのデータを受け入れる意味ではありません"):
            self.assertIn(term, text)

    def test_full_frame_limit_and_all_prior_safety_controls(self):
        doc = (ROOT / "specs/safety_foundation.md").read_text(encoding="utf-8")
        sec = doc.split("## Q161：", 1)[1].split("\n## ", 1)[0]
        for term in (
            "DD2%警告", "DD3%重点再評価", "独立ウォッチドッグ",
            "20 KiB", "20,480バイト", "20,481バイト",
            "16 KiB", "16,384バイト", "4 KiB", "4,096バイト",
            "HMACタグ", "通信管理情報", "残余枠", "上限超過", "拒否",
            "Q160", "段階的・事前長さ検証", "整数オーバーフロー",
            "Q159", "24バイト", "Q158", "UINT32BE", "Q157", "固定順序",
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
            "最大5分間有効・異常時即失効", "Q139〜Q143",
            "45秒", "並列測定", "DD4%・5%", "本人承認必須停止",
            "ほかの停止理由", "未決", "implementation_approved=false",
        ):
            self.assertIn(term, sec)

    def test_unapproved_source_and_registry_state(self):
        r = json.loads((ROOT / "specs/reconciliation_registry.json").read_text(encoding="utf-8"))
        p = json.loads((ROOT / "specs/source_review_priority.json").read_text(encoding="utf-8"))
        reg = next(x for x in r["items"] if x["requirement_id"] == "FX-SAF-006")
        pri = next(x for x in p["items"] if x["requirement_id"] == "FX-SAF-006")
        self.assertIn("Q161", reg["question_ids"])
        self.assertIn("Q161", pri["question_ids"])
        self.assertFalse(reg["implementation_approved"])
        self.assertIsNone(reg["owner_approval"])
        self.assertFalse(pri["human_safety_approval"])
        self.assertEqual(pri["source_review"], "PENDING_ORIGINAL")
        decisions = (ROOT / "DECISIONS.md").read_text(encoding="utf-8")
        self.assertEqual(sum(line.startswith("| Q161 |") for line in decisions.splitlines()), 1)
        self.assertIn("v16.1", (ROOT / "MASTER_SPEC.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
