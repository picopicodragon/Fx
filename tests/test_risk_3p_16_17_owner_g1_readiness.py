"""RISK-3P-16/17 documentary readiness stays BLOCKED across all upstreams."""
from __future__ import annotations

import copy
import unittest

from scripts import audit_risk_3p_16_17_owner_g1_readiness as mod


class G1OwnerReadinessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = mod._docs(mod.ROOT, None)

    def bad(self, path, change, expected):
        d = copy.deepcopy(self.data)
        change(d[path])
        result = mod.audit(mod.ROOT, documents=d)
        self.assertIn(expected, result, result)

    def test_baseline_integrates_all_ten_forms_and_forty_three_decisions(self):
        self.assertEqual(mod.audit(), [])
        packet = self.data[mod.DRAFT]
        self.assertEqual(len(packet["form_ids"]), 10)
        self.assertEqual(sum(packet["pending_owner_decisions_by_source"].values()), 43)
        self.assertEqual(packet["proposed_g1_attributes"], 15)
        self.assertEqual(packet["historic_g1_attributes"], 20)
        self.assertEqual(packet["current_readiness"],
                         "BLOCKED_MISSING_ORIGINALS_AND_REAL_EVIDENCE")
        self.assertEqual(packet["runtime_go_no_go"], "NO_GO")
        self.assertIs(packet["safety_hold_latched"], True)

    def test_unreviewed_main_merge_is_never_granted_by_batching(self):
        self.bad(mod.DRAFT, lambda x: x.update(
            unreviewed_auto_merge_authorized=True),
            "FALSE_AUTHORIZATION:unreviewed_auto_merge_authorized")
        self.bad(mod.DRAFT, lambda x: x.update(manual_main_merge_required=False),
                 "MANUAL_MAIN_MERGE_POLICY_CHANGED")

    def test_all_owner_and_live_authority_flags_remain_false(self):
        self.bad(mod.DRAFT, lambda x: x.update(g1_scope_revision_approved=False),
                 "SCOPE_APPROVAL_RECORD_MISSING")
        for field in (
            "owner_approval_recorded",
            "g1_real_world_verified", "fx_saf_implementation_approved",
            "module_acceptance_approved", "phase_acceptance_approved",
            "production_authorized", "real_market_data_verified",
            "order_allowed", "stop_release_allowed",
        ):
            with self.subTest(field=field):
                self.bad(mod.DRAFT, lambda x, k=field: x.update({k: True}),
                         "FALSE_AUTHORIZATION:" + field)

    def test_stop_latch_and_limits_never_change(self):
        self.bad(mod.DRAFT, lambda x: x.update(runtime_go_no_go="GO"),
                 "BLOCKED_STATE_PROMOTED")
        self.bad(mod.DRAFT, lambda x: x.update(safety_hold_latched=False),
                 "BLOCKED_STATE_PROMOTED")
        self.bad(mod.DRAFT, lambda x: x.update(verified_values={"EUR/USD": "FAKE"}),
                 "BLOCKED_STATE_PROMOTED")
        self.bad(mod.DRAFT, lambda x: x["unchanged_limits"].update(
            aggregate_fraction="0.02"), "HARD_LIMITS_CHANGED")

    def test_all_six_evidence_stages_must_remain_unapproved(self):
        self.bad(mod.DRAFT, lambda x: x["evidence_lifecycle"][3].update(
            authorized=True), "EVIDENCE_LIFECYCLE_FALSELY_COMPLETE")
        self.bad(mod.DRAFT, lambda x: x["evidence_lifecycle"].pop(),
                 "EVIDENCE_LIFECYCLE_FALSELY_COMPLETE")
        self.bad(mod.DRAFT, lambda x: x["evidence_lifecycle"][0].update(
            status="COMPLETE"), "EVIDENCE_LIFECYCLE_FALSELY_COMPLETE")

    def test_all_real_environment_actions_are_separately_unapproved(self):
        for k in self.data[mod.DRAFT]["privacy_and_operation"]:
            with self.subTest(action=k):
                self.bad(mod.DRAFT, lambda x, key=k: x["privacy_and_operation"]
                         .update({key: True}),
                         "UNAUTHORIZED_REAL_ENVIRONMENT_ACTION")

    def test_pending_form_implementation_not_approved_in_original_source(self):
        self.bad(mod.FORM, lambda x: x["open_decisions"][2].update(
            owner_status="APPROVED"), "FORM01_10_ORIGINAL_NOT_UNRESOLVED")
        self.bad(mod.FORM, lambda x: x["adopted_fixed_controls"].update(
            combined_risk_fraction_of_current_equity="0.02"),
            "FIXED_LIMIT_SOURCE_DRIFT")

    def test_form01_to_ten_owner_draft_not_approved(self):
        self.bad(mod.OWNER, lambda x: x["open_reviews"][3].update(
            implementation_approved=True), "TEN_FORM_OWNER_DRAFT_FALSELY_APPROVED")
        self.bad(mod.OWNER, lambda x: x["open_reviews"].pop(),
                 "TEN_FORM_OWNER_DRAFT_FALSELY_APPROVED")

    def test_third_pair_eurusd_evidence_is_not_fake_verified(self):
        self.bad(mod.FORM01, lambda x: x["proposed_evidence_records"][2]
                 ["required_five"][0].update(verified_value="0.01"),
                 "G1_FIELD_FALSELY_VERIFIED:EUR/USD:min_lot")
        self.bad(mod.FORM01, lambda x: x["proposed_evidence_records"][2]
                 ["required_five"][4].update(
                     provenance_reference="FAKE_PERSONAL_SOURCE"),
                 "G1_FIELD_FALSELY_VERIFIED:EUR/USD:tick_value_deposit_currency")
        self.bad(mod.FORM01, lambda x: x["proposed_evidence_records"][2].update(
            account_identity_confirmed=True),
            "G1_ACCOUNT_OR_OWNER_FALSELY_VERIFIED:EUR/USD")
        self.bad(mod.FORM01, lambda x: x["proposed_evidence_records"][2]
                 ["supplementary_checks"][2].update(verified_value="JPY"),
                 "G1_SUPPLEMENTAL_EVIDENCE_FALSELY_VERIFIED:EUR/USD")

    def test_g1_matrix_cannot_have_missing_pair_or_field(self):
        self.bad(mod.FORM01, lambda x: x["proposed_evidence_records"].pop(),
                 "THREE_PAIR_EVIDENCE_ROWS_MISSING")
        self.bad(mod.FORM01, lambda x: x["proposed_evidence_records"][1]
                 ["required_five"].pop(), "G1_FIVE_FIELDS_MISSING:EUR/JPY")
        self.bad(mod.DRAFT, lambda x: x["target_pairs"].append("AUD/JPY"),
                 "TARGET_FORM_G1_SCOPE")

    def test_all_forty_three_form_choices_remain_unapproved(self):
        def disapprove(x):
            x["owner_decisions_to_resolve"][0]["owner_status"] = "APPROVED"
        self.bad(mod.FORM01, disapprove, "FORM01_OWNER_DECISION_FALSELY_APPROVED")
        self.bad(mod.FORM02, lambda x: x["owner_decisions"][0].update(
            owner_status="APPROVED"), "FORM02_OWNER_DECISION_FALSELY_APPROVED")
        self.bad(mod.FORM0307, lambda x: x["owner_decisions"][0].update(
            owner_decision="APPROVED"), "FORM03_10_OWNER_DECISION_FALSELY_APPROVED")
        self.bad(mod.FORM0810, lambda x: x["owner_decisions"][0].update(
            owner_decision="APPROVED"), "FORM03_10_OWNER_DECISION_FALSELY_APPROVED")
        self.bad(mod.FORM0810, lambda x: x["owner_decisions"].pop(),
                 "FORTY_THREE_OWNER_DECISIONS_INCOMPLETE")

    def test_hist_g1_4x5_and_all_nine_gates_stay_blocked(self):
        self.bad(mod.GATES, lambda x: x["gaps"][0].update(
            implementation_status="VERIFIED"),
            "FORMAL_G1_SCOPE_OR_G1_STATUS_DRIFT")
        self.bad(mod.GATES, lambda x: x["gaps"][8].update(
            release_blocker=False), "ONE_OR_MORE_G1_G9_GATES_RELEASED")
        self.bad(mod.GATES, lambda x: x["gaps"][0].update(
            subject="新3ペア実証済み"), "FORMAL_G1_SCOPE_OR_G1_STATUS_DRIFT")
        self.bad(mod.GATES, lambda x: x.update(phase_1="ACCEPTED"),
                 "FORMAL_RELEASE_GATE_FALSELY_ADVANCED")

    def test_15_source_reviews_remain_pending_original(self):
        self.bad(mod.SAFETY, lambda x: x["items"][1].update(
            human_safety_approval=True), "ORIGINAL_SAFETY_EVIDENCE_UNVERIFIED")
        self.bad(mod.SAFETY, lambda x: x["items"][0].update(
            source_review="VERIFIED"), "ORIGINAL_SAFETY_EVIDENCE_UNVERIFIED")

    def test_module_and_phase_signoff_cannot_be_inferred(self):
        self.bad(mod.ACCEPT, lambda x: x["modules"][0].update(
            status="ACCEPTED", approval="FAKE"), "MODULE_OR_PHASE_FALSELY_ACCEPTED")
        self.bad(mod.ACCEPT, lambda x: x["phases"][0].update(
            status="ACCEPTED"), "MODULE_OR_PHASE_FALSELY_ACCEPTED")

    def test_v3_contract_values_not_assumed_or_proven_by_template(self):
        self.bad(mod.V3, lambda x: x["symbols"][2]["properties"].update(
            min_lot="0.01"), "THREE_PAIR_V3_TEMPLATE_FILLED_WITH_UNVERIFIED_VALUES")
        self.bad(mod.V3, lambda x: x["symbols"][2]["observation"].update(
            terminal_symbol="EURUSD"),
            "THREE_PAIR_V3_TEMPLATE_FILLED_WITH_UNVERIFIED_VALUES")

    def test_offline_traceability_never_promotes_production(self):
        self.bad(mod.TRACE, lambda x: x["offline_synthetic_mappings"][0].update(
            production_authorized=True), "OFFLINE_TRACEABILITY_PROMOTED")

    def test_incorrect_packet_missing_form_or_invalid_json_object_denied(self):
        self.bad(mod.DRAFT, lambda x: x.update(form_ids=["FORM-01"]),
                 "TARGET_FORM_G1_SCOPE")
        self.bad(mod.DRAFT, lambda x: x.update(scope="PRODUCTION"),
                 "PREFLIGHT_ID_OR_SCOPE")
        d = copy.deepcopy(self.data)
        d[mod.DRAFT] = []
        self.assertEqual(mod.audit(documents=d), ["INVALID_PREFLIGHT_REGISTER"])


if __name__ == "__main__":
    unittest.main()
