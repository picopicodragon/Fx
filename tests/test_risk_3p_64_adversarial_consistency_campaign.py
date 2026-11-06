"""Offline P60 seven-report adversarial campaign: no unknown GO can pass."""
from __future__ import annotations

import copy
import unittest

from scripts import risk_3p_64_adversarial_consistency_campaign as mod
from scripts import risk_3p_60_offline_ingress_quality_gate as gate


class SyntheticCorruptionCampaignTests(unittest.TestCase):
    def test_campaign_has_seven_reports_and_ten_distinct_mutations(self):
        self.assertEqual(len(gate.NAMES), 7)
        self.assertEqual(len(set(gate.NAMES)), 7)
        self.assertEqual(len(mod.FAULTS), 10)
        self.assertEqual(len(set(mod.FAULTS)), 10)

    def test_all_seventy_corruptions_fail_without_real_mt4_permission(self):
        result = mod.campaign()
        self.assertEqual(result["status"],
                         "PASS_SEVENTY_MOCK_CORRUPTIONS_ONLY", result)
        self.assertEqual(result["synthetic_corruptions_checked"], 70)
        self.assertEqual(result["composite_integration_cases_checked"], 7)
        self.assertEqual(result["errors"], [])
        self.assertFalse(result["actual_broker_evidence_received"])
        self.assertFalse(result["real_mt4_access_authorized"])
        self.assertFalse(result["order_execution_authorized"])
        self.assertEqual(result["p05_passed"], 0)
        self.assertEqual(result["runtime_go_no_go"], "NO_GO")
        self.assertTrue(result["safety_hold_latched"])

    def test_new_false_approval_columns_cannot_hide_in_pass_snapshots(self):
        originals = dict(zip(gate.NAMES, gate._outputs()))
        for name in gate.NAMES:
            with self.subTest(name=name):
                mutated = mod.mutate(
                    originals[name], "ADDED_UNKNOWN_APPROVAL")
                result = gate.evaluate(injected={name: mutated})
                self.assertEqual(result["status"], "FAIL_CLOSED")
                self.assertIn(
                    "P61_UNKNOWN_FIELD_TYPE_OR_VALUE_DRIFT:"
                    + str(gate.NAMES.index(name) + 1),
                    result["errors"])

    def test_boolean_false_is_not_valid_integer_zero_count(self):
        first = dict(zip(gate.NAMES, gate._outputs()))["fictional_ingress"]
        poisoned = mod.mutate(first, "TYPE_CONFUSED_ZERO_COUNTER")
        self.assertIs(poisoned["p05_passed"], False)
        self.assertIs(type(first["p05_passed"]), int)
        result = gate.evaluate(injected={"fictional_ingress": poisoned})
        self.assertEqual(result["status"], "FAIL_CLOSED")
        self.assertEqual(result["runtime_go_no_go"], "NO_GO")

    def test_private_status_and_error_strings_never_appear_in_output(self):
        first = dict(zip(gate.NAMES, gate._outputs()))["fake_clocks"]
        for fault in ("PRIVATE_STATUS_STRING", "SECRET_ERROR_TEXT"):
            with self.subTest(fault=fault):
                r = gate.evaluate(injected={
                    "fake_clocks": mod.mutate(first, fault)})
                self.assertEqual(r["status"], "FAIL_CLOSED")
                self.assertNotIn(mod.CANARY, str(r))

    def test_mutation_does_not_modify_original_or_main_p05_status(self):
        first = dict(zip(gate.NAMES, gate._outputs()))["safe_diagnostics"]
        original = copy.deepcopy(first)
        for kind in mod.FAULTS:
            mod.mutate(first, kind)
        self.assertEqual(first, original)
        self.assertEqual(gate.evaluate()["status"],
                         "PASS_COMBINED_OFFLINE_DESIGN_QA_ONLY")


if __name__ == "__main__":
    unittest.main()
