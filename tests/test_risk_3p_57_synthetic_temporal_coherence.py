"""Two fake time sources demonstrate replay/rollback failures, not live freshness."""
from __future__ import annotations

import copy
import unittest

from scripts import risk_3p_57_synthetic_temporal_coherence as mod


class SyntheticClockTests(unittest.TestCase):
    def setUp(self):
        self.data = mod.fixture()

    def reject(self, change, error):
        x = copy.deepcopy(self.data)
        change(x)
        state = mod.evaluate(x)
        self.assertEqual(state["status"], "FAIL_CLOSED", state)
        self.assertIn(error, state["errors"], state)
        self.assertFalse(state["real_timestamp_authenticity_verified"])
        self.assertFalse(state["real_data_freshness_verified"])
        self.assertFalse(state["real_clock_monotonicity_verified"])
        self.assertFalse(state["real_mt4_session_authorized"])
        self.assertEqual(state["runtime_go_no_go"], "NO_GO")
        self.assertTrue(state["safety_hold_latched"])

    def test_baseline_fake_clock_pairs_never_prove_real_freshness(self):
        r = mod.evaluate(self.data)
        self.assertEqual(r["status"], "PASS_SIMULATED_CLOCK_CONSISTENCY_ONLY")
        self.assertEqual(r["synthetic_sample_pairs"], 3)
        self.assertEqual(r["p05_passed"], 0)
        self.assertEqual(r["g1_real_verified"], 0)
        self.assertFalse(r["order_or_ea_action_authorized"])

    def test_out_of_order_sequence_and_bool_rejected(self):
        for v in (0, 2, 3, True, "1", None):
            with self.subTest(v=v):
                self.reject(lambda d, n=v: d["terminal"]["samples"][0].update(seq=n),
                            "P57_BAD_SEQUENCE_OR_MONOTONIC_SAMPLE:1:terminal")

    def test_fake_monotonic_counter_rollbacks_and_gap_block(self):
        for v in (100, 99, 112):
            with self.subTest(v=v):
                self.reject(lambda d, n=v: d["terminal"]["samples"][1].update(
                    synthetic_monotonic_ticks=n),
                    "P57_ROLLBACK_REPLAY_OR_GAP:2:terminal")

    def test_real_or_bad_utc_never_accepted_as_synthetic(self):
        for v in ("2026-11-06T00:00:00Z", "SIM_2000-01-01T99:00:00Z",
                  "SIM_2000-01-02T00:00:00Z", None):
            with self.subTest(v=v):
                self.reject(lambda d, n=v: d["terminal"]["samples"][0].update(
                    fake_utc=n), "P57_REAL_OR_MALFORMED_TIME:1:terminal")

    def test_fake_utc_replay_and_large_jump_rejected(self):
        self.reject(lambda d: d["witness"]["samples"][1].update(
            fake_utc="SIM_2000-01-01T00:00:00Z"),
            "P57_ROLLBACK_REPLAY_OR_GAP:2:witness")
        self.reject(lambda d: d["witness"]["samples"][2].update(
            fake_utc="SIM_2000-01-01T00:00:30Z"),
            "P57_ROLLBACK_REPLAY_OR_GAP:3:witness")

    def test_fake_cross_source_skew_over_two_seconds_fails(self):
        self.reject(lambda d: d["witness"]["samples"][1].update(
            fake_utc="SIM_2000-01-01T00:00:04Z"),
            "P57_INTERSOURCE_FAKE_SKEW:2")

    def test_session_and_account_mismatch_rejected(self):
        self.reject(lambda d: d["terminal"].update(session_alias="SIM_RESTARTED"),
                    "P57_SOURCE_IDENTITY_OR_SESSION_CHANGED:terminal")
        self.reject(lambda d: d["witness"].update(origin="SIM_REAL_BROKER"),
                    "P57_SOURCE_IDENTITY_OR_SESSION_CHANGED:witness")
        self.reject(lambda d: d.update(account_alias="SIM_LIVE"),
                    "P57_REAL_SOURCE_OR_ACCOUNT_SPOOF")

    def test_source_missing_and_extra_private_columns_rejected(self):
        self.reject(lambda d: d["terminal"]["samples"].pop(),
                    "P57_REQUIRED_THREE_SAMPLES:terminal")
        self.reject(lambda d: d["terminal"]["samples"][0].update(
            private_order_ticket="CANARY_57"),
            "P57_BAD_SEQUENCE_OR_MONOTONIC_SAMPLE:1:terminal")
        self.reject(lambda d: d.update(broker_password="CANARY_57"),
                    "P57_ENVELOPE_MISSING_OR_PRIVATE_FIELDS")

    def test_safety_flags_immutable(self):
        for key, original in mod.SAFETY.items():
            with self.subTest(key=key):
                value = not original if type(original) is bool else (
                    1 if type(original) is int else "GO")
                self.reject(lambda d, k=key, v=value:
                            d["safety"].update({k: v}),
                            "P57_REAL_FRESHNESS_OR_RUNTIME_PERMISSION_FORGED")

    def test_malformed_roots_do_not_echo_canary(self):
        for x in (None, {}, [], "", 9, {"secret": "CANARY_57"}):
            state = mod.evaluate(x)
            self.assertEqual(state["status"], "FAIL_CLOSED")
            self.assertNotIn("CANARY_57", str(state))


if __name__ == "__main__":
    unittest.main()
