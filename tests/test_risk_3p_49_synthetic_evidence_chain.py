"""SHA-256 chain tests for mock event sequence, not broker authentication."""
from __future__ import annotations

import copy
import unittest

from scripts import risk_3p_49_synthetic_evidence_chain as mod


class MockChainTests(unittest.TestCase):
    def setUp(self):
        self.base = mod.fixture()

    def reject(self, mutate, code):
        data = copy.deepcopy(self.base)
        mutate(data)
        state = mod.evaluate(data)
        self.assertEqual(state["status"], "FAIL_CLOSED", state)
        self.assertIn(code, state["errors"])
        self.assertFalse(state["broker_origin_verified"])
        self.assertFalse(state["human_approval_verified"])
        self.assertFalse(state["real_mt4_read_authorized"])
        self.assertFalse(state["order_action_authorized"])
        self.assertEqual(state["runtime_go_no_go"], "NO_GO")
        self.assertTrue(state["safety_hold_latched"])

    def test_baseline_hash_chain_is_deterministic_not_a_signature(self):
        self.assertEqual(self.base, mod.fixture())
        self.assertEqual(mod.evaluate(self.base)["status"],
                         "PASS_SYNTHETIC_HASH_CHAIN_ONLY")
        state = mod.evaluate(self.base)
        self.assertFalse(state["cryptographic_authenticity_verified"])
        self.assertFalse(state["immutable_storage_verified"])
        self.assertEqual(state["simulated_events_checked"], 3)
        self.assertEqual(state["p05_passed"], 0)

    def test_every_payload_edit_without_rehash_is_detected(self):
        for index in range(3):
            with self.subTest(row=index):
                self.reject(
                    lambda d, n=index: d["rows"][n].update(
                        source_token="SIM_TAMPERED"),
                    "P49_EVENT_ORDER_OR_SYNTHETIC_SOURCE_DRIFT:"
                    + str(index + 1))

    def test_digest_tampering_and_link_disconnection(self):
        self.reject(lambda d: d["rows"][1].update(digest="0" * 64),
                    "P49_DIGEST_CONTENT_MISMATCH:2")
        self.reject(lambda d: d["rows"][2].update(
            previous_hash="0" * 64),
            "P49_HASH_CHAIN_DISCONNECTED:3")

    def test_replay_sequence_inversion_and_boolean_rejected(self):
        for val in (0, 2, 3, True, False, "1", None):
            with self.subTest(val=val):
                self.reject(
                    lambda d, x=val: d["rows"][0].update(sequence=x),
                    "P49_EVENT_ORDER_OR_SYNTHETIC_SOURCE_DRIFT:1")

    def test_invalid_time_and_invented_real_server_sources_rejected(self):
        self.reject(lambda d: d["rows"][0].update(
            fake_time="2026-11-06T00:00:00Z"),
            "P49_EVENT_ORDER_OR_SYNTHETIC_SOURCE_DRIFT:1")
        self.reject(lambda d: d["rows"][1].update(
            kind="REAL_BROKER_INDEPENDENT"),
            "P49_EVENT_ORDER_OR_SYNTHETIC_SOURCE_DRIFT:2")
        self.reject(lambda d: d["rows"][2].update(
            kind="REAL_OWNER_APPROVED"),
            "P49_EVENT_ORDER_OR_SYNTHETIC_SOURCE_DRIFT:3")

    def test_unexpected_secret_columns_not_allowed(self):
        self.reject(lambda d: d["rows"][0].update(
            private_account_id="NEVER_STORE_REAL_LOGIN"),
            "P49_INVALID_ROW_OR_SECRET_FIELD:1")
        self.reject(lambda d: d.update(api_key="CANARY_49"),
                    "P49_INVALID_OR_SENSITIVE_PACKAGE_FIELDS")

    def test_missing_or_duplicate_mock_events_not_accepted(self):
        self.reject(lambda d: d["rows"].pop(),
                    "P49_EXACTLY_THREE_FAKE_EVENTS_REQUIRED")
        self.reject(lambda d: d["rows"].append(copy.deepcopy(d["rows"][2])),
                    "P49_EXACTLY_THREE_FAKE_EVENTS_REQUIRED")

    def test_untrusted_human_approval_and_go_flags_never_trusted(self):
        for key in mod.SAFETY:
            with self.subTest(key=key):
                default = mod.SAFETY[key]
                value = not default if type(default) is bool else (
                    8 if type(default) is int else "GO")
                self.reject(lambda d, k=key, v=value:
                            d["safety"].update({k: v}),
                            "P49_FORGED_P05_OR_BROKER_PERMISSION")

    def test_malformed_root_inputs_do_not_echo_values(self):
        for value in (None, [], "", {}, True, 20,
                      {"secret": "CANARY_49"}):
            state = mod.evaluate(value)
            self.assertEqual(state["status"], "FAIL_CLOSED")
            self.assertNotIn("CANARY_49", str(state))


if __name__ == "__main__":
    unittest.main()
