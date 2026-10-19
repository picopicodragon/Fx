"""Q168: cancel-completion requires matching notification, quiescence, no pending I/O and resource isolation."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Q168DecisionTests(unittest.TestCase):
    def test_source_original_answer_separate_from_presented_choice(self):
        records = json.loads((ROOT / "specs/source_evidence.json").read_text(encoding="utf-8"))["records"]
        record = next(x for x in records if x["question_id"] == "Q168")
        self.assertEqual(record["source_kind"], "ORIGINAL")
        self.assertEqual(record["verification"], "DIRECT_CHAT")
        self.assertEqual(record["archive_locator_status"], "PENDING_LOCAL_ARCHIVE")
        self.assertFalse(record["owner_approved_for_safety"])
        source = (ROOT / record["excerpt_path"]).read_text(encoding="utf-8")
        for token in (
            "第168問はBを採用する", "本人の直接発言ではない",
            "完了通知＋旧処理・資源状態検証型", "試行ID", "未完了の通信処理",
            "無効化・隔離", "未決",
        ):
            self.assertIn(token, source)

    def test_cancellation_confirmation_and_all_previous_safety(self):
        doc = (ROOT / "specs/safety_foundation.md").read_text(encoding="utf-8")
        sec = doc.split("## Q168：", 1)[1].split("\n## ", 1)[0]
        for token in (
            "DD2%警告", "DD3%重点再評価", "独立ウォッチドッグ",
            "完了通知＋旧処理・資源状態検証", "キャンセル完了通知",
            "試行ID", "旧試行", "非稼働", "未完了の通信処理",
            "無効化", "隔離", "遅延通知", "全条件", "確認不能",
            "次の再接続試行", "安全側", "既存の障害停止", "通知", "未決",
            "Q167", "非同期通信", "明示的キャンセル",
            "Q166", "最大2秒", "Q165", "最大4回",
            "1秒", "2秒", "4秒", "8秒", "25秒", "Q164", "段階的バックオフ",
            "連続60秒", "連続10分", "自動再起動最大3回",
            "Q163", "通信接続", "断片", "安全停止理由", "リプレイ防止",
            "Q162", "段階的受信", "Q161", "20 KiB", "Q160",
            "UINT32BE", "事前長さ検証", "Q159", "16 KiB",
            "4 KiB", "Q158", "Q157", "固定順序",
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
            "ほかの停止理由", "implementation_approved=false",
        ):
            self.assertIn(token, sec)

    def test_registry_remains_unapproved_and_decision_unique(self):
        register = json.loads((ROOT / "specs/reconciliation_registry.json").read_text(encoding="utf-8"))
        priority = json.loads((ROOT / "specs/source_review_priority.json").read_text(encoding="utf-8"))
        a = next(x for x in register["items"] if x["requirement_id"] == "FX-SAF-006")
        b = next(x for x in priority["items"] if x["requirement_id"] == "FX-SAF-006")
        self.assertIn("Q168", a["question_ids"])
        self.assertIn("Q168", b["question_ids"])
        self.assertFalse(a["implementation_approved"])
        self.assertIsNone(a["owner_approval"])
        self.assertFalse(b["human_safety_approval"])
        self.assertEqual(b["source_review"], "PENDING_ORIGINAL")
        decisions = (ROOT / "DECISIONS.md").read_text(encoding="utf-8")
        self.assertEqual(sum(x.startswith("| Q168 |") for x in decisions.splitlines()), 1)
        self.assertIn("## Q168：", (ROOT / "MASTER_SPEC.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
