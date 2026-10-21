"""Q171: unresolved resource-isolation failure latches a critical stop until human approval."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Q171DecisionTests(unittest.TestCase):
    def test_direct_source_and_option_not_conflated(self):
        records = json.loads((ROOT / "specs/source_evidence.json").read_text(encoding="utf-8"))["records"]
        record = next(x for x in records if x["question_id"] == "Q171")
        self.assertEqual(record["source_kind"], "ORIGINAL")
        self.assertEqual(record["verification"], "DIRECT_CHAT")
        self.assertEqual(record["archive_locator_status"], "PENDING_LOCAL_ARCHIVE")
        self.assertFalse(record["owner_approved_for_safety"])
        quote = (ROOT / record["excerpt_path"]).read_text(encoding="utf-8")
        for term in ("第171問はBを採用する", "本人の直接発言ではない",
                     "重大障害通知＋隔離失敗状態の保持型",
                     "本人承認を必須", "安全検証", "未決"):
            self.assertIn(term, quote)

    def test_critical_isolation_stop_and_all_safety_preservation(self):
        doc = (ROOT / "specs/safety_foundation.md").read_text(encoding="utf-8")
        sec = doc.split("## Q171：", 1)[1].split("\n## ", 1)[0]
        for term in (
            "DD2%警告", "DD3%重点再評価", "独立ウォッチドッグ",
            "重大障害通知＋隔離失敗状態の保持", "隔離失敗状態",
            "重大障害", "LINE＋メール", "安全停止", "自動復旧を禁止",
            "原因解消", "安全検証", "本人承認", "明示的", "再開",
            "新規注文停止", "プロセス再起動", "無条件に解除しない",
            "未確認", "次の試行", "正常認定", "遅延通知",
            "Q170", "閉鎖", "旧試行ID", "通信ハンドル",
            "Q169", "最大1秒", "Q168", "全検証条件",
            "Q167", "非同期通信", "明示的キャンセル",
            "Q166", "最大2秒", "Q165", "最大4回",
            "1秒", "2秒", "4秒", "8秒", "総復旧25秒",
            "Q164", "段階的バックオフ", "連続60秒",
            "連続10分", "自動再起動最大3回", "Q163",
            "通信接続", "断片", "安全停止理由", "リプレイ防止",
            "Q162", "段階的受信", "Q161", "20 KiB",
            "Q160", "UINT32BE", "事前長さ検証",
            "Q159", "16 KiB", "4 KiB", "Q158",
            "Q157", "固定順序", "Q156", "プロトコル版",
            "送信元ID", "セッション識別子", "連番",
            "鮮度検証用時刻", "ハートビート本文",
            "Q155", "HMAC-SHA256", "Windowsローカル通信のアクセス制御",
            "Q154", "形式", "鮮度", "重複・再送", "全検証合格",
            "Q153", "受信した瞬間", "Windows単調増加時計",
            "更新しない", "Q150", "通常2秒", "Q151",
            "厳密に6秒超", "Q152", "欠落回数", "Q149",
            "Windows電源イベント", "Q148", "2回連続成功を無効",
            "Q126の30分計測をリセット", "安全検証を最初から",
            "30分計測再開", "自動解除を禁止",
            "Q145〜Q147", "60秒以上", "UTC", "Q133",
            "最大5分間有効・異常時即失効", "Q139〜Q143",
            "45秒", "並列測定", "DD4%・5%", "本人承認必須停止",
            "ほかの停止理由", "未決", "implementation_approved=false",
        ):
            self.assertIn(term, sec)

    def test_evidence_traceability_approval_hold_and_decision_once(self):
        a = json.loads((ROOT / "specs/reconciliation_registry.json").read_text(encoding="utf-8"))
        b = json.loads((ROOT / "specs/source_review_priority.json").read_text(encoding="utf-8"))
        reg = next(x for x in a["items"] if x["requirement_id"] == "FX-SAF-006")
        pri = next(x for x in b["items"] if x["requirement_id"] == "FX-SAF-006")
        self.assertIn("Q171", reg["question_ids"])
        self.assertIn("Q171", pri["question_ids"])
        self.assertFalse(reg["implementation_approved"])
        self.assertIsNone(reg["owner_approval"])
        self.assertFalse(pri["human_safety_approval"])
        self.assertEqual(pri["source_review"], "PENDING_ORIGINAL")
        dec = (ROOT / "DECISIONS.md").read_text(encoding="utf-8")
        self.assertEqual(sum(x.startswith("| Q171 |") for x in dec.splitlines()), 1)
        master = (ROOT / "MASTER_SPEC.md").read_text(encoding="utf-8")
        sec = master.split("## Q171：", 1)[1].split("\n## ", 1)[0]
        for term in ("隔離失敗状態を保持", "自動復旧禁止", "本人の明示的な再開承認",
                     "安全重要実装・実口座売買は未承認"):
            self.assertIn(term, sec)


if __name__ == "__main__":
    unittest.main()
