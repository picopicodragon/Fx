"""FORM-02 owner-review scenario register: no false authorization."""
from __future__ import annotations

import copy
import json
import unittest

from scripts import audit_risk_3p_07_form02_draft as mod


class Form02DraftAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads((mod.ROOT / mod.DRAFT).read_text(encoding="utf-8"))

    def changed(self, edit, expected):
        d = copy.deepcopy(self.data)
        edit(d)
        self.assertIn(expected, mod.audit(mod.ROOT, d))

    def test_baseline_16_shapes_17_negative_cases_and_six_unapproved_decisions(self):
        self.assertEqual(mod.audit(), [])
        self.assertEqual(len(self.data["review_scenarios"]), 16)
        self.assertEqual(len(self.data["negative_scenarios"]), 17)
        self.assertEqual(len(self.data["owner_decisions"]), 6)
        self.assertEqual(self.data["phase_1"], "BLOCKED")
        self.assertEqual(self.data["runtime_go_no_go"], "NO_GO")
        self.assertIs(self.data["safety_hold_latched"], True)

    def test_target_pairs_kinds_and_stages_cannot_be_extended(self):
        self.changed(lambda d: d["target_pairs"].append("AUD/USD"),
                     "PAIR_OR_ORDER_SCOPE_DRIFT")
        self.changed(lambda d: d["order_kinds"].append("STOP_LIMIT"),
                     "PAIR_OR_ORDER_SCOPE_DRIFT")
        self.changed(lambda d: d["stages"].append("DISPATCHING"),
                     "PAIR_OR_ORDER_SCOPE_DRIFT")

    def test_simulated_shape_cannot_be_mislabelled_trading_authority(self):
        for key in ("owner_approval_recorded", "form02_implementation_approved",
                    "broker_stop_verified", "real_loss_bound_verified",
                    "real_world_evidence_verified", "production_authorized",
                    "mt4_execution_authorized", "order_allowed", "stop_release_allowed"):
            with self.subTest(key=key):
                self.changed(lambda d, k=key: d.update({k: True}),
                             "FALSE_APPROVAL:" + key)

    def test_stop_and_risk_hard_limits_cannot_change(self):
        for key, value in (("phase_1", "ACCEPTED"),
                           ("runtime_go_no_go", "GO"),
                           ("safety_hold_latched", False),
                           ("verified_values", {"fake": True}),
                           ("source_truth", "BROKER_VERIFIED")):
            with self.subTest(key=key):
                self.changed(lambda d, k=key, v=value: d.update({k: v}),
                             "FALSE_SOURCE_OR_STOP_STATUS")
        self.changed(lambda d: d["risk_limits_unchanged"].update(
            aggregate="0.02"), "HARD_LIMITS_DRIFT")

    def test_no_form_dependency_may_be_removed(self):
        self.changed(lambda d: d["related_unresolved"].remove("FORM-03"),
                     "UNRESOLVED_DEPENDENCY_DROPPED")
        self.changed(lambda d: d["related_unresolved"].remove("G1"),
                     "UNRESOLVED_DEPENDENCY_DROPPED")

    def test_scenario_coverage_cannot_drop_buy_sell_limit_stop(self):
        self.changed(lambda d: d["review_scenarios"].pop(),
                     "SCENARIO_SET_INCOMPLETE")
        self.changed(lambda d: d["review_scenarios"][0].update(
            order_kind="STOP_LIMIT"), "SCENARIO_FALSE_POSITIVE")
        self.changed(lambda d: d["review_scenarios"][0].update(
            live_risk_covered=True), "SCENARIO_FALSE_POSITIVE")

    def test_negative_scenarios_cannot_be_promoted_to_pass_or_deleted(self):
        self.changed(lambda d: d["negative_scenarios"].pop(),
                     "NEGATIVE_SCENARIO_COVERAGE_DRIFT")
        self.changed(lambda d: d["negative_scenarios"][0].update(
            expected="ALLOW"), "FALSE_NEGATIVE_SCENARIO_APPROVAL:SL_MISSING")
        self.changed(lambda d: d["negative_scenarios"][0].update(
            real_world_verified=True), "FALSE_NEGATIVE_SCENARIO_APPROVAL:SL_MISSING")

    def test_owner_decisions_are_not_preapproved(self):
        for i in range(6):
            with self.subTest(i=i):
                self.changed(lambda d, j=i: d["owner_decisions"][j].update(
                    owner_status="APPROVED", approval_reference="FAKE"),
                    "FALSE_OWNER_DECISION:F02-" + str(i + 1))
        self.changed(lambda d: d["owner_decisions"].pop(),
                     "OWNER_DECISION_SET_DRIFT")

    def test_malformed_register_refused(self):
        self.assertEqual(mod.audit(mod.ROOT, object()), ["INVALID_DRAFT"])
        self.changed(lambda d: d.update(scope="PRODUCTION"),
                     "DRAFT_IDENTITY_DRIFT")
        self.changed(lambda d: d["review_scenarios"].append([]),
                     "SCENARIO_SET_INCOMPLETE")


if __name__ == "__main__":
    unittest.main()
