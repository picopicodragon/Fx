"""P05-03 synthetic account-wide position/order reconciliation negative tests."""
from __future__ import annotations

import copy
import unittest

from scripts import risk_3p_36_synthetic_order_reconciliation as mod


class SyntheticReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = mod.make_fixture()

    def reject(self, mutation, expected):
        snapshot = copy.deepcopy(self.fixture)
        mutation(snapshot)
        result = mod.evaluate_synthetic_reconciliation(snapshot)
        self.assertEqual(result["status"], "FAIL_CLOSED", result)
        self.assertIn(expected, result["errors"], result)
        self.assertEqual(result["synthetic_scenario"], "UNVERIFIED")
        self.assertFalse(result["real_broker_state_reconciled"])
        self.assertFalse(result["real_positions_or_orders_absent_verified"])
        self.assertFalse(result["p05_03_accepted"])
        self.assertEqual(result["p05_passed_checks"], 0)
        self.assertFalse(result["real_mt4_session_authorized"])
        self.assertFalse(result["order_or_ea_change_authorized"])
        self.assertEqual(result["runtime_go_no_go"], "NO_GO")
        self.assertTrue(result["safety_hold_latched"])

    def test_matched_zero_is_only_fictional_and_never_authorizes_trade(self):
        result = mod.evaluate_synthetic_reconciliation(self.fixture)
        self.assertEqual(result["status"], "PASS_OFFLINE_SYNTHETIC_ONLY")
        self.assertEqual(result["synthetic_scenario"], "MATCHED_ZERO_SYNTHETIC_ONLY")
        self.assertEqual(result["errors"], [])
        self.assertFalse(result["real_positions_or_orders_absent_verified"])
        self.assertFalse(result["p05_03_accepted"])
        self.assertEqual(result["runtime_go_no_go"], "NO_GO")

    def test_matched_nonzero_other_symbols_is_not_ignored(self):
        result = mod.evaluate_synthetic_reconciliation(
            mod.make_fixture(exposure=True))
        self.assertEqual(result["status"], "PASS_OFFLINE_SYNTHETIC_ONLY")
        self.assertEqual(result["synthetic_scenario"],
                         "MATCHED_EXPOSURE_SYNTHETIC_ONLY")
        self.assertFalse(result["real_broker_state_reconciled"])
        self.assertEqual(result["runtime_go_no_go"], "NO_GO")

    def test_terminal_balance_only_cannot_be_treated_as_zero_count(self):
        self.reject(lambda p: p["terminal"].update(
            coverage="SIM_BALANCE_ONLY_NO_ROWS_VISIBLE"),
            "P36_SOURCE_UNVERIFIED_OR_PARTIAL")
        self.reject(lambda p: p["terminal"].update(
            count_status="UNKNOWN_FROM_BALANCE_ONLY"),
            "P36_SOURCE_UNVERIFIED_OR_PARTIAL")
        self.reject(lambda p: p["terminal"]["rows"][0].update(
            open_positions=None), "P36_UNKNOWN_OR_INVALID_COUNT:1")

    def test_broker_source_required_and_no_ui_only_clearance(self):
        self.reject(lambda p: p.update(server=None),
                    "P36_INCOMPLETE_OR_EXTRA_SOURCE_FIELDS")
        self.reject(lambda p: p["server"].update(
            coverage="SIM_ONLY_ONE_SYMBOL"),
            "P36_SOURCE_UNVERIFIED_OR_PARTIAL")
        self.reject(lambda p: p["server"].update(
            connection="SIM_DISCONNECTED"),
            "P36_SOURCE_UNVERIFIED_OR_PARTIAL")
        self.reject(lambda p: p["server"].update(
            source_kind="SIM_TERMINAL_UI"),
            "P36_SOURCE_UNVERIFIED_OR_PARTIAL")

    def test_position_or_pending_mismatch_is_fail_closed(self):
        self.reject(lambda p: p["server"]["rows"][0].update(
            open_positions=2), "P36_POSITION_OR_PENDING_MISMATCH:1")
        self.reject(lambda p: p["terminal"]["rows"][1].update(
            pending_orders=1), "P36_POSITION_OR_PENDING_MISMATCH:2")
        self.reject(lambda p: p["server"]["rows"][3].update(
            pending_orders=5), "P36_POSITION_OR_PENDING_MISMATCH:4")

    def test_other_symbols_and_missing_categories_cannot_be_dropped(self):
        self.reject(lambda p: p["terminal"]["rows"].pop(),
                    "P36_ACCOUNT_WIDE_COVERAGE_MISSING")
        self.reject(lambda p: p["server"]["rows"][3].update(
            category="GBP/USD"), "P36_UNKNOWN_OR_INVALID_COUNT:4")
        self.reject(lambda p: p["server"]["rows"][0].update(
            category="EUR/USD"), "P36_UNKNOWN_OR_INVALID_COUNT:1")
        self.reject(lambda p: p["terminal"]["rows"].reverse(),
                    "P36_UNKNOWN_OR_INVALID_COUNT:1")

    def test_bool_negative_float_or_oversize_counts_cannot_pass(self):
        for invalid in (True, False, -1, 0.0, "0", 100001, None, [], {}):
            with self.subTest(invalid=str(invalid)):
                self.reject(lambda p, value=invalid: p["server"]
                            ["rows"][2].update(open_positions=value),
                            "P36_UNKNOWN_OR_INVALID_COUNT:3")

    def test_cross_account_session_and_origin_must_match_fictional_contract(self):
        for section in ("terminal", "server"):
            with self.subTest(section=section):
                self.reject(lambda p, s=section: p[s].update(
                    account_alias="SIM_OTHER_DEMO_ACCOUNT"),
                    "P36_SOURCE_UNVERIFIED_OR_PARTIAL")
                self.reject(lambda p, s=section: p[s].update(
                    session_alias="SIM_SECOND_TERMINAL"),
                    "P36_SOURCE_UNVERIFIED_OR_PARTIAL")
        self.reject(lambda p: p["terminal"].update(
            source_token="SIM_SERVER_ORIGIN"),
            "P36_SOURCE_UNVERIFIED_OR_PARTIAL")

    def test_fake_utc_is_required_and_simulated_skew_is_detected(self):
        self.reject(lambda p: p["server"].update(
            asof_utc="2026-11-06T00:00:00Z"),
            "P36_INVALID_SIMULATED_UTC")
        self.reject(lambda p: p["server"].update(
            asof_utc="SIM_2000-02-30T00:00:00Z"),
            "P36_INVALID_SIMULATED_UTC")
        self.reject(lambda p: p["server"].update(
            asof_utc="SIM_2000-01-01T00:00:31Z"),
            "P36_SIMULATED_SOURCE_TIME_SKEW")
        equal = copy.deepcopy(self.fixture)
        equal["server"]["asof_utc"] = "SIM_2000-01-01T00:00:30Z"
        result = mod.evaluate_synthetic_reconciliation(equal)
        self.assertEqual(result["status"], "PASS_OFFLINE_SYNTHETIC_ONLY")
        self.assertEqual(result["runtime_go_no_go"], "NO_GO")

    def test_operator_permission_and_real_source_injection_are_blocked(self):
        for name, value in (
            ("p05_passed_checks", 1), ("p05_03_accepted", True),
            ("runtime_go_no_go", "GO"),
            ("safety_hold_latched", False),
            ("real_broker_reconciled", True),
            ("real_mt4_access_authorized", True),
            ("order_action_authorized", True)):
            with self.subTest(name=name):
                self.reject(lambda p, k=name, v=value:
                            p["safety"].update({k: v}),
                            "P36_TRADING_OR_OBSERVATION_AUTHORIZATION_FORGED")
        self.reject(lambda p: p.update(
            classification="REAL_BROKER_EVIDENCE"),
            "P36_UNSAFE_SCOPE_OR_OWNER_UI_INFERENCE")
        self.reject(lambda p: p.update(
            owner_ui_observation="NO_ROWS_MEANS_ZERO"),
            "P36_UNSAFE_SCOPE_OR_OWNER_UI_INFERENCE")

    def test_private_account_identifiers_and_unknown_fields_fail_closed(self):
        self.reject(lambda p: p.update(
            account_number="PRIVATE_ACCOUNT"),
            "P36_PACKAGE_SCHEMA_OR_SENSITIVE_DATA_FIELD")
        self.reject(lambda p: p["server"].update(
            screenshot_bytes="PRIVATE"),
            "P36_INCOMPLETE_OR_EXTRA_SOURCE_FIELDS")
        self.reject(lambda p: p["terminal"]["rows"][0].update(
            ticket_id="PRIVATE_ORDER"),
            "P36_UNKNOWN_OR_INVALID_COUNT:1")
        result = mod.evaluate_synthetic_reconciliation({
            "private_account": "SHOULD_NOT_RETURN_IN_ERRORS"})
        self.assertEqual(result["status"], "FAIL_CLOSED")
        self.assertNotIn("SHOULD_NOT_RETURN_IN_ERRORS", str(result))

    def test_broker_other_symbol_exposure_cannot_be_inferred_from_empty_ui(self):
        # The owner's trade tab only showed balance; even a fictional
        # server-only position on an unselected pair must block zero claims.
        self.reject(lambda p: p["server"]["rows"][3].update(
            open_positions=1, pending_orders=2),
            "P36_POSITION_OR_PENDING_MISMATCH:4")
        self.reject(lambda p: p["terminal"].update(
            coverage="SIM_BALANCE_ONLY_NO_POSITION_ROWS"),
            "P36_SOURCE_UNVERIFIED_OR_PARTIAL")

    def test_malformed_data_fails_closed_without_network_or_mt4(self):
        for item in (None, [], "", 1, True, {}, {"terminal": {}}):
            with self.subTest(item=type(item).__name__):
                r = mod.evaluate_synthetic_reconciliation(item)
                self.assertEqual(r["status"], "FAIL_CLOSED")
                self.assertEqual(r["runtime_go_no_go"], "NO_GO")
                self.assertFalse(r["real_broker_state_reconciled"])
