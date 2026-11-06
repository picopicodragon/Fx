"""Mock-only intake: no real MT4 data, broker credentials or authorization."""
from __future__ import annotations

import copy
import unittest

from scripts import risk_3p_55_synthetic_ingress_contract as mod


class SyntheticIngressTests(unittest.TestCase):
    def setUp(self):
        self.base = mod.fixture()

    def reject(self, change, code):
        data = copy.deepcopy(self.base)
        change(data)
        result = mod.evaluate(data)
        self.assertEqual(result["status"], "FAIL_CLOSED", result)
        self.assertIn(code, result["errors"], result)
        self.assertFalse(result["real_broker_origin_verified"])
        self.assertFalse(result["human_p05_signoff"])
        self.assertEqual(result["p05_passed"], 0)
        self.assertEqual(result["g1_real_verified"], 0)
        self.assertEqual(result["runtime_go_no_go"], "NO_GO")
        self.assertTrue(result["safety_hold_latched"])

    def test_baseline_uses_only_simulated_evidence_and_no_go(self):
        r = mod.evaluate(self.base)
        self.assertEqual(r["status"], "PASS_SYNTHETIC_INGRESS_FORMAT_ONLY")
        self.assertEqual(r["fake_event_count"], 3)
        self.assertEqual(r["fake_g1_field_count"], 15)
        self.assertEqual(r["real_observation_count"], 0)
        self.assertFalse(r["private_data_read_authorized"])
        self.assertFalse(r["orders_or_ea_authorized"])

    def test_rejects_purported_real_broker_source_mode(self):
        self.reject(lambda x: x.update(
            source_mode="LIVE_MT4_BROKER_API"), "P55_REAL_SOURCE_OR_ACCESS_SCOPE_SPOOFED")
        self.reject(lambda x: x.update(
            classification="REAL_EVIDENCE_VERIFIED"),
            "P55_REAL_SOURCE_OR_ACCESS_SCOPE_SPOOFED")

    def test_secret_or_unknown_envelope_columns_fail_closed(self):
        self.reject(lambda x: x.update(
            broker_password="PRIVATE_CANARY_55"),
            "P55_INGRESS_ENVELOPE_MISSING_OR_SENSITIVE_FIELDS")
        self.reject(lambda x: x.pop("owner_review"),
                    "P55_INGRESS_ENVELOPE_MISSING_OR_SENSITIVE_FIELDS")

    def test_hash_chain_forgery_cannot_pass(self):
        self.reject(lambda x: x["event_chain"]["rows"][1].update(
            previous_hash="0" * 64), "P55_UNTRUSTED_SYNTHETIC_CHAIN")

    def test_witness_conflict_cannot_pass(self):
        self.reject(lambda x: x["two_witnesses"]
                    ["second_witness"]["rows"][0].update(
                        synthetic_decimal="999.99"),
                    "P55_UNTRUSTED_SYNTHETIC_WITNESSES")

    def test_owner_p05_signature_never_inherited(self):
        self.reject(lambda x: x["owner_review"]
                    ["unsigned_p05"][0].update(
                        explicit_owner_signoff=True),
                    "P55_UNTRUSTED_SYNTHETIC_REVIEW")

    def test_safety_permission_forgery_rejected_for_every_field(self):
        for key, original in mod.SAFETY.items():
            with self.subTest(key=key):
                value = (not original if type(original) is bool
                         else (1 if type(original) is int else "GO"))
                self.reject(lambda x, k=key, v=value:
                            x["safety"].update({k: v}),
                            "P55_BROKER_OR_APPROVAL_PERMISSION_FORGED")

    def test_malformed_nested_witness_cannot_crash_or_echo(self):
        for value in (None, {}, [], {"password": "PRIVATE_CANARY_55"}):
            with self.subTest(type=type(value).__name__):
                data = copy.deepcopy(self.base)
                data["two_witnesses"] = value
                result = mod.evaluate(data)
                self.assertEqual(result["status"], "FAIL_CLOSED")
                self.assertNotIn("PRIVATE_CANARY_55", str(result))
                self.assertEqual(result["runtime_go_no_go"], "NO_GO")

    def test_invalid_input_types_are_fail_closed(self):
        for x in (None, [], "", {}, True, 3, {
                "secret": "PRIVATE_CANARY_55"}):
            result = mod.evaluate(x)
            self.assertEqual(result["status"], "FAIL_CLOSED")
            self.assertNotIn("PRIVATE_CANARY_55", str(result))
            self.assertFalse(result["real_mt4_read_authorized"])


if __name__ == "__main__":
    unittest.main()
