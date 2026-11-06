"""Mock-only intake: no real MT4 data, broker credentials or authorization."""
from __future__ import annotations

import copy
import unittest
from unittest.mock import patch

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


    def test_false_bool_replaced_by_zero_is_rejected_not_coerced(self):
        for field, expected in mod.SAFETY.items():
            if type(expected) is bool and expected is False:
                with self.subTest(field=field):
                    self.reject(lambda d, k=field: d["safety"].update({k: 0}),
                                "P55_BROKER_OR_APPROVAL_PERMISSION_FORGED")

    def test_true_bool_replaced_by_one_is_rejected_not_coerced(self):
        for field, expected in mod.SAFETY.items():
            if type(expected) is bool and expected is True:
                with self.subTest(field=field):
                    self.reject(lambda d, k=field: d["safety"].update({k: 1}),
                                "P55_BROKER_OR_APPROVAL_PERMISSION_FORGED")

    def test_integer_zero_replaced_by_false_is_rejected(self):
        for field, expected in mod.SAFETY.items():
            if type(expected) is int and expected == 0:
                with self.subTest(field=field):
                    self.reject(lambda d, k=field: d["safety"].update({k: False}),
                                "P55_BROKER_OR_APPROVAL_PERMISSION_FORGED")

    def test_permissions_must_be_exact_dictionary(self):
        class Rogue(dict):
            def __eq__(self, other):
                raise RuntimeError("PRIVATE_CANARY_151")
        self.reject(lambda d: d.update(safety=Rogue(d["safety"])),
                    "P55_BROKER_OR_APPROVAL_PERMISSION_FORGED")

    def test_safety_unknown_key_rejected_even_if_values_match(self):
        self.reject(lambda d: d["safety"].update(unlisted="PRIVATE_CANARY_151"),
                    "P55_BROKER_OR_APPROVAL_PERMISSION_FORGED")

    def test_poisoned_envelope_key_not_rehashed_or_compared(self):
        class Key:
            calls = 0
            def __hash__(self):
                type(self).calls += 1
                return hash("schema_version")
            def __eq__(self, other):
                type(self).calls += 1
                raise RuntimeError("PRIVATE_CANARY_151")
        d = copy.deepcopy(self.base)
        d.pop("schema_version")
        d[Key()] = 1
        Key.calls = 0
        result = mod.evaluate(d)
        self.assertEqual(result["status"], "FAIL_CLOSED")
        self.assertIn("P55_INGRESS_ENVELOPE_MISSING_OR_SENSITIVE_FIELDS",
                      result["errors"])
        self.assertEqual(Key.calls, 0)
        self.assertNotIn("PRIVATE_CANARY_151", str(result))

    def test_poisoned_safety_key_not_rehashed_or_compared(self):
        class Key:
            calls = 0
            def __hash__(self):
                type(self).calls += 1
                return hash("p05_passed")
            def __eq__(self, other):
                type(self).calls += 1
                raise RuntimeError("PRIVATE_CANARY_151")
        d = copy.deepcopy(self.base)
        d["safety"].pop("p05_passed")
        d["safety"][Key()] = 0
        Key.calls = 0
        result = mod.evaluate(d)
        self.assertEqual(result["status"], "FAIL_CLOSED")
        self.assertIn("P55_BROKER_OR_APPROVAL_PERMISSION_FORGED",
                      result["errors"])
        self.assertEqual(Key.calls, 0)

    def test_poisoned_classification_comparison_never_invoked(self):
        class Value:
            calls = 0
            def __eq__(self, other):
                type(self).calls += 1
                raise RuntimeError("PRIVATE_CANARY_151")
            def __ne__(self, other):
                type(self).calls += 1
                raise RuntimeError("PRIVATE_CANARY_151")
        d = copy.deepcopy(self.base)
        d["classification"] = Value()
        result = mod.evaluate(d)
        self.assertEqual(result["status"], "FAIL_CLOSED")
        self.assertIn("P55_REAL_SOURCE_OR_ACCESS_SCOPE_SPOOFED",
                      result["errors"])
        self.assertEqual(Value.calls, 0)

    def test_poisoned_source_mode_comparison_never_invoked(self):
        class Value:
            calls = 0
            def __ne__(self, other):
                type(self).calls += 1
                raise RuntimeError("PRIVATE_CANARY_151")
        d = copy.deepcopy(self.base)
        d["source_mode"] = Value()
        result = mod.evaluate(d)
        self.assertEqual(result["status"], "FAIL_CLOSED")
        self.assertIn("P55_REAL_SOURCE_OR_ACCESS_SCOPE_SPOOFED",
                      result["errors"])
        self.assertEqual(Value.calls, 0)

    def test_child_result_dict_subclass_not_evaluated(self):
        class PoisonDict(dict):
            calls = 0
            def get(self, key, default=None):
                type(self).calls += 1
                raise RuntimeError("PRIVATE_CANARY_151")
        with patch.object(mod.chain, "evaluate",
                          return_value=PoisonDict({"status": "PASS"})):
            result = mod.evaluate(copy.deepcopy(self.base))
        self.assertEqual(result["status"], "FAIL_CLOSED")
        self.assertIn("P55_UNTRUSTED_SYNTHETIC_CHAIN", result["errors"])
        self.assertEqual(PoisonDict.calls, 0)

    def test_child_status_object_is_rejected_without_comparison(self):
        class Value:
            calls = 0
            def __eq__(self, other):
                type(self).calls += 1
                raise RuntimeError("PRIVATE_CANARY_151")
            def __ne__(self, other):
                type(self).calls += 1
                raise RuntimeError("PRIVATE_CANARY_151")
        forged = {"status": Value(), "runtime_go_no_go": "NO_GO",
                  "safety_hold_latched": True}
        with patch.object(mod.witness, "evaluate", return_value=forged):
            result = mod.evaluate(copy.deepcopy(self.base))
        self.assertEqual(result["status"], "FAIL_CLOSED")
        self.assertIn("P55_UNTRUSTED_SYNTHETIC_WITNESSES", result["errors"])
        self.assertEqual(Value.calls, 0)

    def test_child_result_object_key_is_not_hashed_when_checked(self):
        class Key:
            calls = 0
            def __hash__(self):
                type(self).calls += 1
                return hash("status")
            def __eq__(self, other):
                type(self).calls += 1
                raise RuntimeError("PRIVATE_CANARY_151")
        result_map = {"status": "PASS_NO_REAL_APPROVAL_ONLY",
                      "runtime_go_no_go": "NO_GO",
                      "safety_hold_latched": True}
        result_map.pop("status")
        result_map[Key()] = "PASS_NO_REAL_APPROVAL_ONLY"
        Key.calls = 0
        with patch.object(mod.consent, "evaluate", return_value=result_map):
            result = mod.evaluate(copy.deepcopy(self.base))
        self.assertEqual(result["status"], "FAIL_CLOSED")
        self.assertIn("P55_UNTRUSTED_SYNTHETIC_REVIEW", result["errors"])
        self.assertEqual(Key.calls, 0)

    def test_child_runtime_error_is_caught_with_fixed_code(self):
        with patch.object(mod.chain, "evaluate",
                          side_effect=RuntimeError("PRIVATE_CANARY_151")):
            r = mod.evaluate(copy.deepcopy(self.base))
        self.assertEqual(r["status"], "FAIL_CLOSED")
        self.assertIn("P55_MALFORMED_SYNTHETIC_CHAIN", r["errors"])
        self.assertNotIn("PRIVATE_CANARY_151", str(r))
        self.assertEqual(r["runtime_go_no_go"], "NO_GO")

    def test_child_type_error_is_caught_with_fixed_code(self):
        with patch.object(mod.witness, "evaluate",
                          side_effect=TypeError("PRIVATE_CANARY_151")):
            r = mod.evaluate(copy.deepcopy(self.base))
        self.assertEqual(r["status"], "FAIL_CLOSED")
        self.assertIn("P55_MALFORMED_SYNTHETIC_WITNESSES", r["errors"])
        self.assertNotIn("PRIVATE_CANARY_151", str(r))

    def test_child_result_latched_value_requires_true_boolean(self):
        forged = {"status": "PASS_TWO_FAKE_WITNESSES_ONLY",
                  "runtime_go_no_go": "NO_GO",
                  "safety_hold_latched": 1}
        with patch.object(mod.witness, "evaluate", return_value=forged):
            r = mod.evaluate(copy.deepcopy(self.base))
        self.assertEqual(r["status"], "FAIL_CLOSED")
        self.assertIn("P55_UNTRUSTED_SYNTHETIC_WITNESSES", r["errors"])
        self.assertTrue(r["safety_hold_latched"])

    def test_source_mode_and_classification_type_spoofing_rejected(self):
        for key in ("classification", "source_mode"):
            with self.subTest(key=key):
                self.reject(lambda d,k=key: d.update({k: 0}),
                            "P55_REAL_SOURCE_OR_ACCESS_SCOPE_SPOOFED")

    def test_ingress_baseline_still_never_authorizes_broker_operations(self):
        result = mod.evaluate(mod.fixture())
        self.assertEqual(result["status"],
                         "PASS_SYNTHETIC_INGRESS_FORMAT_ONLY")
        self.assertFalse(result["orders_or_ea_authorized"])
        self.assertFalse(result["real_mt4_read_authorized"])
        self.assertFalse(result["real_broker_origin_verified"])
        self.assertFalse(result["human_p05_signoff"])
        self.assertEqual(result["runtime_go_no_go"], "NO_GO")
        self.assertTrue(result["safety_hold_latched"])

    def test_chains_witnesses_and_owner_are_still_all_required(self):
        for k in ("event_chain", "two_witnesses", "owner_review"):
            with self.subTest(key=k):
                self.reject(lambda d,name=k: d.pop(name),
                            "P55_INGRESS_ENVELOPE_MISSING_OR_SENSITIVE_FIELDS")



if __name__ == "__main__":
    unittest.main()
