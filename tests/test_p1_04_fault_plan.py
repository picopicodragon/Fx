"""P1-04: structural checks for a *planned* offline fault-injection matrix.

This module does not open SQLite, cause failures, or test trading safety.
"""
import json
import unittest
from pathlib import Path

MATRIX = Path(__file__).resolve().parents[1] / "specs" / "p1_04_fault_matrix.json"


def load_matrix() -> dict:
    return json.loads(MATRIX.read_text(encoding="utf-8"))


class P104FaultPlanTests(unittest.TestCase):
    def test_draft_only_and_no_unearned_approvals(self):
        plan = load_matrix()
        self.assertEqual(plan["schema_version"], 1)
        self.assertEqual(plan["plan_id"], "P1-04")
        self.assertEqual(plan["plan_status"], "DRAFT_ONLY")
        self.assertFalse(plan["live_trading_permitted"])
        self.assertFalse(plan["safety_implementation_approved"])

    def test_all_cases_are_planned_never_claimed_executed(self):
        cases = load_matrix()["test_cases"]
        self.assertEqual(len(cases), 26)
        ids = [case["id"] for case in cases]
        self.assertEqual(len(set(ids)), len(ids))
        for case in cases:
            with self.subTest(case=case["id"]):
                self.assertTrue(case["id"].startswith("P1-04-F"))
                self.assertEqual(case["fixture"], "SYNTHETIC_OR_DISPOSABLE_SQLITE_ONLY")
                self.assertEqual(case["execution_status"], "NOT_EXECUTED")
                self.assertEqual(case["evidence_refs"], [])
                self.assertFalse(case["owner_safety_approved"])
                self.assertTrue(case["requirements"])
                self.assertTrue(case["fault"])
                self.assertTrue(case["expected"])
                self.assertTrue(all(ref.startswith("Q") for ref in case["requirements"]))

    def test_coverage_of_db_stop_order_and_human_gate(self):
        cases = load_matrix()["test_cases"]
        categories = {case["category"] for case in cases}
        self.assertEqual(categories, {
            "DURABILITY", "RESTORE", "WAL", "CONCURRENCY",
            "DISPATCH", "AUTHORIZATION",
        })
        covered = {ref for case in cases for ref in case["requirements"]}
        for critical in ("Q171", "Q172", "Q173", "Q174", "Q175",
                         "Q176", "Q180", "Q189", "Q190", "Q192",
                         "Q193", "Q194", "Q195", "Q196", "Q197",
                         "Q198", "Q199"):
            with self.subTest(requirement=critical):
                self.assertIn(critical, covered)
        expected = {event for case in cases for event in case["expected"]}
        self.assertIn("STOP_LATCH_PRESERVED", expected)
        self.assertIn("OWNER_APPROVAL_REQUIRED", expected)
        self.assertIn("NO_BLIND_RETRY", expected)
        self.assertIn("OUTCOME_UNKNOWN", expected)
        self.assertIn("BROKER_RECONCILIATION_REQUIRED", expected)

    def test_original_wal_thresholds_are_not_changed(self):
        thresholds = load_matrix()["thresholds_existing_not_validated"]
        self.assertEqual(thresholds["wal_absolute_mib"],
                         {"warning": 64, "major": 256, "critical": 512})
        self.assertEqual(thresholds["wal_growth_one_minute_mib"],
                         {"warning": 8, "major": 32, "critical": 128})
        self.assertEqual(thresholds["wal_growth_five_minute_mib"],
                         {"warning": 32, "major": 128, "critical": 256})
        self.assertEqual(thresholds["ordinary_monitor_interval_seconds"], 10)

    def test_unknown_commit_and_isolation_failure_never_get_approval(self):
        by_id = {item["id"]: item for item in load_matrix()["test_cases"]}
        self.assertIn("NEW_ORDER_BLOCKED", by_id["P1-04-F03"]["expected"])
        self.assertIn("OWNER_APPROVAL_REQUIRED", by_id["P1-04-F06"]["expected"])
        self.assertIn("STOP_LATCH_PRESERVED", by_id["P1-04-F09"]["expected"])
        self.assertIn("OUTCOME_UNKNOWN", by_id["P1-04-F23"]["expected"])
        self.assertIn("NO_BLIND_RETRY", by_id["P1-04-F23"]["expected"])


if __name__ == "__main__":
    unittest.main()
