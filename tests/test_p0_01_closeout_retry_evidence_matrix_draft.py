"""Q120/Q195-Q199 close-out retry evidence checks, documentation only.

These tests validate draft data and fail-closed examples, NOT trading code.
"""
import json
import unittest
from pathlib import Path

from scripts.check_reconciliation import check_reconciliation

ROOT = Path(__file__).resolve().parents[1]
REPORT = "specs/p0_01_closeout_retry_evidence_matrix_draft.json"


def load(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


class CloseoutRetryEvidenceDraftTests(unittest.TestCase):
    def setUp(self):
        self.report = load(REPORT)

    def test_related_source_and_draft_status(self):
        d = self.report
        self.assertEqual(d["lifecycle_status"], "DRAFT_REVIEW_REQUIRED")
        self.assertEqual(d["question_ids"], [
            "Q9", "Q12", "Q120", "Q121", "Q171", "Q195",
            "Q196", "Q197", "Q198", "Q199"
        ])
        self.assertEqual(len(set(d["requirement_ids"])), len(d["requirement_ids"]))
        for src in d["related_sources"]:
            self.assertTrue((ROOT / src).is_file(), src)

    def test_response_classes_do_not_imply_final_broker_state(self):
        rows = {item["code"]: item for item in self.report["response_classes"]}
        self.assertEqual(set(rows), {
            "RESPONSE_ACCEPTED", "RESPONSE_REJECTED", "OUTCOME_UNKNOWN"
        })
        self.assertEqual(rows["RESPONSE_ACCEPTED"]["safe_conclusion"],
                         "RECONCILE_FINAL_STATE_BEFORE_ANY_RETRY")
        self.assertEqual(rows["RESPONSE_REJECTED"]["safe_conclusion"],
                         "RECONCILE_FINAL_STATE_BEFORE_ANY_RETRY")
        self.assertEqual(rows["OUTCOME_UNKNOWN"]["safe_conclusion"],
                         "NO_RETRY_OR_NEW_ORDERS_WHILE_UNRESOLVED")

    def test_eight_independent_required_evidence_dimensions(self):
        proofs = self.report["minimum_proofs_for_retry_consideration"]
        self.assertEqual({p["id"] for p in proofs},
                         {f"EP-{i:02d}" for i in range(1, 9)})
        self.assertEqual(len(proofs), 8)
        for p in proofs:
            self.assertTrue(p["description"])
        joined = " ".join(self.report["durable_evidence_order"])
        for required in ("PREPARED", "DISPATCHING", "Q199", "SL",
                         "partial fills", "UNKNOWN"):
            with self.subTest(value=required):
                self.assertIn(required, joined)

    def test_review_outcomes_do_not_authorize_retry(self):
        results = {v["id"]: v for v in self.report["draft_review_outcomes"]}
        self.assertEqual(set(results), {
            "BLOCKED_UNKNOWN", "BLOCKED_NOT_NEEDED",
            "ELIGIBLE_FOR_LATER_POLICY_CHECK", "BLOCKED_OTHER_STOP"
        })
        for row in results.values():
            self.assertIn(row["kind"], {
                "SAFETY_REJECT", "REVIEW_ONLY_NOT_ORDER_PERMISSION"
            })
        self.assertEqual(results["ELIGIBLE_FOR_LATER_POLICY_CHECK"]["kind"],
                         "REVIEW_ONLY_NOT_ORDER_PERMISSION")
        self.assertIn("not an order", results["ELIGIBLE_FOR_LATER_POLICY_CHECK"]["meaning"])

    def test_twelve_offline_cases_never_allow_auto_orders(self):
        cases = {v["id"]: v for v in self.report["synthetic_cases"]}
        self.assertEqual(set(cases), {f"RT-{i:02d}" for i in range(1, 13)})
        self.assertTrue(all(v["automatic_retry_allowed"] is False
                            for v in cases.values()))
        for k in ("RT-01", "RT-02", "RT-03", "RT-07", "RT-08",
                  "RT-09", "RT-11"):
            self.assertEqual(cases[k]["expected"], "BLOCKED_UNKNOWN")
            self.assertIs(cases[k]["proofs_complete"], False)
        for k in ("RT-05", "RT-06"):
            self.assertEqual(cases[k]["expected"], "ELIGIBLE_FOR_LATER_POLICY_CHECK")
            self.assertIs(cases[k]["proofs_complete"], True)
        self.assertEqual(cases["RT-04"]["expected"], "BLOCKED_NOT_NEEDED")
        self.assertEqual(cases["RT-10"]["expected"], "BLOCKED_OTHER_STOP")
        self.assertEqual(cases["RT-12"]["expected"], "BLOCKED_NOT_NEEDED")

    def test_no_existing_stop_or_approval_is_weakened(self):
        flags = self.report["safety_status"]
        for key in ("implementation_approved", "human_safety_approval",
                    "owner_approved_for_safety", "forward_trading_enabled",
                    "live_orders_allowed"):
            self.assertIs(flags[key], False)
        self.assertEqual(flags["phase_1"], "BLOCKED")
        stops = load("specs/p0_01_stop_reason_clearance_matrix_draft.json")
        by_id = {r["id"]: r for r in stops["rows"]}
        self.assertEqual(by_id["ORDER_OUTCOME_UNKNOWN"]["automatic_clear"],
                         "NO_AUTOMATIC_RETRY")
        self.assertEqual(by_id["DD5_EMERGENCY_HALT"]["automatic_clear"],
                         "FORBIDDEN")
        self.assertIs(by_id["DD5_EMERGENCY_HALT"]["explicit_human_approval_required"], True)

    def test_requirement_and_phase_approval_still_blocked(self):
        registry = load("specs/reconciliation_registry.json")
        self.assertEqual(check_reconciliation(registry), [])
        for r in registry["items"]:
            self.assertIs(r["implementation_approved"], False)
            self.assertIsNone(r["owner_approval"])
        priority = load("specs/source_review_priority.json")
        for r in priority["items"]:
            self.assertEqual(r["source_review"], "PENDING_ORIGINAL")
            self.assertIs(r["human_safety_approval"], False)
        phases = load("specs/acceptance_registry.json")["phases"]
        self.assertEqual(next(p for p in phases if p["id"] == "PHASE-1")["status"],
                         "BLOCKED")


if __name__ == "__main__":
    unittest.main()
