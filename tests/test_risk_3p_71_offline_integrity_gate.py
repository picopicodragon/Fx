"""RISK-3P-71: composite mock integrity cannot authorize live activity."""
from __future__ import annotations

import copy
import unittest

from scripts import risk_3p_71_offline_integrity_gate as mod


class OfflineIntegrityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.baselines = dict(zip(mod.NAMES, mod._outputs()))

    def reject(self, name, edit, expected):
        snapshot = copy.deepcopy(self.baselines[name])
        edit(snapshot)
        result = mod.evaluate(injected={name:snapshot})
        self.assertEqual(result["status"], "FAIL_CLOSED", result)
        self.assertIn(expected, result["errors"], result)
        self.assertEqual(result["p05_passed"], 0)
        self.assertEqual(result["g1_real_verified"], 0)
        self.assertFalse(result["real_mt4_observation_authorized"])
        self.assertFalse(result["real_order_execution_authorized"])
        self.assertFalse(result["main_auto_merge_authorized"])
        self.assertEqual(result["runtime_go_no_go"], "NO_GO")
        self.assertTrue(result["safety_hold_latched"])

    def test_integrity_gate_seven_checks_pass_only_offline(self):
        result = mod.evaluate()
        self.assertEqual(result["status"], "PASS_OFFLINE_INTEGRITY_ONLY",
                         result)
        self.assertEqual(result["offline_subchecks"], 7)
        self.assertEqual(result["simulated_faults_in_nested_campaign"], 29)
        self.assertEqual(result["pinned_offline_sources"], 45)
        self.assertFalse(result["human_p05_signoff"])
        self.assertEqual(result["errors"], [])

    def test_each_subcheck_must_remain_no_go(self):
        for name, status, current in zip(mod.NAMES, mod.STATUS,
                                          self.baselines.values()):
            with self.subTest(name=name):
                self.assertEqual(current["status"], status)
                self.assertEqual(current["runtime_go_no_go"], "NO_GO")
                self.assertTrue(current["safety_hold_latched"])

    def test_false_source_proof_not_acceptance(self):
        self.reject("pinned_offline_inventory",
                    lambda x: x.update(real_source_authenticity_verified=True),
                    "P71_REAL_PERMISSION_OR_FALSE_PROOF:4")

    def test_missing_stop_latch_refused(self):
        self.reject("no_unreviewed_import_time_calls",
                    lambda x: x.update(safety_hold_latched=False),
                    "P71_CHILD_REPORT_MISSING_OR_INVALID:6")

    def test_coverage_counts_cannot_forge_report_success(self):
        self.reject("twenty_nine_mock_attacks",
                    lambda x: x.update(mock_failures_exercised=28),
                    "P71_COVERAGE_COUNTER_CHANGED:7")

    def test_unknown_private_injection_must_not_echo_payload(self):
        result = mod.evaluate(injected={
            "private_login_data": "PRIVATE_CANARY_71"})
        self.assertEqual(result["status"], "FAIL_CLOSED")
        self.assertIn("P71_UNKNOWN_OR_PRIVATE_RESULT_NAME", result["errors"])
        self.assertNotIn("PRIVATE_CANARY_71", str(result))


if __name__ == "__main__":
    unittest.main()
