"""P05 8-item offline cross-reference audit and negative safety scenarios."""
from __future__ import annotations

import copy
import unittest

from scripts import audit_risk_3p_41_p05_offline_gate_matrix as mod


class BlockedP05MatrixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.docs = {name: mod._read(mod.ROOT, name) for name in mod.FILES}

    def reject(self, file, change, expected):
        docs = copy.deepcopy(self.docs)
        change(docs[file])
        errors = mod.audit(injected=docs)
        self.assertIn(expected, errors, errors)
        result = mod.snapshot(injected=docs)
        self.assertEqual(result["status"], "FAIL_CLOSED")
        self.assertEqual(result["real_p05_checks_accepted"], 0)
        self.assertFalse(result["human_p05_signoff"])
        self.assertFalse(result["trading_authorized"])
        self.assertEqual(result["runtime_go_no_go"], "NO_GO")
        self.assertTrue(result["safety_hold_latched"])

    def test_baseline_eight_gates_remain_blocked_even_with_synthetic_pass(self):
        self.assertEqual(mod.audit(), [])
        result = mod.snapshot()
        self.assertEqual(result["status"], "PASS_OFFLINE_MATRIX_ONLY")
        self.assertEqual(result["p05_checks_required"], 8)
        self.assertEqual(result["real_g1_verified"], 0)
        self.assertFalse(result["mt4_session_authorized"])

    def test_each_p05_gate_cannot_be_falsely_marked_accepted(self):
        for i in range(8):
            with self.subTest(check=i + 1):
                self.reject(
                    mod.P05,
                    lambda p, n=i: p["p05_checks"][n].update(
                        p05_accepted=True),
                    "P41_P05_SOURCE_FALSE_ACCEPTANCE:" + str(i + 1))

    def test_each_review_item_cannot_be_falsely_signed(self):
        for i in range(8):
            with self.subTest(check=i + 1):
                self.reject(
                    mod.REVIEW,
                    lambda p, n=i: p["items"][n].update(
                        human_specific_acceptance="SIGNED"),
                    "P41_REVIEW_HUMAN_SIGNATURE_FORGED:" + str(i + 1))

    def test_each_matrix_record_cannot_be_promoted_by_synthetic_test(self):
        for i in range(8):
            with self.subTest(check=i + 1):
                self.reject(
                    mod.MATRIX,
                    lambda p, n=i: p["checks"][n].update(
                        simulator_pass_means_real_clearance=True),
                    "P41_OFFLINE_REVIEW_ROW_PROMOTED:" + str(i + 1))

    def test_all_runtime_and_owner_permits_remain_explicitly_false(self):
        for key, original in mod.CONTROLS.items():
            with self.subTest(key=key):
                new = (not original if type(original) is bool
                       else (1 if type(original) is int else
                             ("GO" if key == "runtime_go_no_go"
                              else "UNAUTHORIZED")))
                self.reject(
                    mod.MATRIX,
                    lambda p, k=key, v=new:
                    p["controls"].update({k: v}),
                    "P41_REAL_P05_OR_ORDER_PERMISSION_FORGED")

    def test_global_owner_review_is_required_before_terminal_actions(self):
        self.reject(mod.P05,
                    lambda p: p.update(
                        p06_observation_authorized=True),
                    "P41_GLOBAL_SAFE_STOP_UNVERIFIED")
        self.reject(mod.P05,
                    lambda p: p.update(
                        safety_hold_latched=False),
                    "P41_GLOBAL_SAFE_STOP_UNVERIFIED")
        self.reject(mod.REVIEW,
                    lambda p: p.update(
                        decision="OWNER_APPROVED_ALL_P05"),
                    "P41_GLOBAL_SAFE_STOP_UNVERIFIED")

    def test_unverified_g1_remains_null_even_with_all_synthetic_gates_pass(self):
        self.reject(mod.G1,
                    lambda p: p["g1_entries"][0].update(value="0.01"),
                    "P41_UNAUTHORIZED_G1_EVIDENCE_PROMOTION")
        self.reject(mod.G1,
                    lambda p: p["safety"].update(
                        independently_verified_g1_items=1),
                    "P41_G1_VERIFIED_DATA_NOT_AVAILABLE")

    def test_owner_storage_decision_cannot_be_promoted_to_live_read(self):
        self.reject(mod.MATRIX,
                    lambda p: p["checks"][5].update(
                        real_evidence_verified=True),
                    "P41_OFFLINE_REVIEW_ROW_PROMOTED:6")
        self.reject(mod.P05,
                    lambda p: p["p05_checks"][5].update(
                        safe_to_proceed=True),
                    "P41_P05_SOURCE_FALSE_ACCEPTANCE:6")

    def test_sensitive_content_never_appears_in_failure_reports(self):
        self.reject(mod.MATRIX,
                    lambda p: p.update(
                        private_windows_path="SENSITIVE_PATH"),
                    "P41_OWNER_EVIDENCE_SCOPE_DRIFT")
        docs = copy.deepcopy(self.docs)
        docs[mod.MATRIX] = {"secret": "MUST_NOT_ECHO"}
        result = mod.snapshot(injected=docs)
        self.assertEqual(result["status"], "FAIL_CLOSED")
        self.assertNotIn("MUST_NOT_ECHO", str(result))

    def test_invalid_and_missing_document_fail_closed(self):
        docs = copy.deepcopy(self.docs)
        docs.pop(mod.P05)
        self.assertIn("P41_MISSING_OR_MALFORMED_INPUT",
                      mod.audit(injected=docs))
        docs = copy.deepcopy(self.docs)
        docs[mod.REVIEW] = []
        self.assertEqual(mod.audit(injected=docs),
                         ["P41_INVALID_OFFLINE_DOCUMENT"])


if __name__ == "__main__":
    unittest.main()
