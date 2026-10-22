"""P0-01 Q80 owner extra detail tests. No original-text or trading approval claim."""
import json
import unittest
from pathlib import Path

from scripts.check_reconciliation import check_reconciliation


ROOT = Path(__file__).resolve().parents[1]


def read_json(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


class Q80OwnerHybridMonitorTests(unittest.TestCase):
    def test_owner_report_contains_hybrid_and_level3_human_gate(self):
        d = read_json("specs/p0_01_owner_q80_additional_details.json")
        self.assertEqual(d["question_id"], "Q80")
        self.assertEqual(d["design_option"], "C")
        self.assertEqual(d["owner_review_result"], "ADDITIONAL_DETAILS")
        by_id = {item["element"]: item["details"] for item in d["confirmed_elements"]}
        self.assertEqual(set(by_id), {
            "DD_LEVELS", "HYBRID_PERFORMANCE_MONITOR", "LEVEL3_RESTART_GATE"
        })
        self.assertIn("2%", by_id["DD_LEVELS"])
        self.assertIn("3%", by_id["DD_LEVELS"])
        self.assertIn("4%", by_id["DD_LEVELS"])
        self.assertIn("statistical", by_id["HYBRID_PERFORMANCE_MONITOR"])
        self.assertIn("AI", by_id["HYBRID_PERFORMANCE_MONITOR"])
        self.assertIn("human approval", by_id["LEVEL3_RESTART_GATE"])

    def test_q80_index_and_safety_spec_are_reconciled(self):
        master = (ROOT / "MASTER_SPEC.md").read_text(encoding="utf-8")
        q80 = next(line for line in master.splitlines() if line.startswith("| Q80 |"))
        for piece in ("DD2%", "3%", "4%", "統計評価", "AI分析", "ハイブリッド", "LEVEL 3", "人間"):
            with self.subTest(piece=piece):
                self.assertIn(piece, q80)
        safety = (ROOT / "specs/safety_foundation.md").read_text(encoding="utf-8")
        self.assertIn("## Q80：成績悪化ハイブリッド監視", safety)
        self.assertIn("LEVEL 3の解除は人間の承認を必須", safety)
        self.assertIn("DD5%到達時の全決済試行", safety)
        self.assertIn("Q11/Q12の独立した安全要件", safety)

    def test_fx_saf_006_remains_unverified_requirement_not_match(self):
        registry = read_json("specs/reconciliation_registry.json")
        self.assertEqual(check_reconciliation(registry), [])
        item = next(x for x in registry["items"] if x["requirement_id"] == "FX-SAF-006")
        reported = item["partial_owner_question_reviews"]
        self.assertEqual(len(reported), 2)
        by_status = {entry["result"]: entry for entry in reported}
        self.assertEqual(set(by_status), {"ADDITIONAL_DETAILS", "ADDITIONAL_RECOVERY_CONDITIONS"})
        self.assertEqual(by_status["ADDITIONAL_DETAILS"]["question_id"], "Q80")
        self.assertEqual(
            by_status["ADDITIONAL_DETAILS"]["evidence_ref"],
            "specs/p0_01_owner_q80_additional_details.json"
        )
        self.assertEqual(
            by_status["ADDITIONAL_RECOVERY_CONDITIONS"]["evidence_ref"],
            "specs/p0_01_owner_q80_recovery_levels.json"
        )
        self.assertEqual(item["source_kind"], "SUMMARY_ONLY")
        self.assertEqual(item["comparison_status"], "SOURCE_UNAVAILABLE")
        self.assertFalse(item["implementation_approved"])
        self.assertIsNone(item["owner_approval"])

    def test_live_trading_and_phase_remain_disabled(self):
        d = read_json("specs/p0_01_owner_q80_additional_details.json")
        for key in (
            "source_excerpt_registered", "original_source_message_id_verified",
            "source_kind_upgraded", "safety_requirement_comparison_upgraded",
            "human_safety_approval", "implementation_approved",
            "owner_approved_for_safety", "forward_trading_enabled"
        ):
            with self.subTest(key=key):
                self.assertIs(d[key], False)
        priority = read_json("specs/source_review_priority.json")
        for item in priority["items"]:
            self.assertEqual(item["source_review"], "PENDING_ORIGINAL")
            self.assertFalse(item["human_safety_approval"])
        acceptance = read_json("specs/acceptance_registry.json")
        phase1 = next(x for x in acceptance["phases"] if x["id"] == "PHASE-1")
        self.assertEqual(phase1["status"], "BLOCKED")
        self.assertIsNone(phase1["approval"])


if __name__ == "__main__":
    unittest.main()
