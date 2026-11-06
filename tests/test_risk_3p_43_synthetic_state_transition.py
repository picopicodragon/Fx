"""Order-state history and anti-replay tests, all data deliberately fictitious."""
from __future__ import annotations

import copy
import unittest

from scripts import risk_3p_43_synthetic_state_transition as mod


class SyntheticHistoryTests(unittest.TestCase):
    def assert_stop(self, result, expected=None):
        self.assertEqual(result["status"], "FAIL_CLOSED", result)
        if expected:
            self.assertIn(expected, result["errors"], result)
        self.assertFalse(result["real_order_absence_verified"])
        self.assertFalse(result["real_close_event_verified"])
        self.assertFalse(result["real_broker_order_state_reconciled"])
        self.assertFalse(result["real_mt4_access_authorized"])
        self.assertFalse(result["trading_or_ea_action_authorized"])
        self.assertFalse(result["p05_03_accepted"])
        self.assertEqual(result["p05_passed"], 0)
        self.assertEqual(result["runtime_go_no_go"], "NO_GO")
        self.assertTrue(result["safety_hold_latched"])

    def test_unchanged_synthetic_zero_never_means_live_flat(self):
        result = mod.evaluate(mod.fixture())
        self.assertEqual(result["status"], "PASS_SYNTHETIC_TIMELINE_ONLY")
        self.assertEqual(result["synthetic_scenario"],
                         "SIMULATED_NO_CHANGE_NOT_BROKER_PROOF")
        self.assertFalse(result["real_order_absence_verified"])
        self.assertEqual(result["runtime_go_no_go"], "NO_GO")

    def test_fictional_close_is_not_a_broker_close(self):
        result = mod.evaluate(mod.fixture(closing=True))
        self.assertEqual(result["status"], "PASS_SYNTHETIC_TIMELINE_ONLY")
        self.assertEqual(result["synthetic_scenario"],
                         "SIMULATED_CLOSE_NOT_BROKER_PROOF")
        self.assertFalse(result["real_close_event_verified"])
        self.assertFalse(result["p05_03_accepted"])

    def test_missing_close_token_blocks_disappearing_exposure(self):
        x = mod.fixture(closing=True)
        x["after"]["synthetic_transition_token"] = mod.NO_EVENT
        self.assert_stop(mod.evaluate(x), "P43_MISSING_SYNTHETIC_CLOSE_TOKEN")

    def test_unexplained_new_exposure_blocks_state(self):
        x = mod.fixture()
        for source in ("terminal", "server"):
            x["after"]["synthetic_snapshot"][source]["rows"][3][
                "open_positions"] = 2
        self.assert_stop(mod.evaluate(x), "P43_UNEXPLAINED_NEW_EXPOSURE")

    def test_fake_close_with_no_count_change_blocks(self):
        x = mod.fixture()
        x["after"]["synthetic_transition_token"] = mod.CLOSE_EVENT
        self.assert_stop(mod.evaluate(x),
                         "P43_FAKE_CLOSE_WITHOUT_COUNT_CHANGE")

    def test_replay_sequence_rollbacks_and_boolean_are_rejected(self):
        for value in (1, 0, -1, True, "2", None, 3):
            with self.subTest(value=value):
                x = mod.fixture()
                x["after"]["sequence"] = value
                self.assert_stop(mod.evaluate(x),
                                 "P43_REPLAY_OR_OUT_OF_ORDER:after")

    def test_replayed_or_reversed_fake_utc_rejected(self):
        for stamp in ("SIM_2000-01-01T00:00:00Z",
                      "SIM_1999-12-31T23:59:59Z"):
            with self.subTest(stamp=stamp):
                x = mod.fixture()
                for source in ("terminal", "server"):
                    x["after"]["synthetic_snapshot"][source][
                        "asof_utc"] = stamp
                self.assert_stop(mod.evaluate(x),
                                 "P43_REPLAYED_OR_ROLLBACK_FAKE_TIMESTAMP")

    def test_fake_cross_source_utc_mismatch_blocks(self):
        x = mod.fixture()
        x["after"]["synthetic_snapshot"]["server"][
            "asof_utc"] = "SIM_2000-01-01T00:00:45Z"
        self.assert_stop(mod.evaluate(x),
                         "P43_UNVERIFIED_SNAPSHOT:after")

    def test_partial_source_and_other_symbol_pending_mismatch_blocks(self):
        x = mod.fixture()
        x["after"]["synthetic_snapshot"]["server"]["rows"][3][
            "pending_orders"] = 1
        self.assert_stop(mod.evaluate(x),
                         "P43_UNVERIFIED_SNAPSHOT:after")
        x = mod.fixture()
        x["after"]["synthetic_snapshot"]["server"] = None
        self.assert_stop(mod.evaluate(x),
                         "P43_UNVERIFIED_SNAPSHOT:after")

    def test_real_scope_or_permissions_never_injected(self):
        x = mod.fixture()
        x["classification"] = "ACTUAL_ACCOUNT_RECONCILIATION"
        self.assert_stop(mod.evaluate(x),
                         "P43_FAKE_SCOPE_PROMOTED_TO_BROKER")
        for key, value in (
            ("real_close_event_verified", True),
            ("p05_passed", 8),
            ("runtime_go_no_go", "GO"),
            ("safety_hold_latched", False),
            ("real_mt4_read_authorized", True)):
            with self.subTest(key=key):
                x = mod.fixture()
                x["safety"][key] = value
                self.assert_stop(mod.evaluate(x),
                                 "P43_RUNTIME_OR_RECONCILIATION_PERMISSION_FORGED")

    def test_untrusted_nested_values_and_unknown_fields_fail_closed(self):
        for bad in (None, "", {}, [], 3, True, {"secret": "CANARY_VALUE_43"}):
            result = mod.evaluate(bad)
            self.assert_stop(result, "P43_MALFORMED_OR_SECRET_FIELDS")
            self.assertNotIn("CANARY_VALUE_43", str(result))
        x = mod.fixture()
        x["after"]["synthetic_snapshot"] = {"password": "CANARY_VALUE_43"}
        result = mod.evaluate(x)
        self.assert_stop(result)
        self.assertNotIn("CANARY_VALUE_43", str(result))
        x = mod.fixture()
        x["before"]["private_account_id"] = "CANARY_VALUE_43"
        self.assert_stop(mod.evaluate(x), "P43_INCOMPLETE_OR_EXTRA_STEP:before")

    def test_old_source_evidence_must_not_be_spoofed(self):
        x = mod.fixture(closing=True)
        x["before"]["synthetic_transition_token"] = mod.CLOSE_EVENT
        self.assert_stop(mod.evaluate(x), "P43_BASELINE_CANNOT_HAVE_TRANSITION")
        x = mod.fixture(closing=True)
        x["after"]["synthetic_transition_token"] = "REAL_BROKER_EVENT"
        self.assert_stop(mod.evaluate(x),
                         "P43_UNTRUSTED_FAKE_TRANSITION:after")


if __name__ == "__main__":
    unittest.main()
