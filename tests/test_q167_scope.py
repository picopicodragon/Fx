"""Q167: async reconnect, independent deadlines, explicit cancellation and safe verification."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Q167DecisionTests(unittest.TestCase):
    def test_source_is_verbatim_and_option_is_distinguished(self):
        evidence = json.loads((ROOT / "specs/source_evidence.json").read_text(encoding="utf-8"))
        row = next(x for x in evidence["records"] if x["question_id"] == "Q167")
        self.assertEqual(row["source_kind"], "ORIGINAL")
        self.assertEqual(row["verification"], "DIRECT_CHAT")
        self.assertEqual(row["archive_locator_status"], "PENDING_LOCAL_ARCHIVE")
        self.assertFalse(row["owner_approved_for_safety"])
        excerpt = (ROOT / row["excerpt_path"]).read_text(encoding="utf-8")
        for token in (
            "第167問はBを採用する", "本人の直接発言ではない",
            "非同期通信＋明示的キャンセル型", "独立した期限監視",
            "完了確認まで新しい試行や正常認定を行わない", "未決",
        ):
            self.assertIn(token, excerpt)

    def test_scope_preserves_timeouts_and_all_prior_safety(self):
        doc = (ROOT / "specs/safety_foundation.md").read_text(encoding="utf-8")
        sec = doc.split("## Q167：", 1)[1].split("\n## ", 1)[0]
        for token in (
            "DD2%警告", "DD3%重点再評価", "独立ウォッチドッグ",
            "非同期通信＋明示的キャンセル", "独立した期限監視",
            "キャンセル要求", "キャンセル完了", "完了確認不能",
            "旧試行", "遅延", "新しい試行", "正常認定", "安全側",
            "Q166", "最大2秒", "Q165", "最大4回",
            "1秒", "2秒", "4秒", "8秒", "25秒",
            "連続60秒", "連続10分", "自動再起動最大3回",
            "Q164", "段階的バックオフ", "Q163", "通信接続",
            "断片", "安全停止理由", "リプレイ防止", "Q162", "段階的受信",
            "Q161", "20 KiB", "Q160", "UINT32BE", "事前長さ検証",
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
            "最大5分間有効・異常時即失効", "Q139〜Q143",
            "45秒", "並列測定", "DD4%・5%", "本人承認必須停止",
            "ほかの停止理由", "未決", "implementation_approved=false",
        ):
            self.assertIn(token, sec)

    def test_registry_and_approval_hold(self):
        r = json.loads((ROOT / "specs/reconciliation_registry.json").read_text(encoding="utf-8"))
        p = json.loads((ROOT / "specs/source_review_priority.json").read_text(encoding="utf-8"))
        a = next(x for x in r["items"] if x["requirement_id"] == "FX-SAF-006")
        b = next(x for x in p["items"] if x["requirement_id"] == "FX-SAF-006")
        self.assertIn("Q167", a["question_ids"])
        self.assertIn("Q167", b["question_ids"])
        self.assertFalse(a["implementation_approved"])
        self.assertIsNone(a["owner_approval"])
        self.assertFalse(b["human_safety_approval"])
        self.assertEqual(b["source_review"], "PENDING_ORIGINAL")
        dec = (ROOT / "DECISIONS.md").read_text(encoding="utf-8")
        self.assertEqual(sum(row.startswith("| Q167 |") for row in dec.splitlines()), 1)
        self.assertIn("v16.7", (ROOT / "MASTER_SPEC.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
