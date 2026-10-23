"""P0-01: stop reason draft checks only; never implements order or recovery actions."""
import json
import unittest
from pathlib import Path

from scripts.check_reconciliation import check_reconciliation

ROOT = Path(__file__).resolve().parents[1]
SPEC = "specs/p0_01_stop_reason_clearance_matrix_draft.json"


def load(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


class StopReasonDraftTests(unittest.TestCase):
    def setUp(self):
        self.d = load(SPEC)
        self.rows = {r["id"]: r for r in self.d["rows"]}

    def test_unique_rows_namespaces_and_review_scope(self):
        self.assertEqual(self.d["status"], "DRAFT_FROM_ADOPTED_POLICY_NOT_FINAL_STATE_MACHINE")
        self.assertEqual(len(self.rows), len(self.d["rows"]))
        self.assertGreaterEqual(len(self.rows), 14)
        groups = self.d["namespaces"]
        self.assertEqual(len({g["name"] for g in groups}), len(groups))
        for g in groups:
            for member in g["members"]:
                self.assertIn(member, self.rows)
                self.assertEqual(self.rows[member]["namespace"], g["name"])
        self.assertEqual(set(self.rows),
                         {name for g in groups for name in g["members"]})

    def test_dd4_dd5_and_performance_level3_never_auto_clear(self):
        for item in ("DD4_NEW_ORDER_HALT", "DD5_EMERGENCY_HALT",
                     "PERFORMANCE_LEVEL3", "NETWORK_L3", "ISOLATION_FAILURE"):
            with self.subTest(item=item):
                row = self.rows[item]
                self.assertEqual(row["effect"], "BLOCK_NEW_ORDERS")
                self.assertEqual(row["automatic_clear"], "FORBIDDEN")
                self.assertIs(row["explicit_human_approval_required"], True)
                self.assertIn("Explicit human approval", row["necessary_evidence"])
        self.assertEqual(self.rows["PERFORMANCE_LEVEL3"]["clearance_scope"], "THIS_STOP_ONLY")

    def test_monitor_levels_distinct_from_stop_and_dd_monitor_thresholds(self):
        for item, threshold in (("DD2_WARNING", "1.5%"),
                                ("DD3_FOCUSED_REVIEW", "2.5%")):
            with self.subTest(item=item):
                row = self.rows[item]
                self.assertEqual(row["effect"], "MONITOR_ONLY")
                self.assertEqual(row["clearance_scope"], "THIS_MONITOR_ONLY")
                self.assertEqual(row["automatic_monitor_clear"], "CONDITIONAL")
                self.assertTrue(any(threshold in e and "30 minutes" in e
                                    for e in row["necessary_evidence"]))
        self.assertEqual(self.rows["PERFORMANCE_LEVEL1"]["effect"], "MONITOR_ONLY")
        self.assertEqual(self.rows["PERFORMANCE_LEVEL2"]["effect"], "MONITOR_ONLY")
        self.assertNotEqual(self.rows["PERFORMANCE_LEVEL3"]["namespace"],
                            self.rows["NETWORK_L3"]["namespace"])

    def test_day_loss_and_unknown_outcome_are_separate(self):
        daily = self.rows["DAILY_LOSS_HALT"]
        self.assertEqual(daily["automatic_clear"], "CONDITIONAL")
        self.assertTrue(any("NY17:00" in s for s in daily["necessary_evidence"]))
        self.assertEqual(daily["clearance_scope"], "THIS_STOP_ONLY")
        outcome = self.rows["ORDER_OUTCOME_UNKNOWN"]
        self.assertEqual(outcome["automatic_clear"], "NO_AUTOMATIC_RETRY")
        self.assertTrue(any("No duplicate or reverse" in x
                            for x in outcome["necessary_evidence"]))
        self.assertEqual(self.rows["STATE_OR_RISK_UNKNOWN"]["automatic_clear"],
                         "FORBIDDEN_WHILE_UNKNOWN")

    def test_synthetic_cases_preserve_stops_and_global_gate(self):
        scenarios = {x["id"]: x for x in self.d["synthetic_cases"]}
        self.assertEqual(set(scenarios), {f"SC-{i:02d}" for i in range(1, 11)})
        self.assertTrue(all(c["live_orders_allowed"] is False
                            for c in scenarios.values()))
        self.assertEqual(scenarios["SC-01"]["expected_remaining"],
                         ["DD4_NEW_ORDER_HALT"])
        self.assertIn("DD4_NEW_ORDER_HALT", scenarios["SC-02"]["expected_remaining"])
        self.assertIn("DD5_EMERGENCY_HALT", scenarios["SC-03"]["expected_remaining"])
        self.assertIn("PERFORMANCE_LEVEL3", scenarios["SC-04"]["expected_remaining"])
        self.assertEqual(scenarios["SC-05"]["expected_remaining"],
                         ["DD5_EMERGENCY_HALT"])
        self.assertEqual(set(scenarios["SC-06"]["expected_remaining"]),
                         {"NETWORK_L1", "ISOLATION_FAILURE"})
        self.assertIn("STATE_OR_RISK_UNKNOWN",
                      scenarios["SC-07"]["expected_remaining"])
        self.assertIn("ORDER_OUTCOME_UNKNOWN",
                      scenarios["SC-08"]["expected_remaining"])
        self.assertEqual(scenarios["SC-09"]["expected_remaining"],
                         ["DD4_NEW_ORDER_HALT"])
        self.assertEqual(scenarios["SC-10"]["expected_remaining"], [])

    def test_no_source_upgrade_implementation_or_live_authorization(self):
        auth = self.d["safety_authorization"]
        for key in ("implementation_approved", "human_safety_approval",
                    "owner_approved_for_safety", "forward_trading_enabled",
                    "live_orders_allowed"):
            self.assertIs(auth[key], False)
        self.assertEqual(auth["phase_1"], "BLOCKED")
        registry = load("specs/reconciliation_registry.json")
        self.assertEqual(check_reconciliation(registry), [])
        for row in registry["items"]:
            self.assertFalse(row["implementation_approved"])
            self.assertIsNone(row["owner_approval"])
        for row in load("specs/source_review_priority.json")["items"]:
            self.assertEqual(row["source_review"], "PENDING_ORIGINAL")
            self.assertFalse(row["human_safety_approval"])
        p = next(x for x in load("specs/acceptance_registry.json")["phases"]
                 if x["id"] == "PHASE-1")
        self.assertEqual(p["status"], "BLOCKED")
        self.assertIsNone(p["approval"])


if __name__ == "__main__":
    unittest.main()
