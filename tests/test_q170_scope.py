"""Q170 logical generation fencing plus resource-close attempt, fail closed until verified."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Q170DecisionTests(unittest.TestCase):
    def test_direct_user_choice_distinct_from_proposal(self):
        evidence = json.loads((ROOT / "specs/source_evidence.json").read_text(encoding="utf-8"))
        record = next(x for x in evidence["records"] if x["question_id"] == "Q170")
        self.assertEqual(record["source_kind"], "ORIGINAL")
        self.assertEqual(record["verification"], "DIRECT_CHAT")
        self.assertEqual(record["archive_locator_status"], "PENDING_LOCAL_ARCHIVE")
        self.assertFalse(record["owner_approved_for_safety"])
        excerpt = (ROOT / record["excerpt_path"]).read_text(encoding="utf-8")
        for token in (
            "第170問はBを採用する", "本人の直接発言ではない",
            "通信資源閉鎖＋論理的隔離型", "旧試行IDを無効化",
            "旧接続・通信ハンドルの閉鎖を試みる", "遅延通知も破棄",
            "終了確認方法と、閉鎖に失敗した場合の復旧条件は後続設問",
        ):
            self.assertIn(token, excerpt)

    def test_fail_closed_isolation_scope_and_retained_prior_guards(self):
        safety = (ROOT / "specs/safety_foundation.md").read_text(encoding="utf-8")
        section = safety.split("## Q170：", 1)[1].split("\n## ", 1)[0]
        for token in (
            "DD2%警告", "DD3%重点再評価", "独立ウォッチドッグ",
            "通信資源閉鎖＋論理的隔離", "旧試行ID", "無効化",
            "通信ハンドル", "閉鎖", "遅延通知", "旧処理",
            "未完了通信", "資源隔離", "閉鎖APIの成功", "保証しない",
            "安全停止", "通知", "追加再接続", "正常認定", "更新しない",
            "Q169", "最大1秒", "Q168", "試行ID", "全検証条件",
            "Q167", "非同期通信", "明示的キャンセル",
            "Q166", "最大2秒", "Q165", "最大4回",
            "1秒", "2秒", "4秒", "8秒", "総復旧25秒", "Q164",
            "段階的バックオフ", "連続60秒", "連続10分",
            "自動再起動最大3回", "Q163", "断片", "リプレイ防止",
            "Q162", "段階的受信", "Q161", "20 KiB",
            "Q160", "UINT32BE", "事前長さ検証", "Q159",
            "16 KiB", "4 KiB", "Q158", "Q157", "固定順序",
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
            "最大5分間有効・異常時即失効", "Q139〜Q143",
            "45秒", "並列測定", "DD4%・5%", "本人承認必須停止",
            "ほかの停止理由", "未決", "implementation_approved=false",
        ):
            self.assertIn(token, section)

    def test_approval_hold_and_unique_decision(self):
        r = json.loads((ROOT / "specs/reconciliation_registry.json").read_text(encoding="utf-8"))
        p = json.loads((ROOT / "specs/source_review_priority.json").read_text(encoding="utf-8"))
        a = next(x for x in r["items"] if x["requirement_id"] == "FX-SAF-006")
        b = next(x for x in p["items"] if x["requirement_id"] == "FX-SAF-006")
        self.assertIn("Q170", a["question_ids"])
        self.assertIn("Q170", b["question_ids"])
        self.assertFalse(a["implementation_approved"])
        self.assertIsNone(a["owner_approval"])
        self.assertFalse(b["human_safety_approval"])
        self.assertEqual(b["source_review"], "PENDING_ORIGINAL")
        decisions = (ROOT / "DECISIONS.md").read_text(encoding="utf-8")
        self.assertEqual(sum(x.startswith("| Q170 |") for x in decisions.splitlines()), 1)
        self.assertIn("v17.0", (ROOT / "MASTER_SPEC.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
