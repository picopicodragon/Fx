"""Q148 design scope and retained safety approval gates."""
import json
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

class Q148DecisionTests(unittest.TestCase):
    def test_source(self):
        p = json.loads((ROOT / "specs/source_evidence.json").read_text(encoding="utf-8"))
        r = next(x for x in p["records"] if x["question_id"] == "Q148")
        self.assertEqual(r["verification"], "DIRECT_CHAT")
        self.assertEqual(r["archive_locator_status"], "PENDING_LOCAL_ARCHIVE")
        self.assertFalse(r["owner_approved_for_safety"])
        s = (ROOT / r["excerpt_path"]).read_text(encoding="utf-8")
        for x in ("第148問はAを採用する", "本人の直接発言ではない",
                  "スリープ・休止状態を検知した場合", "30分計測もリセット"):
            self.assertIn(x, s)

    def test_safety_and_unapproved_state(self):
        s = (ROOT / "specs/safety_foundation.md").read_text(encoding="utf-8")
        q = s.split("## Q148：", 1)[1].split("\n## ", 1)[0]
        for x in ("Q126", "Q133", "Q139", "Q143", "スリープ・休止",
                  "2回連続成功", "30分計測", "自動解除を禁止",
                  "復帰後", "最初から", "DD4%・5%", "本人承認必須停止",
                  "implementation_approved=false"):
            self.assertIn(x, q)
        for path in ("specs/reconciliation_registry.json","specs/source_review_priority.json"):
            data = json.loads((ROOT / path).read_text(encoding="utf-8"))
            rec = next(x for x in data["items"] if x["requirement_id"] == "FX-SAF-006")
            self.assertIn("Q148", rec["question_ids"])
            self.assertFalse(rec["implementation_approved"] if "implementation_approved" in rec else rec["human_safety_approval"])
        dec = (ROOT / "DECISIONS.md").read_text(encoding="utf-8")
        self.assertEqual(sum(x.startswith("| Q148 |") for x in dec.splitlines()), 1)
        self.assertIn("v14.8", (ROOT / "MASTER_SPEC.md").read_text(encoding="utf-8"))

if __name__ == "__main__":
    unittest.main()
