"""RISK-3P-223..228: synthetic P70 campaign unexpected exceptions deny safely."""
from __future__ import annotations

import unittest
from unittest.mock import patch

from scripts import risk_3p_70_fail_closed_campaign as p70


CANARY = "P70_FAKE_PRIVATE_CANARY_NOT_FOR_OUTPUT"
FAULTS = (RuntimeError, AssertionError, ZeroDivisionError,
          UnicodeError, LookupError, NotImplementedError)


class P70UnexpectedExceptions(unittest.TestCase):
    def assert_closed(self, output):
        self.assertEqual(output["status"], "FAIL_CLOSED")
        self.assertEqual(output["runtime_go_no_go"], "NO_GO")
        self.assertIs(output["safety_hold_latched"], True)
        self.assertIs(output["main_auto_merge_authorized"], False)
        self.assertIs(output["order_execution_authorized"], False)
        self.assertIs(output["real_mt4_access_authorized"], False)
        self.assertEqual(output["p05_passed"], 0)
        self.assertEqual(output["g1_real_verified"], 0)
        self.assertIn("P70_SYNTHETIC_CAMPAIGN_INPUT_INVALID", output["errors"])
        self.assertNotIn(CANARY, str(output))

    def test_223_normal_campaign_still_pure_mock_success(self):
        result = p70.campaign()
        self.assertEqual(result["status"], "PASS_TWENTY_NINE_OFFLINE_ATTACKS_ONLY")
        self.assertEqual(result["mock_failures_exercised"], 29)
        self.assertEqual(result["runtime_go_no_go"], "NO_GO")

    def test_224_source_ast_exceptions_do_not_escape(self):
        for exc in FAULTS:
            with self.subTest(exc=exc.__name__):
                with patch.object(p70.source, "audit", side_effect=exc(CANARY)):
                    self.assert_closed(p70.campaign())

    def test_225_import_time_audit_exception_denied(self):
        with patch.object(p70.importer, "audit", side_effect=RuntimeError(CANARY)):
            self.assert_closed(p70.campaign())

    def test_225_source_index_read_exception_denied(self):
        with patch.object(p70.index, "_read", side_effect=RuntimeError(CANARY)):
            self.assert_closed(p70.campaign())

    def test_226_source_index_validation_exception_denied(self):
        with patch.object(p70.index, "audit", side_effect=RuntimeError(CANARY)):
            self.assert_closed(p70.campaign())

    def test_227_governance_output_exception_denied(self):
        with patch.object(p70.prior, "_outputs", side_effect=RuntimeError(CANARY)):
            self.assert_closed(p70.campaign())

    def test_227_governance_validation_exception_denied(self):
        with patch.object(p70.prior, "evaluate", side_effect=RuntimeError(CANARY)):
            self.assert_closed(p70.campaign())

    def test_228_campaign_works_after_exception(self):
        with patch.object(p70.source, "audit", side_effect=RuntimeError(CANARY)):
            self.assert_closed(p70.campaign())
        self.assertEqual(p70.campaign()["status"],
                         "PASS_TWENTY_NINE_OFFLINE_ATTACKS_ONLY")


if __name__ == "__main__":
    unittest.main()
