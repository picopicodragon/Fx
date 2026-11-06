"""Synthetic safety stop-latch never releases real runtime regardless of event."""
from __future__ import annotations

import copy
import unittest

from scripts import risk_3p_44_synthetic_safety_latch as mod


class SyntheticLatchTests(unittest.TestCase):
    def reject(self, mutate, expected):
        fixture = mod.fixture()
        mutate(fixture)
        result = mod.evaluate(fixture)
        self.assertEqual(result["status"], "FAIL_CLOSED", result)
        self.assertIn(expected, result["errors"])
        self.assertFalse(result["real_stop_release_granted"])
        self.assertFalse(result["human_approval_recorded"])
        self.assertFalse(result["real_exit_or_order_action_performed"])
        self.assertEqual(result["runtime_go_no_go"], "NO_GO")
        self.assertTrue(result["safety_hold_latched"])

    def test_every_approved_fictional_event_keeps_live_hold(self):
        for event, label in mod.EVENTS.items():
            with self.subTest(event=event):
                result = mod.evaluate(mod.fixture(event))
                self.assertEqual(result["status"], "PASS_SYNTHETIC_LATCH_ONLY")
                self.assertEqual(result["simulated_state"], label)
                self.assertFalse(result["real_stop_release_granted"])
                self.assertFalse(result["real_exit_or_order_action_performed"])
                self.assertEqual(result["p05_passed"], 0)
                self.assertEqual(result["runtime_go_no_go"], "NO_GO")

    def test_operator_approval_claim_cannot_release_stop(self):
        result = mod.evaluate(mod.fixture("SIM_OPERATOR_APPROVAL_CLAIM"))
        self.assertEqual(result["status"], "PASS_SYNTHETIC_LATCH_ONLY")
        self.assertEqual(result["simulated_state"], "SIM_APPROVAL_UNTRUSTED")
        self.assertFalse(result["human_approval_recorded"])
        self.assertFalse(result["real_stop_release_granted"])

    def test_restart_and_monotonic_clock_rollback_never_auto_resume(self):
        for event in ("SIM_PROCESS_RESTART", "SIM_MONOTONIC_CLOCK_ROLLBACK"):
            with self.subTest(event=event):
                result = mod.evaluate(mod.fixture(event))
                self.assertEqual(result["simulated_state"],
                                 "SIM_CLOCK_CONTINUITY_UNKNOWN")
                self.assertTrue(result["safety_hold_latched"])

    def test_drawdown_levels_do_not_perform_real_closes_or_new_orders(self):
        for event in ("SIM_DRAWDOWN_2_PCT", "SIM_DRAWDOWN_3_PCT",
                      "SIM_DRAWDOWN_4_PCT", "SIM_DRAWDOWN_5_PCT",
                      "SIM_DAILY_LOSS_1_5_PCT"):
            with self.subTest(event=event):
                r = mod.evaluate(mod.fixture(event))
                self.assertFalse(r["real_exit_or_order_action_performed"])
                self.assertFalse(r["real_stop_release_granted"])
                self.assertEqual(r["runtime_go_no_go"], "NO_GO")

    def test_sequence_replay_gap_negative_and_boolean_refused(self):
        for previous, seq in ((1, 1), (1, 3), (9, 9), (-1, 0),
                              (True, 2), (1, False), (1, "2"),
                              (1000000, 1000001)):
            with self.subTest(previous=previous, seq=seq):
                self.reject(lambda x, p=previous, s=seq:
                            x.update(previous_sequence=p, sequence=s),
                            "P44_SEQUENCE_ROLLBACK_OR_GAP")

    def test_unknown_real_event_and_spoofed_approval_refused(self):
        for value in ("LIVE_TRADING_ACTIVATED", "REAL_USER_APPROVED",
                      "RELEASE_STOP", None, 10, True):
            with self.subTest(value=value):
                self.reject(lambda x, v=value: x.update(event=v),
                            "P44_UNKNOWN_OR_REAL_EVENT_INJECTED")

    def test_all_safety_fields_immutable_in_mock(self):
        for key, value in mod.SAFETY.items():
            with self.subTest(key=key):
                changed = (not value if type(value) is bool
                           else (1 if type(value) is int else "GO"))
                self.reject(lambda x, k=key, v=changed:
                            x["safety"].update({k: v}),
                            "P44_UNAUTHORIZED_RESUMPTION_OR_EXIT_PROOF")

    def test_mock_held_status_and_scope_cannot_be_real(self):
        self.reject(lambda x: x.update(
            classification="PRODUCTION_STOP_LATCH"),
            "P44_REAL_STOP_STATE_MISREPRESENTED")
        self.reject(lambda x: x.update(state="LIVE_RUNNING"),
                    "P44_REAL_STOP_STATE_MISREPRESENTED")

    def test_secret_data_or_malformed_envelope_rejected_without_leak(self):
        for bad in (None, {}, [], "", True, 100,
                    {"password": "CANARY_VALUE_44"}):
            r = mod.evaluate(bad)
            self.assertEqual(r["status"], "FAIL_CLOSED")
            self.assertNotIn("CANARY_VALUE_44", str(r))
        self.reject(lambda x: x.update(account_number="CANARY_VALUE_44"),
                    "P44_INVALID_OR_EXTRA_FIELDS")
        self.reject(lambda x: x["safety"].update(
            real_account_id="CANARY_VALUE_44"),
            "P44_UNAUTHORIZED_RESUMPTION_OR_EXIT_PROOF")


if __name__ == "__main__":
    unittest.main()
