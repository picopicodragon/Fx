"""Human-only P05 signoff remains absent after mock merges or CI successes."""
from __future__ import annotations

import copy
import unittest

from scripts import risk_3p_51_mock_approval_separation as mod


class MockOwnerConsentTests(unittest.TestCase):
    def setUp(self):
        self.base = mod.fixture()

    def refuse(self, change, code):
        value = copy.deepcopy(self.base)
        change(value)
        state = mod.evaluate(value)
        self.assertEqual(state["status"], "FAIL_CLOSED", state)
        self.assertIn(code, state["errors"], state)
        self.assertEqual(state["p05_passed"], 0)
        self.assertFalse(state["owner_p05_approval_recorded"])
        self.assertFalse(state["real_mt4_read_authorized"])
        self.assertFalse(state["real_order_execution_authorized"])
        self.assertEqual(state["runtime_go_no_go"], "NO_GO")
        self.assertTrue(state["safety_hold_latched"])

    def test_mock_pr_and_ci_success_is_not_an_approval(self):
        r = mod.evaluate(self.base)
        self.assertEqual(r["status"], "PASS_NO_REAL_APPROVAL_ONLY")
        self.assertEqual(r["p05_items_still_unsigned"], 8)
        self.assertFalse(r["owner_p05_approval_recorded"])
        self.assertFalse(r["phase1_approved"])

    def test_every_p05_item_requires_separate_real_proof_and_human_signoff(self):
        for i in range(8):
            with self.subTest(i=i):
                self.refuse(lambda d, n=i: d["unsigned_p05"][n].update(
                    explicit_owner_signoff=True),
                    "P51_OWNER_OR_BROKER_APPROVAL_FORGED:" + str(i + 1))
                self.refuse(lambda d, n=i: d["unsigned_p05"][n].update(
                    real_evidence_verified=True),
                    "P51_OWNER_OR_BROKER_APPROVAL_FORGED:" + str(i + 1))

    def test_storage_permission_never_implies_mt4_data_access(self):
        self.assertTrue(
            self.base["observations"][
                "owner_local_storage_accepted_for_offline_only"])
        self.refuse(
            lambda d: d["unsigned_p05"][5].update(
                real_mt4_observation_authorized=True),
            "P51_OWNER_OR_BROKER_APPROVAL_FORGED:6")

    def test_no_safety_flags_can_be_forged(self):
        for key, original in mod.SAFETY.items():
            with self.subTest(key=key):
                changed = (not original if type(original) is bool else
                           (1 if type(original) is int else "GO"))
                self.refuse(lambda d, k=key, v=changed:
                            d["safety"].update({k: v}),
                            "P51_STOP_OR_P05_AUTHORIZATION_FORGED")

    def test_incomplete_or_misordered_p05_rows_rejected(self):
        self.refuse(lambda d: d["unsigned_p05"].pop(),
                    "P51_EIGHT_UNSIGNED_P05_ROWS_REQUIRED")
        self.refuse(lambda d: d["unsigned_p05"].reverse(),
                    "P51_OWNER_OR_BROKER_APPROVAL_FORGED:1")

    def test_no_secret_account_fields_accepted(self):
        self.refuse(lambda d: d.update(
            local_mt4_login_id="CANARY_51"),
            "P51_INVALID_OR_UNEXPECTED_PRIVATE_FIELDS")
        self.refuse(lambda d: d["unsigned_p05"][1].update(
            personal_account_number="CANARY_51"),
            "P51_OWNER_OR_BROKER_APPROVAL_FORGED:2")

    def test_changing_mock_ci_status_is_not_authority(self):
        self.refuse(lambda d: d["observations"].update(
            simulated_ci_passed=False),
            "P51_PRIOR_REPORT_OR_SYNTHETIC_RESULT_RELABELED")
        self.refuse(lambda d: d.update(classification="LIVE_SIGNED_REVIEW"),
                    "P51_REAL_PERMISSION_SCOPE_SPOOFED")

    def test_malformed_inputs_fail_without_echoing_secret(self):
        for value in (None, [], 7, {}, True, {"password": "CANARY_51"}):
            result = mod.evaluate(value)
            self.assertEqual(result["status"], "FAIL_CLOSED")
            self.assertNotIn("CANARY_51", str(result))


if __name__ == "__main__":
    unittest.main()
