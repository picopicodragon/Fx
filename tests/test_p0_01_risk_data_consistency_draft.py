"""P0-01 risk data consistency is an unapproved design audit, not a risk calculator."""
import json
import unittest
from pathlib import Path

from scripts.check_reconciliation import check_reconciliation

ROOT = Path(__file__).resolve().parents[1]
DRAFT = "specs/p0_01_risk_data_consistency_draft.json"


def load(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


class RiskDataConsistencyDraftTests(unittest.TestCase):
    def setUp(self):
        self.d = load(DRAFT)

    def test_nine_data_domains_and_source_provenance(self):
        self.assertEqual(self.d["status"],
                         "DRAFT_ONLY_NO_APPROVED_FORMULAS_OR_LIVE_DATA_INTERFACE")
        domains = self.d["snapshot_domains"]
        self.assertEqual(len(domains), 9)
        self.assertEqual({x["id"] for x in domains},
                         {f"DS-{i:02d}" for i in range(1, 10)})
        for item in domains:
            self.assertTrue(item["critical_for"])
            self.assertTrue(item["required_evidence"])
            self.assertTrue(item["not_finalized"])
        for src in self.d["source_refs"]:
            self.assertTrue((ROOT / src).is_file(), src)

    def test_adopted_risk_percentage_limits_unchanged(self):
        policy = self.d["adopted_policy"]
        self.assertEqual(policy["preorder_individual_max_estimated_loss_pct_of_current_equity"], "0.5")
        self.assertEqual(policy["preorder_combined_max_estimated_loss_pct_of_current_equity"], "1.0")
        self.assertEqual(policy["daily_loss_limit_pct_of_fixed_opening_equity"], "1.5")
        self.assertEqual(policy["drawdown_levels_pct"], ["2", "3", "4", "5"])
        self.assertEqual(len(policy["preorder_includes"]), 3)
        self.assertEqual(policy["dd4_dd5_order_stop_clearing"],
                         "explicit human approval required; numeric improvement alone is insufficient")
        self.assertIn("America/New_York", policy["daily_limit_reset"])

    def test_three_distinct_denominators_and_cashflow_roles(self):
        policy = self.d["adopted_policy"]
        self.assertIn("Current equity", self.d["boundaries"][0]["fact"])
        self.assertIn("opening EQUITY", self.d["boundaries"][1]["fact"])
        boundary = {x["id"]: x["fact"] for x in self.d["boundaries"]}
        self.assertIn("NOT the daily fixed opening equity", boundary["BD-01"])
        self.assertIn("remains fixed", boundary["BD-02"])
        self.assertIn("virtual-unit DD", boundary["BD-03"])
        self.assertIn("15 seconds", boundary["BD-04"])
        self.assertIn("Q128", boundary["BD-04"])
        self.assertIn("not a guarantee", boundary["BD-07"])

    def test_order_inflight_and_independent_stops_remain_explicit(self):
        domains = {x["id"]: x for x in self.d["snapshot_domains"]}
        self.assertIn("dispatch/in-flight", " ".join(domains["DS-03"]["required_evidence"]))
        self.assertIn("stop-reason latches", " ".join(domains["DS-09"]["required_evidence"]))
        self.assertIn("Q120", self.d["boundaries"][4]["fact"])
        self.assertIn("DD4/5", self.d["boundaries"][5]["fact"])
        self.assertIn("Q121", self.d["adopted_policy"]["stop_reasons"])

    def test_sixteen_offline_cases_never_approve_order(self):
        cases = self.d["synthetic_cases"]
        self.assertEqual({c["id"] for c in cases},
                         {f"DC-{i:02d}" for i in range(1, 17)})
        self.assertEqual(len(cases), 16)
        outcomes = {v["id"] for v in self.d["review_outcomes"]}
        self.assertEqual(outcomes, {
            "REJECT_NEW_ORDER", "HOLD_DATA_RECONCILIATION",
            "MAINTAIN_INDEPENDENT_STOP", "READY_FOR_FUTURE_FORMULA_REVIEW",
        })
        domains = {v["id"] for v in self.d["snapshot_domains"]}
        for c in cases:
            self.assertIs(c["new_order_permitted"], False)
            self.assertIn(c["expected"], outcomes)
            self.assertTrue(set(c["affected"]) <= domains)
        cases_by_id = {c["id"]: c for c in cases}
        self.assertEqual(cases_by_id["DC-15"]["expected"],
                         "READY_FOR_FUTURE_FORMULA_REVIEW")
        self.assertEqual(cases_by_id["DC-14"]["expected"],
                         "MAINTAIN_INDEPENDENT_STOP")
        self.assertEqual(cases_by_id["DC-07"]["expected"],
                         "HOLD_DATA_RECONCILIATION")

    def test_no_new_numerical_defaults_or_implementation_signoff(self):
        self.assertGreaterEqual(len(self.d["unresolved_before_implementation"]), 8)
        self.assertIn("No new formulas", " ".join(self.d["not_claimed"]))
        state = self.d["safety_status"]
        for key in ("implementation_approved", "human_safety_approval",
                    "owner_approved_for_safety", "forward_trading_enabled",
                    "live_orders_allowed"):
            self.assertIs(state[key], False)
        self.assertEqual(state["phase_1"], "BLOCKED")
        doc = (ROOT / "docs/p0_01_risk_data_consistency_review_20261023.md").read_text(encoding="utf-8")
        self.assertIn("Q128", doc)
        self.assertIn("15秒", doc)
        self.assertIn("DC-16", doc)

    def test_earlier_drafts_and_requirement_latches_still_unchanged(self):
        crosswalk = load("specs/p0_01_safety_consistency_crosswalk.json")
        self.assertEqual(len(crosswalk["crosswalk"]), 6)
        stop = load("specs/p0_01_stop_reason_clearance_matrix_draft.json")
        dd5 = next(x for x in stop["rows"] if x["id"] == "DD5_EMERGENCY_HALT")
        self.assertEqual(dd5["automatic_clear"], "FORBIDDEN")
        retry = load("specs/p0_01_closeout_retry_evidence_matrix_draft.json")
        self.assertTrue(all(x["automatic_retry_allowed"] is False
                            for x in retry["synthetic_cases"]))
        registry = load("specs/reconciliation_registry.json")
        self.assertEqual(check_reconciliation(registry), [])
        self.assertTrue(all(not x["implementation_approved"]
                            and x["owner_approval"] is None
                            for x in registry["items"]))

    def test_phase1_and_owner_review_are_still_blocked(self):
        prio = load("specs/source_review_priority.json")
        self.assertTrue(all(x["source_review"] == "PENDING_ORIGINAL"
                            and x["human_safety_approval"] is False
                            for x in prio["items"]))
        acceptance = load("specs/acceptance_registry.json")
        phase = next(x for x in acceptance["phases"] if x["id"] == "PHASE-1")
        self.assertEqual(phase["status"], "BLOCKED")
        self.assertIsNone(phase["approval"])


if __name__ == "__main__":
    unittest.main()
