"""Allowlisted public diagnostics never contain injected private payload."""
from __future__ import annotations

import copy
import unittest

from scripts import risk_3p_58_safe_diagnostic_projection as mod


class PrivateFreeDiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.base = mod.fixture()

    def reject(self, mutate, code):
        d = copy.deepcopy(self.base)
        mutate(d)
        result = mod.summarize(d)
        self.assertEqual(result["status"], "FAIL_CLOSED", result)
        self.assertIn(code, result["errors"])
        self.assertFalse(result["submitted_values_echoed"])
        self.assertFalse(result["real_evidence_authenticated"])
        self.assertEqual(result["p05_passed"], 0)
        self.assertEqual(result["runtime_go_no_go"], "NO_GO")
        self.assertTrue(result["safety_hold_latched"])

    def test_baseline_summary_is_four_mock_checks_only(self):
        summary = mod.summarize(self.base)
        self.assertEqual(summary["status"], "PASS_SAFE_FAKE_SUMMARY_ONLY")
        self.assertEqual(summary["check_slots"], 4)
        self.assertEqual(summary["synthetic_checks_consistent"], 4)
        self.assertEqual(summary["errors"], [])
        self.assertFalse(summary["raw_evidence_collected"])
        self.assertFalse(summary["real_mt4_read_authorized"])

    def test_secret_extras_cannot_be_accepted(self):
        self.reject(lambda d: d.update(
            real_mt4_password="VERY_PRIVATE_CANARY_58"),
            "P58_UNKNOWN_ENVELOPE_OR_RAW_DATA_FIELD")
        self.reject(lambda d: d["checks"][0].update(
            real_account_number="VERY_PRIVATE_CANARY_58"),
            "P58_UNSAFE_OR_UNTRUSTED_RESULT:1")

    def test_raw_error_strings_never_echoed_back(self):
        self.reject(lambda d: d["checks"][0].update(
            raw_errors=["PRIVATE_CANARY_58", "C:\\Users\\Secret"]),
            "P58_UNSAFE_OR_UNTRUSTED_RESULT:1")
        d = copy.deepcopy(self.base)
        d["checks"][0]["raw_errors"] = ["PRIVATE_CANARY_58"]
        self.assertNotIn("PRIVATE_CANARY_58", str(mod.summarize(d)))

    def test_unfamiliar_or_reordered_checks_are_rejected(self):
        self.reject(lambda d: d["checks"].reverse(),
                    "P58_UNSAFE_OR_UNTRUSTED_RESULT:1")
        self.reject(lambda d: d["checks"][1].update(
            name="real_broker_evidence"),
            "P58_UNSAFE_OR_UNTRUSTED_RESULT:2")
        self.reject(lambda d: d["checks"].pop(),
                    "P58_EXPECTED_FOUR_FICTIONAL_CHECKS")

    def test_claimed_real_evidence_or_nonfictional_status_fails(self):
        self.reject(lambda d: d["checks"][2].update(
            real_evidence_verified=True),
            "P58_UNSAFE_OR_UNTRUSTED_RESULT:3")
        self.reject(lambda d: d["checks"][3].update(
            mock_status="REAL_OWNER_APPROVED"),
            "P58_UNSAFE_OR_UNTRUSTED_RESULT:4")

    def test_no_safety_permission_forgery_accepted(self):
        for key, original in mod.SAFETY.items():
            with self.subTest(key=key):
                value = not original if type(original) is bool else (
                    1 if type(original) is int else "GO")
                self.reject(lambda d, k=key, v=value:
                            d["safety"].update({k: v}),
                            "P58_SCOPE_OR_PERMISSION_SPOOF")

    def test_root_real_sources_and_logs_fail_closed(self):
        for v in (None, [], {}, "", 3, {"private": "CANARY_58"}):
            s = mod.summarize(v)
            self.assertEqual(s["status"], "FAIL_CLOSED")
            self.assertNotIn("CANARY_58", str(s))

    def test_invalid_check_types_do_not_echo_secrets(self):
        for v in (None, [], {}, 11, "PRIVATE_CANARY_58"):
            with self.subTest(kind=type(v).__name__):
                d = copy.deepcopy(self.base)
                d["checks"][0] = v
                result = mod.summarize(d)
                self.assertEqual(result["status"], "FAIL_CLOSED")
                self.assertNotIn("PRIVATE_CANARY_58", str(result))


if __name__ == "__main__":
    unittest.main()
