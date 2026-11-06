"""Unsigned 3x5 future evidence handoff never becomes actual MT4 authority."""
from __future__ import annotations

import copy
import unittest

from scripts import audit_risk_3p_53_54_future_handoff as mod


class FutureEvidenceHandoffTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.docs = {name: mod._read(mod.ROOT, name) for name in mod.PATHS}

    def refuse(self, path, mutate, code):
        data = copy.deepcopy(self.docs)
        mutate(data[path])
        state = mod.snapshot(injected=data)
        self.assertEqual(state["status"], "FAIL_CLOSED", state)
        self.assertIn(code, state["errors"])
        self.assertEqual(state["p05_passed"], 0)
        self.assertEqual(state["g1_real_verified"], 0)
        self.assertFalse(state["real_mt4_access_authorized"])
        self.assertFalse(state["human_p05_signoff"])
        self.assertEqual(state["runtime_go_no_go"], "NO_GO")
        self.assertTrue(state["safety_hold_latched"])

    def test_baseline_handoff_is_8_prerequisites_and_15_null_real_fields(self):
        state = mod.snapshot()
        self.assertEqual(state["status"], "PASS_UNSIGNED_HANDOFF_SCHEMA_ONLY")
        self.assertEqual(state["p05_required"], 8)
        self.assertEqual(state["g1_required"], 15)
        self.assertFalse(state["actual_evidence_received"])
        self.assertFalse(state["real_broker_independence_verified"])
        self.assertEqual(state["errors"], [])
        handoff = self.docs[mod.HANDOFF]
        self.assertEqual(len(handoff["g1_rows"]), 15)
        self.assertEqual(len(handoff["required_before_real_observation"]), 8)

    def test_each_real_g1_field_cannot_be_fabricated(self):
        for i in range(15):
            with self.subTest(i=i):
                self.refuse(mod.HANDOFF,
                            lambda d, n=i: d["g1_rows"][n].update(
                                real_broker_value="0.01"),
                            "P53_REAL_OBSERVATION_FORGED:" + str(i + 1))

    def test_real_references_or_fake_time_cannot_be_imported(self):
        self.refuse(mod.HANDOFF,
                    lambda d: d["g1_rows"][0].update(
                        real_primary_source_ref="SIM_SOURCE"),
                    "P53_REAL_OBSERVATION_FORGED:1")
        self.refuse(mod.HANDOFF,
                    lambda d: d["g1_rows"][14].update(
                        real_observation_utc="SIM_2000-01-01T00:00:00Z"),
                    "P53_REAL_OBSERVATION_FORGED:15")
        self.refuse(mod.HANDOFF,
                    lambda d: d["g1_rows"][7].update(verified=True),
                    "P53_REAL_OBSERVATION_FORGED:8")

    def test_perm_flags_cannot_upgrade_broker_session_or_owner_consent(self):
        for key, original in mod.PERMISSION.items():
            with self.subTest(key=key):
                value = (not original if type(original) is bool
                         else (1 if type(original) is int else "GO"))
                self.refuse(mod.HANDOFF,
                            lambda d, k=key, v=value:
                            d["permission"].update({k: v}),
                            "P53_REAL_MT4_OR_P05_APPROVAL_FORGED")

    def test_absent_human_prerequisite_cannot_be_silently_deleted(self):
        self.refuse(mod.HANDOFF,
                    lambda d: d["required_before_real_observation"].pop(),
                    "P53_REAL_EVIDENCE_HANDOFF_SCOPE_DRIFT")
        self.refuse(mod.HANDOFF,
                    lambda d: d.update(
                        owner_storage_decision="FULL_REAL_MT4_APPROVAL"),
                    "P53_REAL_EVIDENCE_HANDOFF_SCOPE_DRIFT")

    def test_public_p05_source_signoff_not_inherited_from_pr_merge(self):
        self.refuse(mod.P05,
                    lambda d: d.update(
                        p05_human_safety_signoff=True),
                    "P53_P05_SOURCE_NOT_IN_SAFETY_HOLD")
        self.refuse(mod.P05,
                    lambda d: d.update(p06_observation_authorized=True),
                    "P53_P05_SOURCE_NOT_IN_SAFETY_HOLD")

    def test_other_sources_cannot_claim_real_broker_proof(self):
        self.refuse(mod.G1,
                    lambda d: d["safety"].update(
                        independently_verified_g1_items=15),
                    "P53_G1_SOURCE_REAL_PROOF_MISSING_OR_FALSE")
        self.refuse(mod.DEBT,
                    lambda d: d["safety"].update(p05_passed=8),
                    "P53_HISTORICAL_APPROVAL_DEBT_NOT_PRESERVED")
        self.refuse(mod.ORDERS,
                    lambda d: d["environment"].update(
                        real_order_positions_verified=True),
                    "P53_REAL_BROKER_ORDER_PROOF_MISREPRESENTED")

    def test_unknown_fields_and_broker_credentials_are_forbidden(self):
        self.refuse(mod.HANDOFF,
                    lambda d: d.update(
                        real_mt4_password="PRIVATE_CANARY_53"),
                    "P53_REAL_EVIDENCE_HANDOFF_SCOPE_DRIFT")
        self.refuse(mod.HANDOFF,
                    lambda d: d["g1_rows"][0].update(
                        broker_account_number="PRIVATE_CANARY_53"),
                    "P53_REAL_OBSERVATION_FORGED:1")

    def test_missing_malformed_data_no_secret_echo(self):
        data = copy.deepcopy(self.docs)
        data[mod.HANDOFF] = {"password": "PRIVATE_CANARY_53"}
        state = mod.snapshot(injected=data)
        self.assertEqual(state["status"], "FAIL_CLOSED")
        self.assertNotIn("PRIVATE_CANARY_53", str(state))
        data = copy.deepcopy(self.docs)
        data.pop(mod.G1)
        self.assertEqual(mod.audit(injected=data),
                         ["P53_MALFORMED_OR_MISSING_SPEC"])


if __name__ == "__main__":
    unittest.main()
