"""P0-01 policy crosswalk: compatibility and unresolved risks, never approval."""
import json
import unittest
from pathlib import Path

from scripts.check_reconciliation import check_reconciliation

ROOT = Path(__file__).resolve().parents[1]
CROSSWALK = "specs/p0_01_safety_consistency_crosswalk.json"


def read(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


class SafetyCrosswalkReviewTests(unittest.TestCase):
    def test_six_distinct_crosschecks_with_supported_question_scope(self):
        report = read(CROSSWALK)
        checks = report["crosswalk"]
        self.assertEqual({c["id"] for c in checks},
                         {f"CW-{i:02d}" for i in range(1, 7)})
        self.assertEqual(len(checks), 6)
        for item in checks:
            self.assertTrue(item["binding_interpretation"])
            self.assertTrue(item["remaining"])
            self.assertTrue(item["questions"])
            self.assertTrue(item["requirements"])
            self.assertTrue(all(q.startswith("Q") for q in item["questions"]))
            self.assertTrue(all(x.startswith("FX-SAF-") for x in item["requirements"]))

    def test_critical_distinctions_are_not_conflated(self):
        report = read(CROSSWALK)
        by_id = {x["id"]: x for x in report["crosswalk"]}
        self.assertIn("0.5%", by_id["CW-01"]["binding_interpretation"])
        self.assertIn("1.0%", by_id["CW-01"]["binding_interpretation"])
        self.assertIn("1.5%", by_id["CW-02"]["binding_interpretation"])
        self.assertIn("NY17:00", by_id["CW-02"]["binding_interpretation"])
        self.assertIn("30-minute", by_id["CW-03"]["binding_interpretation"])
        self.assertIn("DD4/5", by_id["CW-03"]["binding_interpretation"])
        self.assertIn("communication L1/L2/L3", by_id["CW-04"]["binding_interpretation"])
        self.assertIn("human-approval", by_id["CW-05"]["binding_interpretation"])
        self.assertIn("OUTCOME_UNKNOWN", by_id["CW-06"]["binding_interpretation"])
        self.assertIn("no duplicate", by_id["CW-06"]["binding_interpretation"])

    def test_priorities_preserve_unresolved_implementation_details(self):
        report = read(CROSSWALK)
        priorities = report["priority_decisions"]
        self.assertEqual(len(priorities), 5)
        self.assertEqual([p["priority"] for p in priorities], ["P0", "P0", "P0", "P1", "P1"])
        self.assertEqual(report["review_findings"]["direct_conflicts_confirmed"], 0)
        self.assertEqual(
            report["review_findings"]["conditional_interpretations_requiring_implementation_detail"],
            ["CW-03", "CW-04", "CW-05", "CW-06"]
        )
        for item in report["crosswalk"]:
            self.assertFalse(item["finding"] == "IMPLEMENTATION_APPROVED")
        doc = (ROOT / "docs/p0_01_safety_consistency_review_20261023.md").read_text(
            encoding="utf-8"
        )
        for mark in ("CW-01", "CW-02", "CW-03", "CW-04", "CW-05", "CW-06"):
            self.assertIn(mark, doc)

    def test_existing_source_and_reconciliation_not_elevated(self):
        report = read(CROSSWALK)
        registry = read("specs/reconciliation_registry.json")
        self.assertEqual(check_reconciliation(registry), [])
        ids = {r["requirement_id"] for r in registry["items"]}
        for item in report["crosswalk"]:
            self.assertTrue(set(item["requirements"]) <= ids)
        for entry in registry["items"]:
            self.assertFalse(entry["implementation_approved"])
            self.assertIsNone(entry["owner_approval"])
        for r in read("specs/source_review_priority.json")["items"]:
            self.assertEqual(r["source_review"], "PENDING_ORIGINAL")
            self.assertFalse(r["human_safety_approval"])

    def test_no_live_order_or_phase_approval(self):
        flags = read(CROSSWALK)["authorizations"]
        for key in ("whole_requirements_reconciled", "full_original_context_verified",
                    "implementation_approved", "human_safety_approval",
                    "owner_approved_for_safety", "forward_trading_enabled",
                    "allow_live_orders"):
            with self.subTest(key=key):
                self.assertIs(flags[key], False)
        self.assertEqual(flags["phase_1"], "BLOCKED")
        phase = next(p for p in read("specs/acceptance_registry.json")["phases"]
                     if p["id"] == "PHASE-1")
        self.assertEqual(phase["status"], "BLOCKED")
        self.assertIsNone(phase["approval"])


if __name__ == "__main__":
    unittest.main()
