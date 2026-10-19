"""Q160 staged prefix checks before payload reads/allocations; all safety decisions retained."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Q160DecisionTests(unittest.TestCase):
    def test_direct_answer_and_option_distinguished(self):
        records = json.loads((ROOT / "specs/source_evidence.json").read_text(encoding="utf-8"))["records"]
        row = next(r for r in records if r["question_id"] == "Q160")
        self.assertEqual(row["source_kind"], "ORIGINAL")
        self.assertEqual(row["verification"], "DIRECT_CHAT")
        self.assertEqual(row["archive_locator_status"], "PENDING_LOCAL_ARCHIVE")
        self.assertFalse(row["owner_approved_for_safety"])
        excerpt = (ROOT / row["excerpt_path"]).read_text(encoding="utf-8")
        for term in (
            "第160問はBを採用する", "本人の直接発言ではない",
            "段階的・事前長さ検証型", "合格した場合だけ対応するデータを読み込み",
            "4 KiB", "16 KiB", "即座に拒否する", "未決"
        ):
            self.assertIn(term, excerpt)

    def test_early_rejection_and_all_previous_safety_conditions(self):
        safety = (ROOT / "specs/safety_foundation.md").read_text(encoding="utf-8")
        section = safety.split("## Q160：", 1)[1].split("\n## ", 1)[0]
        for term in (
            "DD2%警告", "DD3%重点再評価", "独立ウォッチドッグ",
            "段階的・事前長さ検証", "UINT32BE", "固定4バイト",
            "4 KiB", "4,096バイト", "16 KiB", "16,384バイト",
            "24バイト", "個別上限", "累積上限",
            "読み込み前", "バッファ確保前", "即座に拒否",
            "オーバーフロー", "境界", "更新しない",
            "認証済みを意味しない", "Q159", "Q158", "Q157", "固定順序",
            "Q156", "プロトコル版", "送信元ID", "セッション識別子",
            "連番", "鮮度検証用時刻", "ハートビート本文",
            "Q155", "HMAC-SHA256", "Windowsローカル通信のアクセス制御",
            "Q154", "形式", "鮮度", "重複・再送", "全検証合格",
            "Q153", "受信した瞬間", "Windows単調増加時計",
            "Q150", "通常2秒", "Q151", "厳密に6秒超",
            "Q152", "欠落回数", "Q149", "Windows電源イベント",
            "Q148", "2回連続成功を無効", "Q126の30分計測をリセット",
            "安全検証を最初から", "30分計測再開", "自動解除を禁止",
            "Q145〜Q147", "60秒以上", "UTC", "Q133",
            "最大5分間有効・異常時即失効", "Q139〜Q143", "45秒",
            "並列測定", "DD4%・5%", "本人承認必須停止",
            "ほかの停止理由", "未決", "implementation_approved=false",
        ):
            self.assertIn(term, section)

    def test_registry_approval_hold_and_decision_uniqueness(self):
        reg = json.loads((ROOT / "specs/reconciliation_registry.json").read_text(encoding="utf-8"))
        pri = json.loads((ROOT / "specs/source_review_priority.json").read_text(encoding="utf-8"))
        a = next(x for x in reg["items"] if x["requirement_id"] == "FX-SAF-006")
        b = next(x for x in pri["items"] if x["requirement_id"] == "FX-SAF-006")
        self.assertIn("Q160", a["question_ids"])
        self.assertIn("Q160", b["question_ids"])
        self.assertFalse(a["implementation_approved"])
        self.assertIsNone(a["owner_approval"])
        self.assertFalse(b["human_safety_approval"])
        self.assertEqual(b["source_review"], "PENDING_ORIGINAL")
        decisions = (ROOT / "DECISIONS.md").read_text(encoding="utf-8")
        self.assertEqual(sum(l.startswith("| Q160 |") for l in decisions.splitlines()), 1)
        self.assertIn("## Q160：", (ROOT / "MASTER_SPEC.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
