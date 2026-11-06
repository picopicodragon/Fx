"""Twenty-nine in-memory attacks against documented offline-only gates."""
from __future__ import annotations

import unittest

from scripts import risk_3p_70_fail_closed_campaign as mod
from scripts import audit_risk_3p_56_static_offline_boundary as static
from scripts import audit_risk_3p_69_import_time_safety as importer


class OfflineAttackCampaignTests(unittest.TestCase):
    def test_29_scenarios_reject_unknown_permissions(self):
        r = mod.campaign()
        self.assertEqual(r["status"],
                         "PASS_TWENTY_NINE_OFFLINE_ATTACKS_ONLY", r)
        self.assertEqual(r["mock_failures_exercised"], 29)
        self.assertEqual(r["pure_modules_reviewed"], 6)
        self.assertEqual(r["errors"], [])
        self.assertFalse(r["real_source_security_proven"])
        self.assertFalse(r["real_broker_evidence_verified"])
        self.assertFalse(r["real_mt4_access_authorized"])
        self.assertEqual(r["runtime_go_no_go"], "NO_GO")

    def test_private_canary_never_emitted_by_campaign(self):
        self.assertNotIn(mod.CANARY, str(mod.campaign()))

    def test_each_pure_target_blocks_broker_import_and_side_effect(self):
        self.assertEqual(static.TARGETS, importer.TARGETS)
        for name in static.TARGETS:
            with self.subTest(name=name):
                self.assertTrue(static.audit(overrides={
                    name:"from scripts import unreviewed_broker_adapter"}))
                self.assertTrue(importer.audit(overrides={
                    name:"connect_to_mt4()"}))

    def test_campaign_is_not_consent_or_merge_policy(self):
        r = mod.campaign()
        self.assertEqual(r["p05_passed"], 0)
        self.assertEqual(r["g1_real_verified"], 0)
        self.assertFalse(r["main_auto_merge_authorized"])
        self.assertFalse(r["order_execution_authorized"])
        self.assertTrue(r["safety_hold_latched"])


if __name__ == "__main__":
    unittest.main()
