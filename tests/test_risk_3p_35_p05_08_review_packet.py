"""P05-08 unsigned review packet: block any forged approval or market evidence."""
from __future__ import annotations

import copy
import unittest

from scripts import audit_risk_3p_35_p05_08_review_packet as mod


class P0508UnsignedReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.docs = {name: mod._read(mod.ROOT, name) for name in mod.PATHS}

    def reject(self, path, mutate, expected):
        data = copy.deepcopy(self.docs)
        mutate(data[path])
        errors = mod.audit(injected=data)
        self.assertIn(expected, errors, errors)
        result = mod.snapshot(injected=data)
        self.assertEqual(result["status"], "FAIL_CLOSED")
        self.assertEqual(result["accepted_p05_items"], 0)
        self.assertFalse(result["human_p05_signoff_recorded"])
        self.assertFalse(result["p06_observation_authorized"])
        self.assertEqual(result["runtime_go_no_go"], "NO_GO")
        self.assertTrue(result["safety_hold_latched"])

    def test_baseline_is_unsigned_eight_item_review_packet(self):
        self.assertEqual(mod.audit(), [])
        packet = self.docs[mod.PACKET]
        self.assertEqual(len(packet["items"]), 8)
        self.assertEqual([x["check_id"] for x in packet["items"]],
                         [f"P05-{i:02d}" for i in range(1, 9)])
        self.assertEqual(packet["safety"], mod.SAFETY)
        result = mod.snapshot()
        self.assertEqual(result["status"], "PASS_UNSIGNED_REVIEW_DRAFT_ONLY")
        self.assertEqual(result["required_p05_items"], 8)
        self.assertEqual(result["accepted_p05_items"], 0)
        self.assertEqual(result["real_g1_fields_verified"], 0)
        self.assertFalse(result["order_authorized"])
        self.assertFalse(result["p06_observation_authorized"])
        self.assertFalse(result["real_mt4_session_authorized"])

    def test_review_packet_rejects_all_implied_p05_and_phase_signoff(self):
        modifications = (
            ("p05_passed", 1),
            ("real_broker_g1_items_verified", 15),
            ("real_mt4_account_session_authorized", True),
            ("observation_or_script_authorized", True),
            ("sensitive_data_read_or_upload_authorized", True),
            ("ea_or_order_changes_authorized", True),
            ("p06_authorized", True),
            ("broker_order_or_position_absence_verified", True),
            ("human_p05_signoff_reference", "FAKE_OWNER_APPROVAL"),
            ("human_phase_1_signoff_reference", "FAKE_PHASE_APPROVAL"),
            ("main_auto_merge_allowed", True),
            ("runtime_go_no_go", "GO"),
            ("safety_hold_latched", False),
        )
        for key, value in modifications:
            with self.subTest(key=key):
                self.reject(mod.PACKET,
                            lambda d, k=key, v=value:
                            d["safety"].update({k: v}),
                            "P35_SIGNOFF_OR_RUNTIME_PERMISSION_FORGED")

    def test_p05_status_rows_remain_pending_and_never_accept_synthetic_pass(self):
        self.reject(mod.PACKET,
                    lambda d: d["items"][0].update(
                        human_specific_acceptance="APPROVED"),
                    "P35_ITEM_FALSELY_VERIFIED_OR_SIGNED:1")
        self.reject(mod.PACKET,
                    lambda d: d["items"][5].update(item_accepted=True),
                    "P35_ITEM_FALSELY_VERIFIED_OR_SIGNED:6")
        self.reject(mod.PACKET,
                    lambda d: d["items"][6].update(
                        independent_environment_evidence="VERIFIED"),
                    "P35_ITEM_FALSELY_VERIFIED_OR_SIGNED:7")
        self.reject(mod.PACKET,
                    lambda d: d["items"][7].update(
                        current_summary_code="P05_PASSED"),
                    "P35_ITEM_FALSELY_VERIFIED_OR_SIGNED:8")

    def test_packet_cannot_embed_private_logs_account_ids_or_change_scope(self):
        self.reject(mod.PACKET,
                    lambda d: d["items"][1].update(
                        account_number="SECRET_ACCOUNT_ID"),
                    "P35_ITEM_FALSELY_VERIFIED_OR_SIGNED:2")
        self.reject(mod.PACKET,
                    lambda d: d.update(
                        windows_path="PRIVATE_PROFILE_PATH"),
                    "P35_UNAUTHORIZED_PACKET_METADATA_OR_FIELDS")
        self.reject(mod.PACKET,
                    lambda d: d["items"].pop(),
                    "P35_EIGHT_UNSIGNED_CHECKS_REQUIRED")
        self.reject(mod.PACKET,
                    lambda d: d["items"].reverse(),
                    "P35_ITEM_FALSELY_VERIFIED_OR_SIGNED:1")
        self.reject(mod.PACKET,
                    lambda d: d.update(
                        scope="APPROVED_MT4_REVIEW"),
                    "P35_UNAUTHORIZED_PACKET_METADATA_OR_FIELDS")

    def test_p05_human_or_execution_permission_cannot_be_invented(self):
        self.reject(mod.P05,
                    lambda d: d.update(
                        p05_human_safety_signoff=True),
                    "P35_P05_INDEPENDENT_SIGNOFF_STILL_REQUIRED")
        self.reject(mod.P05,
                    lambda d: d.update(
                        p06_observation_authorized=True),
                    "P35_P05_INDEPENDENT_SIGNOFF_STILL_REQUIRED")
        self.reject(mod.P05,
                    lambda d: d["p05_checks"][7].update(
                        p05_accepted=True),
                    "P35_P05_SOURCE_ITEM_UNJUSTIFIABLY_PASSED:8")
        self.reject(mod.P05,
                    lambda d: d["p05_checks"][5]
                    ["owner_accepted_storage_security_scope"].update(
                        accepted_for="UNRESTRICTED_EVIDENCE_COLLECTION"),
                    "P35_OWNER_STORAGE_ACCEPTANCE_OUT_OF_SCOPE")

    def test_g1_source_must_keep_all_15_real_values_null(self):
        self.reject(mod.G1,
                    lambda d: d["g1_entries"][0].update(
                        value="0.01"),
                    "P35_G1_PROVENANCE_NOT_EMPTY:1")
        self.reject(mod.G1,
                    lambda d: d["g1_entries"][14].update(
                        observed_at_utc="2026-11-06T00:00:00Z"),
                    "P35_G1_PROVENANCE_NOT_EMPTY:15")
        self.reject(mod.G1,
                    lambda d: d.update(required_items=20),
                    "P35_NO_VERIFIED_G1_EVIDENCE_ALLOWED")
        self.reject(mod.G1,
                    lambda d: d["safety"].update(
                        real_mt4_data_collected=True),
                    "P35_NO_VERIFIED_G1_EVIDENCE_ALLOWED")

    def test_malformed_and_secret_inputs_are_fail_closed_without_leaks(self):
        self.reject(mod.PACKET,
                    lambda d: d["items"][0].update(
                        private_log_or_account_id_collected=True),
                    "P35_ITEM_FALSELY_VERIFIED_OR_SIGNED:1")
        invalid = copy.deepcopy(self.docs)
        invalid[mod.PACKET] = {"secret": "PRIVATE_ACCOUNT_PASSWORD"}
        error_list = mod.audit(injected=invalid)
        self.assertEqual(mod.snapshot(injected=invalid)["status"], "FAIL_CLOSED")
        self.assertNotIn("PRIVATE_ACCOUNT_PASSWORD", str(error_list))
        invalid = copy.deepcopy(self.docs)
        invalid[mod.PACKET] = []
        self.assertEqual(mod.audit(injected=invalid),
                         ["P35_INVALID_REVIEW_PACKET_INPUT"])


if __name__ == "__main__":
    unittest.main()
