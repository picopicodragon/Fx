"""Across seven mock-only safety modules, 42 adversarial inputs fail closed."""
from __future__ import annotations

import copy
import unittest

from scripts import risk_3p_45_synthetic_schema_mutation_campaign as mod


class MultiContractMutationTests(unittest.TestCase):
    def test_campaign_has_seven_unique_contracts_and_six_fault_types(self):
        self.assertEqual(len(mod.CONTRACTS), 7)
        self.assertEqual(len(set(name for name, _, _ in mod.CONTRACTS)), 7)
        self.assertEqual(len(mod.FAULT_IDS), 6)
        self.assertEqual(len(set(mod.FAULT_IDS)), 6)

    def test_complete_campaign_never_promotes_runtime(self):
        state = mod.campaign()
        self.assertEqual(state["status"],
                         "PASS_OFFLINE_MUTATION_CAMPAIGN_ONLY", state)
        self.assertEqual(state["synthetic_cases"], 42)
        self.assertEqual(state["synthetic_contracts"], 7)
        self.assertEqual(state["synthetic_fault_kinds"], 6)
        self.assertEqual(state["errors"], [])
        self.assertEqual(state["actual_p05_items_passed"], 0)
        self.assertFalse(state["real_mt4_session_authorized"])
        self.assertFalse(state["order_or_ea_operation_authorized"])
        self.assertEqual(state["runtime_go_no_go"], "NO_GO")
        self.assertTrue(state["safety_hold_latched"])

    def test_all_forty_two_bad_inputs_have_no_unsafe_side_effects(self):
        for name, factory, evaluate in mod.CONTRACTS:
            base = factory()
            with self.subTest(name=name, fault="baseline"):
                clean = evaluate(copy.deepcopy(base))
                self.assertTrue(clean["status"].startswith("PASS_"), clean)
            for fault in mod.FAULT_IDS:
                with self.subTest(name=name, fault=fault):
                    inp = mod._mutation(base, fault)
                    result = evaluate(inp)
                    self.assertEqual(result["status"], "FAIL_CLOSED", result)
                    self.assertEqual(result["runtime_go_no_go"], "NO_GO")
                    self.assertTrue(result["safety_hold_latched"])
                    self.assertNotIn(mod.CANARY, str(result))

    def test_faults_do_not_mutate_original_synthetic_fixtures(self):
        for name, factory, evaluate in mod.CONTRACTS:
            original = factory()
            before = copy.deepcopy(original)
            for fault in mod.FAULT_IDS:
                mod._mutation(original, fault)
                self.assertEqual(original, before, (name, fault))

    def test_mutation_names_not_source_or_secret_values(self):
        for fault in mod.FAULT_IDS:
            with self.subTest(fault=fault):
                self.assertNotIn("MT4_CONNECT", fault)
                self.assertNotIn("BROKER_LOGIN", fault)
        state = mod.campaign()
        self.assertNotIn(mod.CANARY, str(state))
        self.assertNotIn("C:\\Users\\", str(state))


if __name__ == "__main__":
    unittest.main()
