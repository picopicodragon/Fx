"""RISK-3P-06: offline FORM-01 owner-evidence plan checks, no MT4."""
from __future__ import annotations

import copy
import json
import unittest

from scripts import audit_risk_3p_06_form01_evidence as mod


class Form01ThreePairEvidenceDraftTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.draft = json.loads((mod.ROOT / mod.DRAFT).read_text(encoding="utf-8"))

    def changed(self, edit, error):
        draft = copy.deepcopy(self.draft)
        edit(draft)
        self.assertIn(error, mod.audit(mod.ROOT, draft), error)

    def test_baseline_15_fields_pending_and_no_owner_approval(self):
        self.assertEqual(mod.audit(), [])
        self.assertEqual(len(self.draft["proposed_evidence_records"]), 3)
        for row in self.draft["proposed_evidence_records"]:
            self.assertEqual(len(row["required_five"]), 5)
            self.assertTrue(all(x["verified_value"] is None for x in row["required_five"]))
            self.assertTrue(all(x["status"] == "PENDING_REAL_WORLD_EVIDENCE"
                                for x in row["required_five"]))
        self.assertEqual(self.draft["form01_owner_decision"], "NOT_RECORDED")
        self.assertIs(self.draft["safety_hold_latched"], True)
        self.assertEqual(self.draft["runtime_go_no_go"], "NO_GO")

    def test_pair_scope_and_five_field_scope_cannot_drift(self):
        self.changed(lambda x: x["target_pairs"].pop(), "G1_DESIGN_SCOPE_DRIFT")
        self.changed(lambda x: x["required_g1_five_fields"].pop(),
                     "G1_DESIGN_SCOPE_DRIFT")
        self.changed(lambda x: x.update(target_g1_attribute_count=20),
                     "G1_DESIGN_SCOPE_DRIFT")
        self.changed(lambda x: x.update(legacy_g1_gate_scope_unchanged=False),
                     "G1_DESIGN_SCOPE_DRIFT")

    def test_g1_draft_and_real_world_claims_cannot_be_promoted(self):
        for key in ("g1_scope_revision_approved", "real_world_verified",
                    "broker_connection_authorized", "terminal_execution_approved",
                    "production_authorized", "stop_release_authorized",
                    "form01_implementation_approved",
                    "fx_saf_implementation_approved"):
            with self.subTest(key=key):
                self.changed(lambda x, k=key: x.update({k: True}),
                             "FALSE_APPROVAL:" + key)

    def test_false_owner_signoff_and_stop_release_rejected(self):
        for key, value in (("form01_owner_decision", "APPROVED"),
                           ("phase_1", "ACCEPTED"),
                           ("runtime_go_no_go", "GO"),
                           ("safety_hold_latched", False),
                           ("verified_values", {"fake": "123"})):
            with self.subTest(key=key):
                self.changed(lambda x, k=key, v=value: x.update({k: v}),
                             "FALSE_OWNER_ACCEPTANCE_OR_STOP_RELEASE")

    def test_original_limits_cannot_be_changed_in_evidence_plan(self):
        self.changed(lambda x: x["risk_caps_unmodified"].update(
            single_trade_fraction="0.01"), "HARD_RISK_CAP_CHANGED")
        self.changed(lambda x: x["risk_caps_unmodified"].update(
            combined_fraction="0.02"), "HARD_RISK_CAP_CHANGED")

    def test_missing_or_substituted_pair_cannot_pass(self):
        self.changed(lambda x: x["proposed_evidence_records"].pop(),
                     "THREE_PAIR_EVIDENCE_MATRIX_MISSING")
        self.changed(lambda x: x["proposed_evidence_records"][2].update(
            pair="GBP/JPY"), "EVIDENCE_SYMBOL_SET_INVALID")

    def test_one_field_cannot_be_called_verified(self):
        for field, value in (("status", "VERIFIED"),
                             ("verified_value", "0.01"),
                             ("provenance_reference", "fake-proof"),
                             ("observed_at_utc", "2026-11-04T02:00:00Z"),
                             ("independent_crosscheck", "PASS")):
            with self.subTest(field=field):
                self.changed(
                    lambda x, k=field, v=value: x["proposed_evidence_records"][2]
                    ["required_five"][0].update({k: v}),
                    "FALSE_FIVE_FIELD_EVIDENCE:EUR/USD:min_lot")

    def test_falsely_confirmed_account_symbol_or_owner_evidence_rejected(self):
        for field in ("real_symbol_identity_confirmed",
                      "account_identity_confirmed", "owner_verified"):
            with self.subTest(field=field):
                self.changed(
                    lambda x, k=field: x["proposed_evidence_records"][2]
                    .update({k: True}),
                    "FALSE_REAL_EVIDENCE:EUR/USD")

    def test_supplemental_tick_and_contract_fields_remain_unknown(self):
        self.changed(
            lambda x: x["proposed_evidence_records"][2]["supplementary_checks"][2]
            .update(verified_value="JPY"),
            "FALSE_SUPPLEMENTARY_EVIDENCE:EUR/USD:account_deposit_currency")
        self.changed(
            lambda x: x["proposed_evidence_records"][1]["supplementary_checks"].pop(),
            "SUPPLEMENTARY_EVIDENCE_INVALID:EUR/JPY")

    def test_none_of_the_five_owner_decisions_are_preapproved(self):
        for i in range(5):
            with self.subTest(i=i):
                self.changed(
                    lambda x, j=i: x["owner_decisions_to_resolve"][j]
                    .update(owner_status="APPROVED", approval_reference="UNVERIFIED"),
                    "OWNER_DECISION_PREMATURELY_FINAL:F01-" + str(i + 1))
        self.changed(
            lambda x: x["owner_decisions_to_resolve"].pop(),
            "OWNER_DECISION_SET_INVALID")

    def test_missing_evidence_rejection_conditions_cannot_be_removed(self):
        self.changed(lambda x: x["mandatory_reject_conditions"].pop(),
                     "FAIL_CLOSED_REJECTION_SCOPE_DRIFT")

    def test_invalid_schema_and_malformed_document_denied(self):
        self.assertEqual(mod.audit(mod.ROOT, draft=object()), ["DRAFT_SCHEMA_INVALID"])
        self.changed(lambda x: x.update(scope="LIVE_BROKER_APPROVED"),
                     "DRAFT_SCOPE_OR_ID_INVALID")
        self.changed(lambda x: x["proposed_evidence_records"][0].update(
            required_five={}), "REQUIRED_FIVE_INVALID:USD/JPY")


if __name__ == "__main__":
    unittest.main()
