"""RISK-3P-217..222: exceptions in offline mock subchecks always deny.

No network, MT4, EA, orders, broker access, approval updates or secret logs.
"""
from __future__ import annotations

import unittest
from unittest.mock import patch

from scripts import risk_3p_60_offline_ingress_quality_gate as p60
from scripts import risk_3p_65_integrated_offline_audit as p65

CANARY = "PRIVATE_CANARY_217_DO_NOT_ECHO"
FAULTS = (RuntimeError, AssertionError, ZeroDivisionError,
          UnicodeError, LookupError, NotImplementedError)


class OfflineUnexpectedExceptionTests(unittest.TestCase):
    def assert_denied(self, output, code):
        self.assertEqual(output["status"], "FAIL_CLOSED")
        self.assertEqual(output["runtime_go_no_go"], "NO_GO")
        self.assertIs(output["safety_hold_latched"], True)
        self.assertEqual(output["p05_passed"], 0)
        self.assertEqual(output["g1_real_verified"], 0)
        self.assertIn(code, output["errors"])
        self.assertNotIn(CANARY, str(output))

    def test_217_p60_normal_fixture_keeps_mock_only_pass(self):
        outcome = p60.evaluate()
        self.assertEqual(outcome["status"], "PASS_COMBINED_OFFLINE_DESIGN_QA_ONLY")
        self.assertEqual(outcome["runtime_go_no_go"], "NO_GO")

    def test_218_p65_normal_fixture_keeps_mock_only_pass(self):
        outcome = p65.evaluate()
        self.assertEqual(outcome["status"], "PASS_GOVERNANCE_DESIGN_ONLY")
        self.assertEqual(outcome["runtime_go_no_go"], "NO_GO")

    def test_219_p60_unexpected_exceptions_are_fixed_denials(self):
        for exc in FAULTS:
            with self.subTest(exception=exc.__name__):
                with patch.object(p60, "_outputs", side_effect=exc(CANARY)):
                    self.assert_denied(
                        p60.evaluate(), "P60_MISSING_OR_INVALID_OFFLINE_INPUT")

    def test_220_p65_unexpected_exceptions_are_fixed_denials(self):
        for exc in FAULTS:
            with self.subTest(exception=exc.__name__):
                with patch.object(p65, "_outputs", side_effect=exc(CANARY)):
                    self.assert_denied(
                        p65.evaluate(), "P65_OFFLINE_QUALITY_INPUT_INVALID")

    def test_221_p60_disables_all_real_permissions_on_exception(self):
        with patch.object(p60, "_outputs", side_effect=RuntimeError(CANARY)):
            output = p60.evaluate()
        for key in ("real_broker_or_mt4_read_performed",
                    "real_account_evidence_verified",
                    "human_p05_signoff", "real_mt4_access_authorized",
                    "real_order_or_ea_action_authorized",
                    "main_automatic_merge_authorized"):
            self.assertIs(output[key], False)

    def test_221_p65_disables_all_real_permissions_on_exception(self):
        with patch.object(p65, "_outputs", side_effect=RuntimeError(CANARY)):
            output = p65.evaluate()
        for key in ("actual_broker_evidence_verified",
                    "real_mt4_observation_authorized",
                    "ea_or_order_execution_authorized",
                    "automatic_main_merge_authorized"):
            self.assertIs(output[key], False)

    def test_222_p60_failure_does_not_poison_later_clean_call(self):
        with patch.object(p60, "_outputs", side_effect=RuntimeError(CANARY)):
            self.assertEqual(p60.evaluate()["status"], "FAIL_CLOSED")
        self.assertEqual(p60.evaluate()["status"],
                         "PASS_COMBINED_OFFLINE_DESIGN_QA_ONLY")

    def test_222_p65_failure_does_not_poison_later_clean_call(self):
        with patch.object(p65, "_outputs", side_effect=RuntimeError(CANARY)):
            self.assertEqual(p65.evaluate()["status"], "FAIL_CLOSED")
        self.assertEqual(p65.evaluate()["status"], "PASS_GOVERNANCE_DESIGN_ONLY")


if __name__ == "__main__":
    unittest.main()
