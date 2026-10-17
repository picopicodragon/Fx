"""Q142: 45-second global clock verification deadline and DD fail-closed safeguards."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Q142DecisionTests(unittest.TestCase):
    def test_user_direct_choice_and_historical_source_pending(self):
        evidence = json.loads((ROOT / "specs/source_evidence.json").read_text(encoding="utf-8"))
        rec = next(x for x in evidence["records"] if x["question_id"] == "Q142")
        self.assertEqual(rec["verification"], "DIRECT_CHAT")
        self.assertEqual(rec["source_kind"], "ORIGINAL")
        self.assertEqual(rec["archive_locator_status"], "PENDING_LOCAL_ARCHIVE")
        self.assertFalse(rec["owner_approved_for_safety"])
        excerpt = (ROOT / rec["excerpt_path"]).read_text(encoding="utf-8")
        for v in (
            "第142問はA", "DD2%警告", "DD3%重点再評価",
            "主時刻サーバーと予備時刻サーバーを含む",
            "所要時間上限を45秒", "最初の測定開始",
            "最終的な時計検証結果の確定", "45秒を超えた場合",
            "検証不能", "監視レベル自動解除を禁止",
            "第126問", "30分計測をリセット",
            "第141問", "タイムアウト2秒", "測定間隔1秒",
            "第140問", "最大5回", "第139問", "最低3回",
            "並列・順次処理", "通信・処理遅延",
            "サンプル品質", "例外処理", "第133問",
            "DD4%・5%", "別途決定",
        ):
            self.assertIn(v, excerpt)

    def test_fx_saf_006_approval_stays_pending(self):
        registry = json.loads((ROOT / "specs/reconciliation_registry.json").read_text(encoding="utf-8"))
        priority = json.loads((ROOT / "specs/source_review_priority.json").read_text(encoding="utf-8"))
        a = next(x for x in registry["items"] if x["requirement_id"] == "FX-SAF-006")
        b = next(x for x in priority["items"] if x["requirement_id"] == "FX-SAF-006")
        self.assertIn("Q142", a["question_ids"])
        self.assertIn("Q142", b["question_ids"])
        self.assertFalse(a["implementation_approved"])
        self.assertIsNone(a["owner_approval"])
        self.assertFalse(b["human_safety_approval"])
        self.assertEqual(b["source_review"], "PENDING_ORIGINAL")

    def test_global_deadline_preserves_prior_safety_requirements(self):
        doc = (ROOT / "specs/safety_foundation.md").read_text(encoding="utf-8")
        sec = doc.split("## Q142：", 1)[1].split("\n## ", 1)[0]
        for v in (
            "所要時間上限を45秒", "最初の測定開始",
            "45秒を超えた場合", "45秒ちょうど",
            "1検証全体", "各系別々に45秒", "検証不能",
            "自動解除を禁止", "Q126", "30分計測をリセット",
            "Q141", "タイムアウト2秒", "待機間隔1秒",
            "Q140", "最大5回試行", "Q139", "最低3回の有効測定",
            "Q138", "Q133", "異常時即失効", "未決",
            "並列・順次処理", "時間計測方法", "通信・処理遅延",
            "DD4%・5%", "本人承認必須停止",
            "ほかの停止理由", "implementation_approved=false",
        ):
            self.assertIn(v, sec)


if __name__ == "__main__":
    unittest.main()
