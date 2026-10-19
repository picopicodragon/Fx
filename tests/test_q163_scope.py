"""Q163 reset corrupt receive channel, never reset last-valid heartbeat or safety state."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Q163DecisionTests(unittest.TestCase):
    def test_answer_and_presented_choice_distinguished(self):
        records = json.loads((ROOT / "specs/source_evidence.json").read_text(encoding="utf-8"))["records"]
        rec = next(x for x in records if x["question_id"] == "Q163")
        self.assertEqual(rec["source_kind"], "ORIGINAL")
        self.assertEqual(rec["verification"], "DIRECT_CHAT")
        self.assertEqual(rec["archive_locator_status"], "PENDING_LOCAL_ARCHIVE")
        self.assertFalse(rec["owner_approved_for_safety"])
        excerpt = (ROOT / rec["excerpt_path"]).read_text(encoding="utf-8")
        for token in (
            "第163問はBを採用する", "本人の直接発言ではない",
            "通信状態リセット＋安全再受信型", "異常フレームを破棄",
            "受信状態と通信接続をリセット", "完全なフレーム",
            "再接続回数や待機時間は後続で決定", "未決",
        ):
            self.assertIn(token, excerpt)

    def test_reset_no_forged_validity_and_prior_safety(self):
        text = (ROOT / "specs/safety_foundation.md").read_text(encoding="utf-8")
        sec = text.split("## Q163：", 1)[1].split("\n## ", 1)[0]
        for token in (
            "DD2%警告", "DD3%重点再評価", "独立ウォッチドッグ",
            "通信状態リセット＋安全再受信", "異常フレーム", "途中切断",
            "タイムアウト", "破棄", "受信状態", "通信接続",
            "断片", "混在", "再接続", "完全なフレーム",
            "正常確認時刻を更新しない", "安全停止理由", "連番履歴", "リプレイ",
            "Q162", "段階的受信＋累積サイズ監視", "20 KiB", "20,480バイト",
            "Q161", "Q160", "UINT32BE", "事前長さ検証",
            "Q159", "16 KiB", "16,384バイト", "4 KiB", "4,096バイト",
            "Q158", "Q157", "固定順序", "Q156", "プロトコル版",
            "送信元ID", "セッション識別子", "連番", "鮮度検証用時刻",
            "ハートビート本文", "Q155", "HMAC-SHA256",
            "Windowsローカル通信のアクセス制御", "Q154", "形式", "鮮度",
            "重複・再送", "全検証合格", "Q153", "受信した瞬間",
            "Windows単調増加時計", "Q150", "通常2秒", "Q151",
            "厳密に6秒超", "Q152", "欠落回数", "Q149",
            "Windows電源イベント", "Q148", "2回連続成功を無効",
            "Q126の30分計測をリセット", "安全検証を最初から",
            "30分計測再開", "自動解除を禁止", "Q145〜Q147",
            "60秒以上", "UTC", "Q133",
            "最大5分間有効・異常時即失効", "Q139〜Q143", "45秒",
            "並列測定", "DD4%・5%", "本人承認必須停止",
            "ほかの停止理由", "未決", "implementation_approved=false",
        ):
            self.assertIn(token, sec)

    def test_registry_unapproved_and_single_decision(self):
        rr = json.loads((ROOT / "specs/reconciliation_registry.json").read_text(encoding="utf-8"))
        pp = json.loads((ROOT / "specs/source_review_priority.json").read_text(encoding="utf-8"))
        a = next(x for x in rr["items"] if x["requirement_id"] == "FX-SAF-006")
        b = next(x for x in pp["items"] if x["requirement_id"] == "FX-SAF-006")
        self.assertIn("Q163", a["question_ids"])
        self.assertIn("Q163", b["question_ids"])
        self.assertFalse(a["implementation_approved"])
        self.assertIsNone(a["owner_approval"])
        self.assertFalse(b["human_safety_approval"])
        self.assertEqual(b["source_review"], "PENDING_ORIGINAL")
        dec = (ROOT / "DECISIONS.md").read_text(encoding="utf-8")
        self.assertEqual(sum(line.startswith("| Q163 |") for line in dec.splitlines()), 1)
        self.assertIn("v16.3", (ROOT / "MASTER_SPEC.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
