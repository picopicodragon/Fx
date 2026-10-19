"""Q165: four bounded reconnect attempts and a 25s total deadline without safety bypass."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Q165DecisionTests(unittest.TestCase):
    def test_direct_answer_and_option_are_separate(self):
        records = json.loads((ROOT / "specs/source_evidence.json").read_text(encoding="utf-8"))["records"]
        item = next(x for x in records if x["question_id"] == "Q165")
        self.assertEqual(item["source_kind"], "ORIGINAL")
        self.assertEqual(item["verification"], "DIRECT_CHAT")
        self.assertEqual(item["archive_locator_status"], "PENDING_LOCAL_ARCHIVE")
        self.assertFalse(item["owner_approved_for_safety"])
        excerpt = (ROOT / item["excerpt_path"]).read_text(encoding="utf-8")
        for token in (
            "第165問はBを採用する", "本人の直接発言ではない",
            "標準バックオフ型", "最大4回試行", "1秒 → 2秒 → 4秒 → 8秒",
            "最大25秒", "試行の処理時間も含む", "自動再起動最大3回",
        ):
            self.assertIn(token, excerpt)

    def test_scope_preserves_watchdog_and_security(self):
        doc = (ROOT / "specs/safety_foundation.md").read_text(encoding="utf-8")
        section = doc.split("## Q165：", 1)[1].split("\n## ", 1)[0]
        self.assertIn("1秒、2秒、4秒、8秒", section)
        self.assertIn("総復旧25秒はハートビート異常の6秒判定猶予時間ではない", section)
        for token in (
            "DD2%警告", "DD3%重点再評価", "独立ウォッチドッグ",
            "最大4回", "1秒", "2秒", "4秒", "8秒", "最大25秒",
            "試行処理時間", "待機時間", "いずれか", "上限到達",
            "障害停止", "通知", "無制限再試行", "未決",
            "連続60秒", "連続10分", "自動再起動最大3回",
            "Q164", "段階的バックオフ", "Q163", "通信接続",
            "断片", "安全停止理由", "リプレイ防止",
            "Q162", "段階的受信", "Q161", "20 KiB",
            "Q160", "UINT32BE", "事前長さ検証",
            "Q159", "16 KiB", "4 KiB", "Q158", "Q157", "固定順序",
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
            "最大5分間有効・異常時即失効", "Q139〜Q143", "45秒",
            "並列測定", "DD4%・5%", "本人承認必須停止",
            "ほかの停止理由", "implementation_approved=false",
        ):
            self.assertIn(token, section)

    def test_approval_remains_pending(self):
        r = json.loads((ROOT / "specs/reconciliation_registry.json").read_text(encoding="utf-8"))
        p = json.loads((ROOT / "specs/source_review_priority.json").read_text(encoding="utf-8"))
        a = next(x for x in r["items"] if x["requirement_id"] == "FX-SAF-006")
        b = next(x for x in p["items"] if x["requirement_id"] == "FX-SAF-006")
        self.assertIn("Q165", a["question_ids"])
        self.assertIn("Q165", b["question_ids"])
        self.assertFalse(a["implementation_approved"])
        self.assertIsNone(a["owner_approval"])
        self.assertFalse(b["human_safety_approval"])
        self.assertEqual(b["source_review"], "PENDING_ORIGINAL")
        decisions = (ROOT / "DECISIONS.md").read_text(encoding="utf-8")
        self.assertEqual(sum(line.startswith("| Q165 |") for line in decisions.splitlines()), 1)
        self.assertIn("v16.5", (ROOT / "MASTER_SPEC.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
