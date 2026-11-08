"""RISK-3P-235..240: unexpected synthetic P64 faults fail closed.

No actual market data, terminal, broker, orders, or secrets are accessed.
"""
from __future__ import annotations

import unittest
from unittest.mock import patch

from scripts import risk_3p_64_adversarial_consistency_campaign as p64

CANARY = "P64_FAKE_SECRET_CANARY_NEVER_ECHO"
EXCEPTIONS = (RuntimeError, AssertionError, ZeroDivisionError,
              UnicodeError, LookupError, NotImplementedError)


class SyntheticCampaignBoundaryTests(unittest.TestCase):
    def assert_closed(self, report):
        self.assertEqual(report["status"], "FAIL_CLOSED", report)
        self.assertEqual(report["runtime_go_no_go"], "NO_GO")
        self.assertIs(report["safety_hold_latched"], True)
        self.assertEqual(report["p05_passed"], 0)
        self.assertEqual(report["g1_real_verified"], 0)
        self.assertIs(report["actual_broker_evidence_received"], False)
        self.assertIs(report["human_signoff_verified"], False)
        self.assertIs(report["real_mt4_access_authorized"], False)
        self.assertIs(report["order_execution_authorized"], False)
        self.assertIn("P64_OFFLINE_ADVERSARIAL_HARNESS_FAILURE", report["errors"])
        self.assertNotIn(CANARY, str(report))

    def test_235_normal_baseline_preserves_offline_no_go(self):
        report = p64.campaign()
        self.assertEqual(report["status"], "PASS_SEVENTY_MOCK_CORRUPTIONS_ONLY", report)
        self.assertEqual(report["runtime_go_no_go"], "NO_GO")
        self.assertEqual(report["synthetic_corruptions_checked"], 70)

    def test_236_child_snapshot_unexpected_errors(self):
        for error in EXCEPTIONS:
            with self.subTest(error=error.__name__):
                with patch.object(p64.quality, "_outputs", side_effect=error(CANARY)):
                    self.assert_closed(p64.campaign())

    def test_237_mutation_stage_unexpected_error(self):
        with patch.object(p64, "mutate", side_effect=RuntimeError(CANARY)):
            self.assert_closed(p64.campaign())

    def test_238_strict_contract_unexpected_error(self):
        with patch.object(p64.strict, "check", side_effect=AssertionError(CANARY)):
            self.assert_closed(p64.campaign())

    def test_239_composite_gate_unexpected_error(self):
        with patch.object(p64.quality, "evaluate", side_effect=RuntimeError(CANARY)):
            self.assert_closed(p64.campaign())

    def test_240_failure_followed_by_clean_offline_run(self):
        with patch.object(p64.quality, "_outputs", side_effect=RuntimeError(CANARY)):
            self.assert_closed(p64.campaign())
        self.assertEqual(p64.campaign()["status"], "PASS_SEVENTY_MOCK_CORRUPTIONS_ONLY")


if __name__ == "__main__":
    unittest.main()
