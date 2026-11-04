"""RISK-3P-18/19 G1 pre-observation guards, all synthetic mutations."""
from __future__ import annotations

import copy
import unittest

from scripts import audit_risk_3p_18_19_g1_readonly_protocol as audit


class ReadonlyG1ProtocolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        keys = (audit.PLAN, audit.PREVIOUS, audit.GATES, audit.FORM01, audit.V3)
        cls.documents = {key: audit._read(audit.ROOT, key) for key in keys}

    def assert_refused(self, path, mutate, message):
        d = copy.deepcopy(self.documents)
        mutate(d[path])
        errors = audit.audit(injected=d)
        self.assertIn(message, errors, errors)

    def test_15_field_evidence_plan_and_unopened_mt4_actions(self):
        self.assertEqual(audit.audit(), [])
        plan = self.documents[audit.PLAN]
        self.assertEqual(len(plan["proposed_observations"]), 15)
        self.assertEqual(len(plan["field_methodology"]), 5)
        self.assertEqual(len(plan["preflight_checks"]), 7)
        self.assertEqual(len(plan["environment_readonly_steps"]), 6)
        self.assertTrue(all(x["status"] == "NOT_OBSERVED"
                            and x["verified_value"] is None
                            and x["real_world_verified"] is False
                            for x in plan["proposed_observations"]))
        self.assertEqual(plan["phase_1"], "BLOCKED")
        self.assertEqual(plan["runtime_go_no_go"], "NO_GO")
        self.assertIs(plan["safety_hold_latched"], True)

    def test_false_owner_live_or_g1_authorizations_are_rejected(self):
        for k in ("evidence_collected", "owner_approved_real_read",
                  "g1_3x5_scope_approved", "g1_real_world_verified",
                  "fx_saf_implementation_approved", "production_authorized",
                  "order_allowed", "stop_release_allowed", "auto_merge_authorized"):
            with self.subTest(flag=k):
                self.assert_refused(
                    audit.PLAN, lambda p, key=k: p.update({key: True}),
                    "FALSE_AUTHORIZATION:" + k)

    def test_evidence_value_timestamp_unit_source_and_identity_must_be_unknown(self):
        for key, value in (
            ("verified_value", "0.01"),
            ("unit_provenance", "JPY"),
            ("terminal_symbol", "EURUSD"),
            ("account_environment_alias", "demo_private"),
            ("observation_at_utc", "2026-11-04T03:01:00Z"),
            ("broker_source_reference", "fake"),
            ("independent_source_reference", "fake"),
            ("status", "VERIFIED"),
            ("independent_crosscheck", "PASS"),
            ("real_world_verified", True),
        ):
            with self.subTest(field=key):
                self.assert_refused(
                    audit.PLAN, lambda d, k=key, v=value:
                    d["proposed_observations"][14].update({k: v}),
                    "FALSELY_VERIFIED_CONTRACT_FIELD:EUR/USD:tick_value_deposit_currency")

    def test_missing_pair_duplicate_attribute_and_order_swap_are_rejected(self):
        self.assert_refused(
            audit.PLAN, lambda d: d["proposed_observations"].pop(),
            "MISSING_OR_RELABELED_OBSERVATIONS")
        self.assert_refused(
            audit.PLAN, lambda d: d["proposed_observations"][14].update(
                field="min_lot"), "MISSING_OR_RELABELED_OBSERVATIONS")
        self.assert_refused(
            audit.PLAN, lambda d: d["target_pairs"].pop(),
            "PAIR_SCOPE_OR_G1_HISTORY_DRIFT")
        self.assert_refused(
            audit.PLAN, lambda d: d.update(expected_g1_items=20),
            "PAIR_SCOPE_OR_G1_HISTORY_DRIFT")

    def test_field_source_visibility_and_independence_cannot_be_forged(self):
        for k, value in (
            ("ui_field_presence", "CONFIRMED_DISPLAYED"),
            ("independent_source_available", True),
            ("assumption_is_broker_verified", True),
            ("cannot_use_digits_or_pip_proxy_without_unit_proof", False),
        ):
            with self.subTest(field=k):
                self.assert_refused(
                    audit.PLAN, lambda d, key=k, v=value:
                    d["field_methodology"][4].update({key: v}),
                    "FALSE_FIELD_SOURCE_ASSURANCE:tick_value_deposit_currency")

    def test_five_required_methods_and_evidence_requirements_not_omitted(self):
        self.assert_refused(
            audit.PLAN, lambda d: d["field_methodology"].pop(),
            "FIVE_CONTRACT_METHODS_INCOMPLETE")
        self.assert_refused(
            audit.PLAN, lambda d: d["evidence_required_for_each_field"].pop(),
            "EVIDENCE_PROVENANCE_REQUIREMENTS_DROPPED")

    def test_abort_controls_cannot_ignore_existing_ea_and_orders(self):
        self.assert_refused(
            audit.PLAN, lambda d: d["preflight_checks"].pop(),
            "PREOBSERVATION_ABORT_LIST_INCOMPLETE")
        self.assert_refused(
            audit.PLAN, lambda d: d["preflight_checks"][0].update(
                if_unverified="CONTINUE"),
            "ABORT_GUARD_WEAKENED:P18-01")

    def test_future_steps_all_require_separate_authorization(self):
        self.assert_refused(
            audit.PLAN, lambda d: d["environment_readonly_steps"][2].update(
                status="AUTHORIZED"),
            "UNAUTHORIZED_TERMINAL_STEP:OBS-03")
        self.assert_refused(
            audit.PLAN, lambda d: d["environment_readonly_steps"].pop(),
            "FUTURE_MANUAL_STEP_SET_INCOMPLETE")

    def test_no_creds_upload_trade_or_unsafe_merge_authority(self):
        self.assert_refused(
            audit.PLAN, lambda d: d["forbidden_actions_now"].remove("SEND_ORDER"),
            "UNAUTHORIZED_OPERATION_OR_MERGE")
        self.assert_refused(
            audit.PLAN, lambda d: d["allowed_actions_now"].append("MT4_LOGIN"),
            "UNAUTHORIZED_OPERATION_OR_MERGE")
        self.assert_refused(
            audit.PLAN, lambda d: d.update(human_manual_merge_required=False),
            "UNAUTHORIZED_OPERATION_OR_MERGE")

    def test_any_source_g1_or_new_v3_promotion_is_denied(self):
        self.assert_refused(
            audit.GATES, lambda d: d["gaps"][0].update(
                real_world_verified=True),
            "FORMAL_G1_OR_MT4_ACCESS_FALSIFIED")
        self.assert_refused(
            audit.GATES, lambda d: d.update(real_mt4_access_approved=True),
            "FORMAL_G1_OR_MT4_ACCESS_FALSIFIED")
        self.assert_refused(
            audit.FORM01, lambda d: d.update(form01_implementation_approved=True),
            "FORM01_UNRESOLVED_NOT_PRESERVED")
        self.assert_refused(
            audit.V3, lambda d: d["symbols"][2]["properties"].update(
                min_lot="0.01"), "V3_CONTRACT_TEMPLATE_PREMATURELY_FILLED")
        self.assert_refused(
            audit.PREVIOUS, lambda d: d.update(g1_scope_revision_approved=True),
            "UPSTREAM_G1_PREFLIGHT_PROMOTED")

    def test_stop_gate_never_go_after_pass_or_bad_mutation(self):
        self.assert_refused(
            audit.PLAN, lambda d: d.update(runtime_go_no_go="GO"),
            "STOP_LATCH_OR_PHASE_PROMOTED")
        self.assert_refused(
            audit.PLAN, lambda d: d.update(safety_hold_latched=False),
            "STOP_LATCH_OR_PHASE_PROMOTED")
        self.assert_refused(
            audit.PLAN, lambda d: d.update(verified_values={"fake": "true"}),
            "STOP_LATCH_OR_PHASE_PROMOTED")

    def test_malformed_and_unknown_formats_fail_closed(self):
        packet = copy.deepcopy(self.documents)
        packet[audit.PLAN] = None
        self.assertEqual(audit.audit(injected=packet), ["PLAN_NOT_A_DOCUMENT"])
        self.assert_refused(
            audit.PLAN, lambda d: d.update(scope="BROKER_CONNECTION_APPROVED"),
            "DOCUMENT_IDENTITY_OR_SCOPE_CHANGED")


if __name__ == "__main__":
    unittest.main()
