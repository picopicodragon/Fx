"""Q80 performance-monitoring recovery is not broker permission or a network L-level."""
import json
import unittest
from pathlib import Path

from scripts.check_reconciliation import check_reconciliation

ROOT = Path(__file__).resolve().parents[1]


def load(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


class Q80RecoveryLevelTests(unittest.TestCase):
    def test_all_four_distinct_recovery_cases(self):
        d = load("specs/p0_01_owner_q80_recovery_levels.json")
        self.assertEqual(d["question_id"], "Q80")
        self.assertEqual(d["design_option"], "C")
        levels = {v["level"]: v for v in d["levels"]}
        self.assertEqual(set(levels), {
            "PERFORMANCE_LEVEL_1", "PERFORMANCE_LEVEL_2",
            "PERFORMANCE_LEVEL_3", "DD_5_PERCENT_STOP"
        })
        self.assertEqual(levels["PERFORMANCE_LEVEL_1"]["conditions"], ["CAUSE_RESOLVED"])
        self.assertEqual(levels["PERFORMANCE_LEVEL_2"]["conditions"],
                         ["AI_REEVALUATION_PASSED", "SAFETY_CHECK_PASSED"])
        self.assertEqual(levels["PERFORMANCE_LEVEL_3"]["conditions"],
                         ["SAFETY_CHECK_PASSED", "EXPLICIT_HUMAN_APPROVAL"])
        self.assertFalse(levels["PERFORMANCE_LEVEL_3"]["temporary_dd_improvement_is_sufficient"])
        self.assertTrue(levels["PERFORMANCE_LEVEL_3"]["human_approval_required_by_this_level"])
        self.assertTrue(levels["DD_5_PERCENT_STOP"]["human_approval_required_by_this_level"])

    def test_q80_spec_keeps_hard_stop_and_level_names_separate(self):
        master = (ROOT / "MASTER_SPEC.md").read_text(encoding="utf-8")
        q80 = next(x for x in master.splitlines() if x.startswith("| Q80 |"))
        for snippet in ("DD2%", "3%", "4%", "LEVEL 1", "LEVEL 2", "LEVEL 3",
                        "AI再評価", "安全確認", "本人明示承認", "DD5%", "Q11/Q12"):
            with self.subTest(snippet=snippet):
                self.assertIn(snippet, q80)
        safety = (ROOT / "specs/safety_foundation.md").read_text(encoding="utf-8")
        for snippet in ("**成績悪化LEVEL 1：**", "**成績悪化LEVEL 2：**",
                        "**成績悪化LEVEL 3：**", "**DD5%到達：**",
                        "**通常監視への復帰≠新規注文の許可**",
                        "DD4%の独立した本人承認必須停止"):
            with self.subTest(snippet=snippet):
                self.assertIn(snippet, safety)

    def test_source_and_requirement_never_marked_approved(self):
        d = load("specs/p0_01_owner_q80_recovery_levels.json")
        for key in ("recorded_original_excerpt", "independently_verified_chat_message_id",
                    "source_excerpt_registered", "requirement_original_verified",
                    "implementation_approved", "human_safety_approval",
                    "owner_approved_for_safety", "forward_trading_enabled"):
            with self.subTest(key=key):
                self.assertIs(d[key], False)
        reg = load("specs/reconciliation_registry.json")
        self.assertEqual(check_reconciliation(reg), [])
        saf006 = next(x for x in reg["items"] if x["requirement_id"] == "FX-SAF-006")
        self.assertEqual(saf006["source_kind"], "SUMMARY_ONLY")
        self.assertEqual(saf006["comparison_status"], "SOURCE_UNAVAILABLE")
        self.assertFalse(saf006["implementation_approved"])
        self.assertIsNone(saf006["owner_approval"])
        for item in reg["items"]:
            self.assertFalse(item["implementation_approved"])
            self.assertIsNone(item["owner_approval"])
        phase1 = next(p for p in load("specs/acceptance_registry.json")["phases"]
                      if p["id"] == "PHASE-1")
        self.assertEqual(phase1["status"], "BLOCKED")

    def test_monitoring_clearance_not_equivalent_to_trade_permission(self):
        d = load("specs/p0_01_owner_q80_recovery_levels.json")
        joined = " ".join(d["interpretation_constraints"])
        self.assertIn("not itself permission to open positions", joined)
        self.assertIn("communication failure", joined)
        self.assertIn("DD4%", joined)
        self.assertIn("Fail Closed", joined)


if __name__ == "__main__":
    unittest.main()
