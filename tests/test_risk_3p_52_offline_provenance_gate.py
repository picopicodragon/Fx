"""Synthetic P05 provenance gate integrates chain, witnesses and review."""
from __future__ import annotations

import copy
import unittest

from scripts import risk_3p_52_offline_provenance_gate as mod


class CompositeProvenanceGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.outputs = dict(zip(mod.CASE_NAMES, mod._results(mod.ROOT)))

    def reject(self, name, mutate, error):
        value = copy.deepcopy(self.outputs[name])
        mutate(value)
        result = mod.evaluate(injected={name: value})
        self.assertEqual(result["status"], "FAIL_CLOSED", result)
        self.assertIn(error, result["errors"], result)
        self.assertFalse(result["real_broker_evidence_verified"])
        self.assertFalse(result["independent_source_authenticity_verified"])
        self.assertEqual(result["p05_passed"], 0)
        self.assertEqual(result["g1_real_verified"], 0)
        self.assertFalse(result["real_mt4_read_authorized"])
        self.assertEqual(result["runtime_go_no_go"], "NO_GO")
        self.assertTrue(result["safety_hold_latched"])

    def test_baseline_cross_gate_checks_four_modules_no_live_proof(self):
        result = mod.evaluate()
        self.assertEqual(result["status"], "PASS_OFFLINE_PROVENANCE_QA_ONLY",
                         result)
        self.assertEqual(result["offline_modules_checked"], 4)
        self.assertEqual(result["errors"], [])
        self.assertFalse(result["real_owner_authorization_recorded"])
        self.assertFalse(result["real_order_execution_authorized"])

    def test_each_mock_module_expected_and_no_go(self):
        for name, status, obj in zip(mod.CASE_NAMES, mod.EXPECTED,
                                    mod._results(mod.ROOT)):
            with self.subTest(name=name):
                self.assertEqual(obj["status"], status)
                self.assertEqual(obj["errors"], [])
                self.assertEqual(obj["runtime_go_no_go"], "NO_GO")

    def test_any_unrecognized_success_is_rejected(self):
        for i, name in enumerate(mod.CASE_NAMES, 1):
            with self.subTest(name=name):
                self.reject(name,
                            lambda x: x.update(
                                status="PASS_REAL_BROKER_CERTIFIED"),
                            "P52_COMPOSITE_RESULT_UNTRUSTED:" + str(i))

    def test_go_and_safety_stop_changes_are_rejected(self):
        for i, name in enumerate(mod.CASE_NAMES, 1):
            with self.subTest(name=name):
                self.reject(name,
                            lambda x: x.update(runtime_go_no_go="GO"),
                            "P52_COMPOSITE_RESULT_UNTRUSTED:" + str(i))
                self.reject(name,
                            lambda x: x.update(safety_hold_latched=False),
                            "P52_COMPOSITE_RESULT_UNTRUSTED:" + str(i))

    def test_no_real_broker_sources_or_owner_approval_flags_accepted(self):
        self.reject("simulated_chain",
                    lambda x: x.update(broker_origin_verified=True),
                    "P52_REAL_WORLD_AUTHORITY_FABRICATED:1")
        self.reject("simulated_dual_witness",
                    lambda x: x.update(
                        actual_source_independence_verified=True),
                    "P52_REAL_WORLD_AUTHORITY_FABRICATED:2")
        self.reject("unsigned_owner_review",
                    lambda x: x.update(owner_p05_approval_recorded=True),
                    "P52_REAL_WORLD_AUTHORITY_FABRICATED:3")
        self.reject("existing_p05_quality_gate",
                    lambda x: x.update(real_mt4_read_authorized=True),
                    "P52_REAL_WORLD_AUTHORITY_FABRICATED:4")

    def test_no_g1_or_p05_counts_can_be_fabricated(self):
        self.reject("simulated_chain",
                    lambda x: x.update(g1_verified=15),
                    "P52_P05_OR_G1_VALUES_FAKE_ACCEPTED:1")
        self.reject("simulated_dual_witness",
                    lambda x: x.update(actual_broker_fields_verified=15),
                    "P52_P05_OR_G1_VALUES_FAKE_ACCEPTED:2")
        self.reject("unsigned_owner_review",
                    lambda x: x.update(p05_passed=8),
                    "P52_P05_OR_G1_VALUES_FAKE_ACCEPTED:3")

    def test_unknown_case_cannot_inject_secret_payload(self):
        result = mod.evaluate(injected={
            "private_account_password": "CANARY_VALUE_52"})
        self.assertEqual(result["status"], "FAIL_CLOSED")
        self.assertIn("P52_INJECTED_UNKNOWN_OR_SENSITIVE_CASE", result["errors"])
        self.assertNotIn("CANARY_VALUE_52", str(result))

    def test_malformed_override_never_authorizes_runtime(self):
        for name in mod.CASE_NAMES:
            with self.subTest(name=name):
                result = mod.evaluate(injected={name: None})
                self.assertEqual(result["status"], "FAIL_CLOSED")
                self.assertEqual(result["runtime_go_no_go"], "NO_GO")
                self.assertFalse(result["real_mt4_read_authorized"])


if __name__ == "__main__":
    unittest.main()
