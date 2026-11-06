"""Combined offline source/intake/dependency QA is not MT4 or trade consent."""
from __future__ import annotations

import copy
import unittest

from scripts import risk_3p_60_offline_ingress_quality_gate as mod


class CombinedIngressQATests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.baselines = dict(zip(mod.NAMES, mod._outputs()))

    def reject(self, name, modify, code):
        value = copy.deepcopy(self.baselines[name])
        modify(value)
        result = mod.evaluate(injected={name: value})
        self.assertEqual(result["status"], "FAIL_CLOSED", result)
        self.assertIn(code, result["errors"], result)
        self.assertEqual(result["p05_passed"], 0)
        self.assertFalse(result["human_p05_signoff"])
        self.assertFalse(result["real_mt4_access_authorized"])
        self.assertFalse(result["real_order_or_ea_action_authorized"])
        self.assertEqual(result["runtime_go_no_go"], "NO_GO")
        self.assertTrue(result["safety_hold_latched"])

    def test_combined_gate_has_seven_mock_and_spec_subchecks(self):
        r = mod.evaluate()
        self.assertEqual(r["status"], "PASS_COMBINED_OFFLINE_DESIGN_QA_ONLY", r)
        self.assertEqual(r["offline_subchecks"], 7)
        self.assertEqual(r["errors"], [])
        self.assertFalse(r["real_account_evidence_verified"])
        self.assertFalse(r["real_broker_or_mt4_read_performed"])
        self.assertFalse(r["main_automatic_merge_authorized"])

    def test_all_seven_expected_statuses_present_and_stopped(self):
        self.assertEqual(len(mod.NAMES), 7)
        self.assertEqual(len(set(mod.NAMES)), 7)
        for name, expected, result in zip(mod.NAMES, mod.EXPECTED,
                                          mod._outputs()):
            with self.subTest(name=name):
                self.assertEqual(result["status"], expected)
                self.assertEqual(result["errors"], [])
                self.assertEqual(result["runtime_go_no_go"], "NO_GO")

    def test_no_unknown_success_label_can_upgrade_p05(self):
        for i, name in enumerate(mod.NAMES, 1):
            with self.subTest(name=name):
                self.reject(name,
                            lambda d: d.update(status="REAL_BROKER_PASS"),
                            "P60_OFFLINE_CASE_UNTRUSTED:" + str(i))

    def test_no_stop_latch_release_accepted(self):
        for i, name in enumerate(mod.NAMES, 1):
            with self.subTest(name=name):
                self.reject(name,
                            lambda d: d.update(safety_hold_latched=False),
                            "P60_OFFLINE_CASE_UNTRUSTED:" + str(i))

    def test_real_source_and_mt4_permissions_not_accepted(self):
        self.reject("fictional_ingress",
                    lambda d: d.update(real_mt4_read_authorized=True),
                    "P60_REAL_WORLD_PERMISSION_FORGED:1")
        self.reject("static_boundary",
                    lambda d: d.update(full_runtime_isolation_proven=True),
                    "P60_REAL_WORLD_PERMISSION_FORGED:2")
        self.reject("fake_clocks",
                    lambda d: d.update(real_data_freshness_verified=True),
                    "P60_REAL_WORLD_PERMISSION_FORGED:3")
        self.reject("unsigned_future_handoff",
                    lambda d: d.update(real_mt4_access_authorized=True),
                    "P60_REAL_WORLD_PERMISSION_FORGED:7")

    def test_all_real_evidence_counters_forced_to_zero(self):
        self.reject("fictional_ingress",
                    lambda d: d.update(real_observation_count=1),
                    "P60_UNVERIFIED_COUNT_PROMOTED:1")
        self.reject("unsigned_dependency_dag",
                    lambda d: d.update(p05_real_accepted=8),
                    "P60_UNVERIFIED_COUNT_PROMOTED:5")
        self.reject("unsigned_future_handoff",
                    lambda d: d.update(g1_real_verified=15),
                    "P60_UNVERIFIED_COUNT_PROMOTED:7")

    def test_malformed_or_private_injected_cases_rejected_without_echo(self):
        r = mod.evaluate(injected={"private_account": "PRIVATE_CANARY_60"})
        self.assertEqual(r["status"], "FAIL_CLOSED")
        self.assertIn("P60_UNAUTHORIZED_OR_PRIVATE_CASE_INSERTION", r["errors"])
        self.assertNotIn("PRIVATE_CANARY_60", str(r))
        for x in (None, [], "PASSWORD", True):
            result = mod.evaluate(injected={"fictional_ingress": x})
            self.assertEqual(result["status"], "FAIL_CLOSED")
            self.assertEqual(result["runtime_go_no_go"], "NO_GO")
            self.assertNotIn("PASSWORD", str(result))

    def test_quality_gate_does_not_generate_any_real_authorization(self):
        r = mod.evaluate()
        for key in ("real_account_evidence_verified", "human_p05_signoff",
                    "real_mt4_access_authorized",
                    "real_order_or_ea_action_authorized",
                    "main_automatic_merge_authorized"):
            self.assertIs(r[key], False)
        self.assertEqual(r["p05_passed"], 0)
        self.assertEqual(r["g1_real_verified"], 0)


if __name__ == "__main__":
    unittest.main()
