"""Final mock governance audit rejects hidden permissions across six reports."""
from __future__ import annotations

import copy
import unittest

from scripts import risk_3p_65_integrated_offline_audit as mod


class OfflineGovernanceAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.baselines = dict(zip(mod.NAMES, mod._outputs()))

    def reject(self, name, edit, expected):
        d = copy.deepcopy(self.baselines[name])
        edit(d)
        result = mod.evaluate(injected={name: d})
        self.assertEqual(result["status"], "FAIL_CLOSED", result)
        self.assertIn(expected, result["errors"], result)
        self.assertEqual(result["p05_passed"], 0)
        self.assertEqual(result["g1_real_verified"], 0)
        self.assertFalse(result["real_mt4_observation_authorized"])
        self.assertFalse(result["ea_or_order_execution_authorized"])
        self.assertFalse(result["automatic_main_merge_authorized"])
        self.assertEqual(result["runtime_go_no_go"], "NO_GO")
        self.assertTrue(result["safety_hold_latched"])

    def test_combined_governance_gate_passes_only_mock_checks(self):
        result = mod.evaluate()
        self.assertEqual(result["status"], "PASS_GOVERNANCE_DESIGN_ONLY",
                         result)
        self.assertEqual(result["offline_governance_subchecks"], 6)
        self.assertEqual(result["synthetic_corruption_cases_included"], 70)
        self.assertEqual(result["errors"], [])
        self.assertFalse(result["actual_broker_evidence_verified"])

    def test_no_silently_added_authorization_keys_accepted(self):
        for name in mod.NAMES:
            with self.subTest(name=name):
                self.reject(
                    name,
                    lambda d: d.update(authorize_broker_order=True),
                    "P65_INVALID_INTEGRATION_RESULT:" +
                    str(mod.NAMES.index(name) + 1))

    def test_all_seven_legacy_and_five_new_checks_remain_offline(self):
        baseline = self.baselines["existing_mock_quality"]
        self.assertEqual(baseline["offline_subchecks"], 7)
        self.assertTrue(baseline["synthetic_data_only"])
        self.assertEqual(self.baselines["seventy_adversarial_inputs"]
                         ["synthetic_corruptions_checked"], 70)
        self.assertEqual(self.baselines["blank_g1_cross_ledgers"]
                         ["required_real_g1_rows"], 15)
        self.assertEqual(self.baselines["blocked_p05_dependencies"]
                         ["p05_real_accepted"], 0)

    def test_go_or_safety_latch_loss_refused_for_every_subcheck(self):
        for i, name in enumerate(mod.NAMES, 1):
            with self.subTest(name=name):
                self.reject(name, lambda d: d.update(
                    runtime_go_no_go="GO"),
                    "P65_INVALID_INTEGRATION_RESULT:" + str(i))
                self.reject(name, lambda d: d.update(
                    safety_hold_latched=False),
                    "P65_INVALID_INTEGRATION_RESULT:" + str(i))

    def test_fake_p05_acceptance_never_promotes_runtime(self):
        self.reject("blocked_p05_dependencies",
                    lambda d: d.update(p05_real_accepted=1),
                    "P65_FALSE_ACCEPTANCE_COUNTER:6")
        self.reject("blank_g1_cross_ledgers",
                    lambda d: d.update(real_g1_verified=15),
                    "P65_FALSE_ACCEPTANCE_COUNTER:4")

    def test_changed_coverage_counters_fail_closed(self):
        self.reject("seventy_adversarial_inputs",
                    lambda d: d.update(synthetic_corruptions_checked=69),
                    "P65_TEST_COVERAGE_COUNT_DRIFT:5")
        self.reject("offline_q109_traces",
                    lambda d: d.update(minimum_tracked_synthetic_sources=40),
                    "P65_TEST_COVERAGE_COUNT_DRIFT:3")

    def test_real_approval_or_mt4_observation_injection_rejected(self):
        self.reject("blocked_p05_dependencies",
                    lambda d: d.update(real_mt4_observation_authorized=True),
                    "P65_FORGED_REAL_WORLD_AUTHORITY:6")
        self.reject("existing_mock_quality",
                    lambda d: d.update(real_account_evidence_verified=True),
                    "P65_FORGED_REAL_WORLD_AUTHORITY:1")

    def test_local_storage_scope_cannot_be_silently_changed(self):
        self.reject("blocked_p05_dependencies",
                    lambda d: d.update(
                        owner_storage_accepted_for_offline_planning=False),
                    "P65_OWNER_OFFLINE_STORAGE_SCOPE_DRIFT")

    def test_unknown_child_or_private_values_are_not_returned(self):
        result = mod.evaluate(injected={"unknown_secret": "PRIVATE_CANARY_65"})
        self.assertEqual(result["status"], "FAIL_CLOSED")
        self.assertIn("P65_UNKNOWN_OR_PRIVATE_RESULT_INJECTION",
                      result["errors"])
        self.assertNotIn("PRIVATE_CANARY_65", str(result))

    def test_final_gate_does_not_authorize_auto_merge(self):
        outcome = mod.evaluate()
        self.assertFalse(outcome["automatic_main_merge_authorized"])
        self.assertFalse(outcome["ea_or_order_execution_authorized"])
        self.assertFalse(outcome["real_mt4_observation_authorized"])
        self.assertEqual(outcome["runtime_go_no_go"], "NO_GO")


if __name__ == "__main__":
    unittest.main()
