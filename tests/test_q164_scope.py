"""Q164 staged bounded reconnect backoff, without weakening watchdog or safety stops."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Q164DecisionTests(unittest.TestCase):
    def test_verbatim_answer_and_option_separated(self):
        rows = json.loads((ROOT / "specs/source_evidence.json").read_text(encoding="utf-8"))["records"]
        r = next(x for x in rows if x["question_id"] == "Q164")
        self.assertEqual(r["source_kind"], "ORIGINAL")
        self.assertEqual(r["verification"], "DIRECT_CHAT")
        self.assertEqual(r["archive_locator_status"], "PENDING_LOCAL_ARCHIVE")
        self.assertFalse(r["owner_approved_for_safety"])
        source = (ROOT / r["excerpt_path"]).read_text(encoding="utf-8")
        for token in (
            "第164問はBを採用する", "本人の直接発言ではない",
            "段階的バックオフ＋上限管理型", "初回は短い間隔",
            "最大試行回数と待機時間の上限", "後続の設問で決定",
        ):
            self.assertIn(token, source)

    def test_scope_preserves_all_critical_constraints(self):
        safety = (ROOT / "specs/safety_foundation.md").read_text(encoding="utf-8")
        section = safety.split("## Q164：", 1)[1].split("\n## ", 1)[0]
        for token in (
            "DD2%警告", "DD3%重点再評価", "独立ウォッチドッグ",
            "段階的バックオフ＋上限管理", "初回", "試行間隔",
            "最大再試行回数", "待機時間", "上限到達", "既存の障害停止",
            "通知", "無制限再試行", "未決", "60秒", "10分",
            "自動再起動最大3回", "Q163", "破棄", "通信接続",
            "断片", "安全停止理由", "リプレイ防止",
            "Q162", "段階的受信", "Q161", "20 KiB",
            "Q160", "UINT32BE", "事前長さ検証",
            "Q159", "16 KiB", "4 KiB", "Q158", "Q157", "固定順序",
            "Q156", "プロトコル版", "送信元ID", "セッション識別子",
            "連番", "鮮度検証用時刻", "ハートビート本文",
            "Q155", "HMAC-SHA256", "Windowsローカル通信のアクセス制御",
            "Q154", "形式", "鮮度", "重複・再送", "全検証合格",
            "Q153", "受信した瞬間", "Windows単調増加時計",
            "更新しない", "Q150", "通常2秒", "Q151", "厳密に6秒超",
            "Q152", "欠落回数", "Q149", "Windows電源イベント",
            "Q148", "2回連続成功を無効", "Q126の30分計測をリセット",
            "安全検証を最初から", "30分計測再開", "自動解除を禁止",
            "Q145〜Q147", "60秒以上", "UTC",
            "Q133", "最大5分間有効・異常時即失効", "Q139〜Q143",
            "45秒", "並列測定", "DD4%・5%", "本人承認必須停止",
            "ほかの停止理由", "implementation_approved=false",
        ):
            self.assertIn(token, section)

    def test_registry_approvals_and_uniqueness(self):
        registry = json.loads((ROOT / "specs/reconciliation_registry.json").read_text(encoding="utf-8"))
        priority = json.loads((ROOT / "specs/source_review_priority.json").read_text(encoding="utf-8"))
        a = next(x for x in registry["items"] if x["requirement_id"] == "FX-SAF-006")
        b = next(x for x in priority["items"] if x["requirement_id"] == "FX-SAF-006")
        self.assertIn("Q164", a["question_ids"])
        self.assertIn("Q164", b["question_ids"])
        self.assertFalse(a["implementation_approved"])
        self.assertIsNone(a["owner_approval"])
        self.assertFalse(b["human_safety_approval"])
        self.assertEqual(b["source_review"], "PENDING_ORIGINAL")
        decisions = (ROOT / "DECISIONS.md").read_text(encoding="utf-8")
        self.assertEqual(sum(x.startswith("| Q164 |") for x in decisions.splitlines()), 1)
        self.assertIn("v16.4", (ROOT / "MASTER_SPEC.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
