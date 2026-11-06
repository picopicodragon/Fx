"""Combined 18-scenario simulated QA gate is never live approval."""
from __future__ import annotations

import copy
import unittest

from scripts import risk_3p_47_48_offline_quality_gate as mod


class OfflineQualityGateTests(unittest.TestCase):
    def setUp(self):
        self.outputs = {name: copy.deepcopy(result)
                        for name, result, _ in mod._cases(mod.ROOT)}

    def refuse(self, case_id, change, code):
        cloned = copy.deepcopy(self.outputs[case_id])
        change(cloned)
        outcome = mod.evaluate(injected={case_id: cloned})
        self.assertEqual(outcome["status"], "FAIL_CLOSED")
        self.assertIn(code, outcome["errors"])
        self.assertEqual(outcome["real_p05_passed"], 0)
        self.assertEqual(outcome["real_g1_verified"], 0)
        self.assertFalse(outcome["real_mt4_read_authorized"])
        self.assertFalse(outcome["real_order_execution_authorized"])
        self.assertFalse(outcome["main_auto_merge_authorized"])
        self.assertEqual(outcome["runtime_go_no_go"], "NO_GO")
        self.assertTrue(outcome["safety_hold_latched"])

    def test_all_mock_scenarios_return_offline_success_but_no_go(self):
        result = mod.evaluate()
        self.assertEqual(result["status"], "PASS_OFFLINE_QUALITY_GATE_ONLY",
                         result)
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["simulated_check_cases"], 18)
        self.assertEqual(result["expected_simulated_cases"], 18)
        self.assertEqual(result["nested_fault_campaign_cases"], 16)
        self.assertEqual(result["nested_mutation_cases"], 42)
        self.assertFalse(result["actual_broker_or_mt4_contacted"])
        self.assertFalse(result["human_p05_signoff"])

    def test_every_case_is_named_and_expected_to_be_mock_only(self):
        scenarios = list(mod._cases(mod.ROOT))
        self.assertEqual(len(scenarios), mod.EXPECTED_CASES)
        self.assertEqual(len({name for name, _, _ in scenarios}),
                         mod.EXPECTED_CASES)
        for name, outcome, expected in scenarios:
            with self.subTest(name=name):
                self.assertEqual(outcome["status"], expected)
                self.assertEqual(outcome["errors"], [])
                self.assertEqual(outcome["runtime_go_no_go"], "NO_GO")

    def test_fault_gate_fails_if_old_mutation_coverage_drops(self):
        self.refuse("mutation42",
                    lambda d: d.update(synthetic_cases=41),
                    "P47_MUTATION_COVERAGE_MISSING")
        self.refuse("fault16",
                    lambda d: d.update(simulated_faults_exercised=15),
                    "P47_FAULT_COVERAGE_MISSING")

    def test_any_mock_go_promotion_is_refused(self):
        for name in self.outputs:
            with self.subTest(case=name):
                self.refuse(name,
                            lambda d: d.update(runtime_go_no_go="GO"),
                            "P47_CASE_INVALID_OR_UNVERIFIED:" + name)

    def test_any_mock_stop_latch_deletion_is_refused(self):
        for name in self.outputs:
            with self.subTest(case=name):
                self.refuse(name,
                            lambda d: d.update(safety_hold_latched=False),
                            "P47_CASE_INVALID_OR_UNVERIFIED:" + name)

    def test_simulated_pass_cannot_be_real_mt4_permission(self):
        self.refuse("timeline_close",
                    lambda d: d.update(real_close_event_verified=True),
                    "P48_REAL_WORLD_PERMISSION_PROMOTED:timeline_close")
        self.refuse("p05_acceptance_debt",
                    lambda d: d.update(real_trading_authorized=True),
                    "P48_REAL_WORLD_PERMISSION_PROMOTED:p05_acceptance_debt")
        self.refuse("fault16",
                    lambda d: d.update(order_authorized=True),
                    "P48_REAL_WORLD_PERMISSION_PROMOTED:fault16")

    def test_approval_counts_cannot_be_invented(self):
        self.refuse("interlock_zero",
                    lambda d: d.update(real_p05_passed=8),
                    "P48_P05_OR_G1_ACCEPTANCE_FORGED:interlock_zero")
        self.refuse("p05_acceptance_debt",
                    lambda d: d.update(g1_broker_verified=15),
                    "P48_P05_OR_G1_ACCEPTANCE_FORGED:p05_acceptance_debt")

    def test_required_p05_and_g1_debt_counts_must_not_change(self):
        self.refuse("p05_acceptance_debt",
                    lambda d: d.update(p05_checks=7),
                    "P48_SAFETY_DEBT_COUNTS_DRIFT")
        self.refuse("p05_acceptance_debt",
                    lambda d: d.update(g1_fields=20),
                    "P48_SAFETY_DEBT_COUNTS_DRIFT")

    def test_unknown_or_secret_result_is_not_echoed(self):
        self.refuse("interlock_exposure",
                    lambda d: d.update(status="SECRET_REAL_BROKER_GO"),
                    "P47_CASE_INVALID_OR_UNVERIFIED:interlock_exposure")
        fake = {"status": "PRIVATE_VALUE_CANARY_48",
                "errors": ["PRIVATE_VALUE_CANARY_48"]}
        result = mod.evaluate(injected={"timeline_unchanged": fake})
        self.assertEqual(result["status"], "FAIL_CLOSED")
        self.assertNotIn("PRIVATE_VALUE_CANARY_48", str(result))

    def test_injected_non_mapping_and_null_fail_closed(self):
        for item in (None, [], "", True):
            with self.subTest(type=type(item).__name__):
                r = mod.evaluate(injected={"interlock_zero": item})
                self.assertEqual(r["status"], "FAIL_CLOSED")
                self.assertEqual(r["runtime_go_no_go"], "NO_GO")
                self.assertFalse(r["real_mt4_read_authorized"])


if __name__ == "__main__":
    unittest.main()
