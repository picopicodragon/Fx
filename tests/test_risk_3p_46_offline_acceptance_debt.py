"""P05/G1 acceptance debt cross-check, no broker facts invented."""
from __future__ import annotations

import copy
import unittest

from scripts import audit_risk_3p_46_offline_acceptance_debt as mod


class P05AcceptanceDebtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.docs = {name: mod._read(mod.ROOT, name) for name in mod.FILES}

    def reject(self, path, change, expected):
        docs = copy.deepcopy(self.docs)
        change(docs[path])
        errors = mod.audit(injected=docs)
        self.assertIn(expected, errors, errors)
        snapshot = mod.snapshot(injected=docs)
        self.assertEqual(snapshot["status"], "FAIL_CLOSED")
        self.assertEqual(snapshot["p05_passed"], 0)
        self.assertFalse(snapshot["real_mt4_access_authorized"])
        self.assertEqual(snapshot["runtime_go_no_go"], "NO_GO")
        self.assertTrue(snapshot["safety_hold_latched"])

    def test_baseline_manifest_is_unsigned_and_no_go(self):
        self.assertEqual(mod.audit(), [])
        snapshot = mod.snapshot()
        self.assertEqual(snapshot["status"], "PASS_OFFLINE_DEBT_CONSISTENCY_ONLY")
        self.assertEqual(snapshot["p05_checks"], 8)
        self.assertEqual(snapshot["g1_fields"], 15)
        self.assertEqual(snapshot["g1_broker_verified"], 0)
        self.assertFalse(snapshot["human_p05_signoff"])
        self.assertFalse(snapshot["real_trading_authorized"])

    def test_all_eight_manifest_items_cannot_claim_acceptance(self):
        for n in range(8):
            with self.subTest(n=n):
                self.reject(mod.MANIFEST,
                            lambda p, i=n:
                            p["p05_items"][i].update(passed=True),
                            "P46_MANIFEST_ROW_WRONGLY_APPROVED:" + str(n + 1))

    def test_all_eight_source_items_cannot_claim_acceptance(self):
        for n in range(8):
            with self.subTest(n=n):
                self.reject(mod.P05,
                            lambda p, i=n:
                            p["p05_checks"][i].update(p05_accepted=True),
                            "P46_P05_SOURCE_WRONGLY_APPROVED:" + str(n + 1))

    def test_human_review_claim_without_independent_evidence_rejected(self):
        for n in range(8):
            with self.subTest(n=n):
                self.reject(mod.REVIEW,
                            lambda p, i=n:
                            p["items"][i].update(
                                human_specific_acceptance="SIGNED"),
                            "P46_REVIEW_OR_HUMAN_SIGNOFF_FALSE:" + str(n + 1))

    def test_matrix_cannot_promote_simulated_pass_to_real_proof(self):
        for n in range(8):
            with self.subTest(n=n):
                self.reject(mod.MATRIX,
                            lambda p, i=n:
                            p["checks"][i].update(
                                real_evidence_verified=True),
                            "P46_OFFLINE_MATRIX_FALSE_APPROVAL:" + str(n + 1))

    def test_p05_acceptance_does_not_inherit_storage_permission(self):
        self.reject(mod.P05,
                    lambda p: p["p05_checks"][5]
                    ["owner_accepted_storage_security_scope"].update(
                        accepted_for="REAL_MT4_LOG_COLLECTION"),
                    "P46_OWNER_STORAGE_ACCEPTANCE_OVEREXTENDED")
        self.reject(mod.P05,
                    lambda p: p["p05_checks"][5]
                    ["owner_accepted_storage_security_scope"].update(
                        real_mt4_session_or_data_collection_authorized=True),
                    "P46_OWNER_STORAGE_ACCEPTANCE_OVEREXTENDED")

    def test_global_safety_latch_and_p06_not_authorized(self):
        self.reject(mod.P05,
                    lambda p: p.update(p06_observation_authorized=True),
                    "P46_GLOBAL_P05_STOP_LOST")
        self.reject(mod.P05,
                    lambda p: p.update(safety_hold_latched=False),
                    "P46_GLOBAL_P05_STOP_LOST")
        self.reject(mod.REVIEW,
                    lambda p: p["safety"].update(p05_passed=1),
                    "P46_GLOBAL_P05_STOP_LOST")

    def test_all_g1_values_and_sources_must_remain_null(self):
        for i in (0, 7, 14):
            with self.subTest(i=i):
                self.reject(mod.G1,
                            lambda p, n=i:
                            p["g1_entries"][n].update(
                                observed_at_utc="SIM_FABRICATED"),
                            "P46_G1_UNVERIFIED_ROW_FILLED:" + str(i + 1))
        self.reject(mod.G1,
                    lambda p: p.update(required_items=20),
                    "P46_G1_EVIDENCE_COUNT_FALSE")

    def test_manifest_safety_cannot_be_forged(self):
        for key, value in mod.SAFETY.items():
            with self.subTest(key=key):
                if key == "owner_local_storage_accepted_for_offline_planning_only":
                    changed = False
                elif type(value) is bool:
                    changed = not value
                elif type(value) is int:
                    changed = value + 1
                else:
                    changed = "GO"
                self.reject(mod.MANIFEST,
                            lambda p, k=key, v=changed:
                            p["safety"].update({k: v}),
                            "P46_FAKE_HUMAN_APPROVAL_OR_RUNTIME_GO")

    def test_malformed_documents_and_privacy(self):
        docs = copy.deepcopy(self.docs)
        docs[mod.MANIFEST] = {"private_password": "CANARY_VALUE_46"}
        r = mod.snapshot(injected=docs)
        self.assertEqual(r["status"], "FAIL_CLOSED")
        self.assertNotIn("CANARY_VALUE_46", str(r))
        docs = copy.deepcopy(self.docs)
        docs.pop(mod.P05)
        self.assertIn("P46_INPUT_MISSING_OR_INVALID",
                      mod.audit(injected=docs))


if __name__ == "__main__":
    unittest.main()
