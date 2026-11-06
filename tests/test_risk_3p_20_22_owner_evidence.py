"""RISK-3P-20..22: mutation tests for the 15-field rubric and 43 decisions."""
from __future__ import annotations

import copy
import unittest

from scripts import audit_risk_3p_20_22_owner_evidence as audit


class OwnerEvidenceRubricTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.files = audit.documents()

    def denied(self, path, change, expected):
        docs = copy.deepcopy(self.files)
        change(docs[path])
        errors = audit.audit(injected=docs)
        self.assertIn(expected, errors, errors)

    def test_baseline_fifteen_criteria_and_forty_three_owner_decisions(self):
        self.assertEqual(audit.audit(), [])
        rub, docket = self.files[audit.RUBRIC], self.files[audit.DOCKET]
        self.assertEqual(len(rub["rows"]), 15)
        self.assertEqual(rub["verified_count"], 0)
        self.assertTrue(all(row["verified_value"] is None
                            and row["acceptance"] == "NOT_EVALUATED"
                            for row in rub["rows"]))
        self.assertEqual(len(docket["form_groups"]), 10)
        self.assertEqual(len(docket["decisions"]), 43)
        self.assertTrue(all(x["owner_decision"] == "NOT_RECORDED"
                            for x in docket["decisions"]))
        self.assertIs(rub["safety_hold_latched"], True)
        self.assertEqual(docket["runtime_go_no_go"], "NO_GO")

    def test_rubric_old_g1_and_new_three_pair_scope_cannot_change(self):
        self.denied(audit.RUBRIC,
                    lambda d: d["target_pairs"].append("AUD/USD"),
                    "G1_FIFTEEN_ITEM_SCOPE_DRIFT")
        self.denied(audit.RUBRIC,
                    lambda d: d.update(historical_g1="3_PAIRS_APPROVED"),
                    "G1_FIFTEEN_ITEM_SCOPE_DRIFT")
        self.denied(audit.RUBRIC,
                    lambda d: d.update(verified_count=1),
                    "G1_FIFTEEN_ITEM_SCOPE_DRIFT")
        self.denied(audit.RUBRIC,
                    lambda d: d.update(scope="BROKER_VALIDATED"),
                    "RUBRIC_IDENTITY_OR_REVIEW_SCOPE_DRIFT")

    def test_15_rows_cannot_be_dropped_duplicated_or_relabelled(self):
        self.denied(audit.RUBRIC, lambda d: d["rows"].pop(),
                    "G1_RUBRIC_ROWS_MISSING")
        self.denied(audit.RUBRIC,
                    lambda d: d["rows"][14].update(field="min_lot"),
                    "G1_RUBRIC_ROWS_MISSING")

    def test_each_g1_cell_will_refuse_fabricated_verified_value(self):
        for index in range(15):
            r = self.files[audit.RUBRIC]["rows"][index]
            with self.subTest(pair=r["pair"], field=r["field"]):
                self.denied(
                    audit.RUBRIC,
                    lambda d, i=index: d["rows"][i].update(verified_value="0.01"),
                    "G1_FIELD_FALSELY_ACCEPTED:" + r["pair"] + ":" + r["field"])

    def test_issuer_account_timestamp_and_signoff_must_stay_unknown(self):
        for field, value in (
            ("recorded_unit", "JPY"), ("account_environment_alias", "demo"),
            ("terminal_symbol", "EURUSD"),
            ("primary_source_reference", "claimed"),
            ("independent_source_reference", "claimed-other"),
            ("observed_at_utc", "2026-11-04T04:00:00Z"),
            ("primary_issuer", "fake"),
            ("independent_issuer", "fake"),
            ("human_evidence_review_reference", "fake-approval"),
        ):
            with self.subTest(field=field):
                self.denied(
                    audit.RUBRIC,
                    lambda d, k=field, v=value: d["rows"][14].update({k: v}),
                    "G1_FIELD_FALSELY_ACCEPTED:EUR/USD:tick_value_deposit_currency")

    def test_no_missing_g1_acceptance_prerequisite_or_fake_approval(self):
        self.denied(audit.RUBRIC,
                    lambda d: d["common_required_checks"].pop(),
                    "COMMON_EVIDENCE_CHECKS_DROPPED")
        self.denied(audit.RUBRIC,
                    lambda d: d["field_specific_checks"]["point_quote"].pop(),
                    "FIELD_UNIT_OR_RISK_CHECKS_DROPPED")
        self.denied(audit.RUBRIC,
                    lambda d: d["rows"][14]["required_checks"].pop(),
                    "G1_FIELD_FALSELY_ACCEPTED:EUR/USD:tick_value_deposit_currency")
        self.denied(audit.RUBRIC,
                    lambda d: d["rows"][14]["checks_passed"].append("FAKE_PASS"),
                    "G1_FIELD_FALSELY_ACCEPTED:EUR/USD:tick_value_deposit_currency")
        self.denied(audit.RUBRIC,
                    lambda d: d["explicit_non_approvals"].update(
                        broker_contract_verified=True),
                    "RUBRIC_FALSE_AUTHORIZATION")

    def test_rubric_does_not_release_stop_or_skip_form_gates(self):
        for k, v in (("phase_1", "ACCEPTED"),
                     ("runtime_go_no_go", "GO"),
                     ("safety_hold_latched", False),
                     ("verified_values", {"x": "fake"})):
            with self.subTest(key=k):
                self.denied(
                    audit.RUBRIC, lambda d, key=k, value=v: d.update({key: value}),
                    "RUBRIC_STOP_STATE_PROMOTED")
        self.denied(audit.RUBRIC,
                    lambda d: d["pending_additional_requirements"].pop(),
                    "DEPENDENT_GATES_DROPPED")

    def test_source_observation_and_v3_template_are_still_unverified(self):
        self.denied(
            audit.PROTOCOL,
            lambda d: d["proposed_observations"][14].update(
                status="REAL_WORLD_VERIFIED"),
            "OBSERVATION_PROTOCOL_FALSELY_ADVANCED")
        self.denied(
            audit.V3,
            lambda d: d["symbols"][2]["properties"].update(min_lot="0.01"),
            "MT4_V3_UNVERIFIED_VALUES_FILLED")

    def test_form_group_count_and_order_stays_consistent(self):
        self.denied(
            audit.DOCKET, lambda d: d["form_groups"].pop(),
            "FORM_GROUP_SCOPE_CHANGED")
        self.denied(
            audit.DOCKET,
            lambda d: d["form_groups"][4].update(review_sequence=1),
            "FORM_GROUP_FALSELY_REVIEWED:FORM-05")
        self.denied(
            audit.DOCKET,
            lambda d: d["form_groups"][0].update(review_packet_ready=True),
            "FORM_GROUP_FALSELY_REVIEWED:FORM-01")

    def test_all_forty_three_owner_decisions_cannot_be_implicitly_approved(self):
        for index, row in enumerate(self.files[audit.DOCKET]["decisions"]):
            with self.subTest(id=row["id"]):
                self.denied(
                    audit.DOCKET,
                    lambda d, i=index: d["decisions"][i].update(
                        owner_decision="APPROVED", human_approval_reference="FAKE"),
                    "DECISION_FALSELY_APPROVED:" + row["id"])

    def test_missing_or_extra_decision_is_rejected(self):
        self.denied(audit.DOCKET, lambda d: d["decisions"].pop(),
                    "DECISION_ROWS_MISSING_DUPLICATE_OR_UNEXPECTED")
        self.denied(
            audit.DOCKET,
            lambda d: d["decisions"][1].update(id=d["decisions"][0]["id"]),
            "DECISION_ROWS_MISSING_DUPLICATE_OR_UNEXPECTED")
        self.denied(audit.DOCKET, lambda d: d["decisions"].reverse(),
                    "DECISION_SOURCE_ORDER_CHANGED")

    def test_questions_and_recommendations_stay_exactly_as_proposed(self):
        self.denied(
            audit.DOCKET, lambda d: d["decisions"][0].update(
                original_question="APPROVED AND COMPLETE"),
            "DECISION_SOURCE_PROVENANCE_DRIFT:F01-1")
        self.denied(
            audit.DOCKET, lambda d: d["decisions"][6].update(
                required_evidence_gate="NONE"),
            "DECISION_SOURCE_PROVENANCE_DRIFT:F02-2")
        self.denied(
            audit.FORM01, lambda d: d["owner_decisions_to_resolve"][0].update(
                owner_status="APPROVED"),
            "DECISION_UPSTREAM_FALSELY_APPROVED:F01-1")
        self.denied(
            audit.FORM0307, lambda d: d["owner_decisions"][0].update(
                approval_reference="FAKE"),
            "DECISION_UPSTREAM_FALSELY_APPROVED:FORM03-1")

    def test_no_autosignoff_or_broker_test_without_approval(self):
        self.denied(audit.DOCKET,
                    lambda d: d["owner_review_policy"].update(
                        allow_implicit_owner_approval=True),
                    "OWNER_REVIEW_POLICY_WEAKENED")
        self.denied(audit.DOCKET,
                    lambda d: d["owner_review_policy"].update(
                        allow_live_test_without_separate_authorization=True),
                    "OWNER_REVIEW_POLICY_WEAKENED")
        self.denied(audit.DOCKET,
                    lambda d: d.update(main_automerge_authorized=True),
                    "DOCKET_FALSE_AUTHORIZATION:main_automerge_authorized")

    def test_docket_stays_phase_blocked_and_original_forms_undecided(self):
        self.denied(audit.DOCKET,
                    lambda d: d.update(runtime_go_no_go="GO"),
                    "DOCKET_STOP_STATE_PROMOTED")
        self.denied(audit.FORM_BASE,
                    lambda d: d["open_decisions"][0].update(blocking=False),
                    "FORM_SOURCE_NOT_ALL_UNDECIDED")
        self.denied(audit.GATES,
                    lambda d: d["gaps"][0].update(real_world_verified=True),
                    "G1_G9_PREMATURELY_RELEASED")

    def test_malformed_packet_is_rejected(self):
        a = copy.deepcopy(self.files)
        a[audit.DOCKET] = []
        self.assertEqual(audit.audit(injected=a),
                         ["INVALID_REVIEW_REGISTERS"])


if __name__ == "__main__":
    unittest.main()
