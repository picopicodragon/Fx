"""Offline P05-03 policy cross-check; protects unsigned P05 and real G1."""
from __future__ import annotations

import copy
import unittest

from scripts import audit_risk_3p_37_p05_03_reconciliation_readiness as mod


class P0503OfflineBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.docs = {name: mod._read(mod.ROOT, name) for name in mod.PATHS}

    def reject(self, file, mutate, error_code):
        docs = copy.deepcopy(self.docs)
        mutate(docs[file])
        errors = mod.audit(injected=docs)
        self.assertIn(error_code, errors, errors)
        state = mod.snapshot(injected=docs)
        self.assertEqual(state["status"], "FAIL_CLOSED")
        self.assertFalse(state["p05_03_real_server_reconciled"])
        self.assertEqual(state["p05_passed"], 0)
        self.assertEqual(state["real_g1_fields_verified"], 0)
        self.assertEqual(state["runtime_go_no_go"], "NO_GO")
        self.assertTrue(state["safety_hold_latched"])

    def test_baseline_reported_balance_only_cannot_be_cleared(self):
        self.assertEqual(mod.audit(), [])
        state = mod.snapshot()
        self.assertEqual(state["status"], "PASS_OFFLINE_POLICY_ONLY")
        self.assertTrue(state["p05_03_observed_balance_only"])
        self.assertFalse(state["p05_03_real_server_reconciled"])
        self.assertFalse(state["real_mt4_read_authorized"])
        self.assertFalse(state["order_authorized"])
        self.assertFalse(state["human_p05_signoff"])

    def test_broker_source_or_ui_assumptions_must_not_be_weakened(self):
        for key in (
            "observed_zero_is_not_verified_zero",
            "unknown_counts_must_not_be_normalized_to_zero",
            "broker_side_must_be_independent_and_account_wide",
            "no_live_session_or_order_manipulation",
        ):
            with self.subTest(key=key):
                self.reject(mod.POLICY,
                            lambda d, k=key: d.update({k: False}),
                            "P37_RECONCILIATION_POLICY_DRIFT")
        self.reject(mod.POLICY,
                    lambda d: d.update(
                        observed_owner_ui="BALANCE_ONLY_EQUALS_ZERO"),
                    "P37_RECONCILIATION_POLICY_DRIFT")

    def test_policy_guards_cannot_enable_real_mt4_or_orders(self):
        for field, value in (
            ("p05_03_accepted", True),
            ("p05_checks_passed", 8),
            ("real_mt4_access_authorized", True),
            ("order_execution_authorized", True),
            ("auto_trading_change_authorized", True),
            ("real_order_positions_verified", True),
            ("uploaded_private_broker_log", True),
            ("runtime_go_no_go", "GO"),
            ("safety_hold_latched", False),
        ):
            with self.subTest(field=field):
                self.reject(mod.POLICY,
                            lambda d, k=field, v=value:
                            d["environment"].update({k: v}),
                            "P37_REAL_ACCOUNT_OR_TRADE_PERMISSION_PROMOTED")

    def test_p05_owner_ui_not_server_reconciliation(self):
        self.reject(mod.P05,
                    lambda d: d["p05_checks"][2].update(
                        p05_accepted=True),
                    "P37_TRADE_TAB_UI_MISTAKEN_FOR_SERVER_PROOF")
        self.reject(mod.P05,
                    lambda d: d["p05_checks"][2].update(
                        current_status="SERVER_VERIFIED_ZERO"),
                    "P37_TRADE_TAB_UI_MISTAKEN_FOR_SERVER_PROOF")
        self.reject(mod.P05,
                    lambda d: d["p05_checks"][2]
                    ["owner_reported_ui_observation"].update(
                        server_order_state_reconciled=True),
                    "P37_TRADE_TAB_UI_MISTAKEN_FOR_SERVER_PROOF")
        self.reject(mod.P05,
                    lambda d: d.update(
                        p06_observation_authorized=True),
                    "P37_P05_STILL_REQUIRES_REAL_SAFETY_REVIEW")

    def test_human_review_packet_remains_unsigned(self):
        self.reject(mod.REVIEW,
                    lambda d: d["items"][2].update(item_accepted=True),
                    "P37_P05_03_HUMAN_SIGNOFF_NOT_GRANTED")
        self.reject(mod.REVIEW,
                    lambda d: d["items"][2].update(
                        independent_environment_evidence="VERIFIED"),
                    "P37_P05_03_HUMAN_SIGNOFF_NOT_GRANTED")
        self.reject(mod.REVIEW,
                    lambda d: d["items"][2].update(
                        human_specific_acceptance="SIGNED"),
                    "P37_P05_03_HUMAN_SIGNOFF_NOT_GRANTED")
        self.reject(mod.REVIEW,
                    lambda d: d["safety"].update(p06_authorized=True),
                    "P37_UNSIGNED_HUMAN_REVIEW_REQUIRED")

    def test_g1_contract_values_still_null(self):
        self.reject(mod.G1,
                    lambda d: d["g1_entries"][0].update(
                        value="0.01"),
                    "P37_G1_REAL_VALUE_INJECTED")
        self.reject(mod.G1,
                    lambda d: d["g1_entries"][14].update(
                        status="INDEPENDENTLY_VERIFIED"),
                    "P37_G1_REAL_VALUE_INJECTED")
        self.reject(mod.G1,
                    lambda d: d.update(required_items=20),
                    "P37_REAL_BROKER_G1_ZERO_PROOF_REQUIRED")
        self.reject(mod.G1,
                    lambda d: d["safety"].update(
                        independently_verified_g1_items=15),
                    "P37_REAL_BROKER_G1_ZERO_PROOF_REQUIRED")

    def test_malformed_or_private_data_never_exposed(self):
        self.reject(mod.POLICY,
                    lambda d: d.update(
                        account_password="SECRET"),
                    "P37_RECONCILIATION_POLICY_DRIFT")
        self.reject(mod.POLICY,
                    lambda d: d["future_real_evidence_requirements"].pop(),
                    "P37_RECONCILIATION_POLICY_DRIFT")
        copydocs = copy.deepcopy(self.docs)
        copydocs[mod.POLICY] = {"password": "SECRET_SHOULD_NOT_LEAK"}
        result = mod.audit(injected=copydocs)
        self.assertNotIn("SECRET_SHOULD_NOT_LEAK", str(result))
        self.assertEqual(mod.snapshot(injected=copydocs)["status"], "FAIL_CLOSED")

    def test_missing_or_bad_source_fails_closed(self):
        copydocs = copy.deepcopy(self.docs)
        copydocs.pop(mod.P05)
        self.assertIn("P37_MISSING_OR_MALFORMED_OFFLINE_INPUT",
                      mod.audit(injected=copydocs))
        copydocs = copy.deepcopy(self.docs)
        copydocs[mod.REVIEW] = []
        self.assertEqual(mod.audit(injected=copydocs),
                         ["P37_DOCUMENT_MALFORMED"])


if __name__ == "__main__":
    unittest.main()
