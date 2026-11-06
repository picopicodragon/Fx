"""P05 in-memory 16-fault campaign regression, no MT4 nor account files."""
from __future__ import annotations

import copy
import unittest

from scripts import risk_3p_42_synthetic_fault_campaign as campaign
from scripts import risk_3p_40_synthetic_p05_interlock_matrix as matrix


class OfflineFaultCampaignTests(unittest.TestCase):
    def test_campaign_has_sixteen_unique_stable_faults(self):
        self.assertEqual(len(campaign.FAULTS), 16)
        self.assertEqual(
            [name for name, _, _ in campaign.FAULTS],
            [f"P42-{i:02d}" for i in range(1, 17)])

    def test_campaign_pass_means_simulation_only_no_mt4_permission(self):
        result = campaign.campaign()
        self.assertEqual(result["status"],
                         "PASS_SYNTHETIC_FAULT_CAMPAIGN_ONLY")
        self.assertEqual(result["simulated_baselines"], 2)
        self.assertEqual(result["simulated_faults_exercised"], 16)
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["real_p05_checks_passed"], 0)
        self.assertEqual(result["real_g1_fields_verified"], 0)
        self.assertFalse(result["real_mt4_access_authorized"])
        self.assertFalse(result["order_authorized"])
        self.assertEqual(result["runtime_go_no_go"], "NO_GO")
        self.assertTrue(result["safety_hold_latched"])

    def test_each_fault_individually_refuses_misleading_clearance(self):
        for name, expected, mutate in campaign.FAULTS:
            with self.subTest(scenario=name):
                package = copy.deepcopy(matrix.fixture())
                mutate(package)
                result = matrix.evaluate(package)
                self.assertEqual(result["status"], "FAIL_CLOSED")
                self.assertIn(expected, result["errors"])
                self.assertEqual(result["real_p05_passed"], 0)
                self.assertFalse(result["real_mt4_read_authorized"])
                self.assertFalse(result["human_p05_08_signoff"])
                self.assertFalse(result["broker_order_or_ea_action_authorized"])
                self.assertEqual(result["runtime_go_no_go"], "NO_GO")

    def test_campaign_never_exposes_private_identifier_fixture(self):
        summary = str(campaign.campaign())
        self.assertNotIn("PRIVATE_ACCOUNT_IDENTIFIER_NOT_TO_LEAK", summary)
        self.assertNotIn("C:\\Users\\", summary)

    def test_simulation_with_exposure_is_not_flat_broker_proof(self):
        r = matrix.evaluate(matrix.fixture(simulated_exposure=True))
        self.assertEqual(r["status"], "PASS_SYNTHETIC_MATRIX_ONLY")
        self.assertFalse(r["real_broker_orders_absent_verified"])
        self.assertEqual(r["runtime_go_no_go"], "NO_GO")


if __name__ == "__main__":
    unittest.main()
