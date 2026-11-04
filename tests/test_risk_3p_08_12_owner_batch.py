"""FORM-03..07 batch registry must not turn drafts into approvals."""
from __future__ import annotations

import copy
import json
import unittest

from scripts import audit_risk_3p_08_12_owner_batch as mod


class Form03To07OwnerBatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = json.loads(
            (mod.ROOT / mod.DRAFT).read_text(encoding="utf-8"))

    def mutation(self, change, expected):
        d = copy.deepcopy(self.document)
        change(d)
        self.assertIn(expected, mod.audit(mod.ROOT, d))

    def test_five_form_register_is_unapproved_and_ci_does_not_change_gates(self):
        self.assertEqual(mod.audit(), [])
        self.assertEqual(
            [x["form_id"] for x in self.document["forms"]],
            ["FORM-03", "FORM-04", "FORM-05", "FORM-06", "FORM-07"])
        self.assertEqual(len(self.document["owner_decisions"]), 20)
        self.assertIs(self.document["safety_hold_latched"], True)
        self.assertEqual(self.document["runtime_go_no_go"], "NO_GO")
        self.assertEqual(self.document["phase_1"], "BLOCKED")

    def test_target_pairs_and_unresolved_form_dependencies_are_guarded(self):
        self.mutation(lambda d: d["design_pairs"].pop(),
                      "THREE_PAIR_SCOPE_DRIFT")
        self.mutation(lambda d: d["downstream_unresolved"].remove("FORM-08"),
                      "UPSTREAM_OR_UNRESOLVED_GATES_DROPPED")
        self.mutation(lambda d: d["upstream_drafts"].pop(),
                      "UPSTREAM_OR_UNRESOLVED_GATES_DROPPED")

    def test_no_change_to_equity_limits(self):
        for key in ("individual", "aggregate", "daily", "max_drawdown"):
            with self.subTest(key=key):
                self.mutation(lambda d, k=key: d["existing_caps"].update(
                    {k: "0.2"}), "FIXED_CAPS_CHANGED")

    def test_batch_does_not_implicitly_authorize_automerge(self):
        self.mutation(lambda d: d.update(allow_unreviewed_main_merge=True),
                      "FALSE_AUTHORIZATION:allow_unreviewed_main_merge")
        self.mutation(lambda d: d.update(production_authorized=True),
                      "FALSE_AUTHORIZATION:production_authorized")
        self.mutation(lambda d: d.update(mt4_script_execution_authorized=True),
                      "FALSE_AUTHORIZATION:mt4_script_execution_authorized")

    def test_g1_and_stop_latches_and_reality_claims_unchanged(self):
        for field, value in (
            ("real_loss_bound_verified", True),
            ("form03_07_owner_approval_recorded", True),
            ("g1_scope_change_approved", True),
            ("fx_saf_implementation_approved", True),
            ("order_allowed", True),
            ("stop_release_allowed", True),
        ):
            with self.subTest(field=field):
                self.mutation(lambda d, k=field, v=value: d.update({k: v}),
                              "FALSE_AUTHORIZATION:" + field)
        for field, value in (
            ("phase_1", "ACCEPTED"),
            ("runtime_go_no_go", "GO"),
            ("safety_hold_latched", False),
            ("verified_values", {"unknown": "invented"}),
        ):
            with self.subTest(field=field):
                self.mutation(lambda d, k=field, v=value: d.update({k: v}),
                              "BLOCKED_STATUS_PROMOTED")

    def test_all_form_approvals_remain_unrecorded(self):
        for form in mod.FORM_IDS:
            with self.subTest(form=form):
                self.mutation(
                    lambda d, f=form: next(x for x in d["forms"]
                                          if x["form_id"] == f).update(
                                              owner_approval_recorded=True),
                    "FALSE_FORM_APPROVAL:" + form)

    def test_remove_form_or_change_risk_id_is_rejected(self):
        self.mutation(lambda d: d["forms"].pop(),
                      "FIVE_FORM_SCOPE_DRIFT")
        self.mutation(lambda d: d["forms"][0].update(risk_id="RISK-3P-99"),
                      "FIVE_FORM_SCOPE_DRIFT")

    def test_falsely_approve_one_of_twenty_decisions_rejected(self):
        for i in range(20):
            with self.subTest(i=i):
                ident = self.document["owner_decisions"][i]["id"]
                self.mutation(lambda d, j=i: d["owner_decisions"][j].update(
                    owner_decision="APPROVED", approval_reference="FAKE"),
                    "FALSE_OWNER_APPROVAL:" + ident)

    def test_missing_decision_or_proposal_evidence_rejected(self):
        self.mutation(lambda d: d["owner_decisions"].pop(),
                      "OWNER_DECISION_SET_DRIFT")
        self.mutation(lambda d: d["forms"][0].update(unresolved=[]),
                      "MISSING_FORM_EVIDENCE_PLAN:FORM-03")
        self.mutation(lambda d: d["owner_decisions"][0].update(
            real_world_evidence_verified=True),
            "FALSE_OWNER_APPROVAL:FORM03-1")

    def test_synthetic_cost_and_reservation_assumptions_not_promoted(self):
        self.mutation(lambda d: d.update(
            simulated_fx_loss_conversion="BROKER_APPROVED"),
            "SYNTHETIC_ASSUMPTION_SCOPE_CHANGED")
        self.mutation(lambda d: d["simulated_cost_modes"].pop(),
                      "SYNTHETIC_ASSUMPTION_SCOPE_CHANGED")

    def test_invalid_document_rejected(self):
        self.assertEqual(mod.audit(mod.ROOT, object()), ["INVALID_REGISTER"])
        self.mutation(lambda d: d.update(scope="PRODUCTION"),
                      "DRAFT_ID_OR_SCOPE_INVALID")


if __name__ == "__main__":
    unittest.main()
