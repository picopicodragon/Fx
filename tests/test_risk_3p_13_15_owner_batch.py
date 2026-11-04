"""FORM-08..10 offline review cannot grant stop release or universal TTL."""
from __future__ import annotations

import copy
import json
import unittest

from scripts import audit_risk_3p_13_15_owner_batch as mod


class OwnerForm08To10Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = json.loads((mod.ROOT / mod.DRAFT).read_text(encoding="utf-8"))

    def changed(self, edit, expected):
        draft = copy.deepcopy(self.doc)
        edit(draft)
        self.assertIn(expected, mod.audit(mod.ROOT, draft))

    def test_baseline_pending_twelve_owner_choices(self):
        self.assertEqual(mod.audit(), [])
        self.assertEqual([r["form_id"] for r in self.doc["forms"]],
                         ["FORM-08", "FORM-09", "FORM-10"])
        self.assertEqual(len(self.doc["owner_decisions"]), 12)
        self.assertEqual(self.doc["phase_1"], "BLOCKED")
        self.assertEqual(self.doc["runtime_go_no_go"], "NO_GO")
        self.assertIs(self.doc["safety_hold_latched"], True)

    def test_day_dd_loss_limits_cannot_change(self):
        self.changed(lambda d: d["existing_caps"].update(daily="0.03"),
                     "RISK_LIMITS_CHANGED")
        self.changed(lambda d: d["existing_caps"].update(max_drawdown="0.10"),
                     "RISK_LIMITS_CHANGED")

    def test_no_live_account_approval_is_implicit(self):
        for name in ("fx_saf_implementation_approved",
                     "g1_to_g9_real_world_verified", "owner_approval_recorded",
                     "production_authorized", "broker_connection_authorized",
                     "mt4_execution_authorized", "order_allowed",
                     "stop_release_allowed", "auto_resume_authorized"):
            with self.subTest(name=name):
                self.changed(lambda d, n=name: d.update({n: True}),
                             "FALSE_OPERATIONAL_APPROVAL:" + name)

    def test_stop_gate_cannot_be_released_from_synthetic_dd_recovery(self):
        for key, value in (("phase_1", "ACCEPTED"),
                           ("runtime_go_no_go", "GO"),
                           ("safety_hold_latched", False),
                           ("verified_values", {"dd": 0})):
            with self.subTest(key=key):
                self.changed(lambda d, k=key, v=value: d.update({k: v}),
                             "FALSE_STOP_RELEASE")

    def test_universal_ttl_is_not_inferred_from_monitor_delay(self):
        self.changed(lambda d: d.update(only_examples=["Q128_APPROVED_TTL_15S"]),
                     "FALSE_PRODUCTION_EXAMPLE_OR_TTL")
        self.changed(lambda d: d["unresolved_dependencies"].remove("G1"),
                     "DOWNSTREAM_DEPENDENCIES_DROPPED")

    def test_form08_09_10_provenance_is_unapproved(self):
        for key in mod.IDS:
            with self.subTest(key=key):
                self.changed(
                    lambda d, form=key: next(x for x in d["forms"]
                                            if x["form_id"] == form).update(
                                                implementation_approved=True),
                    "FALSE_FORM_APPROVAL:" + key)

    def test_missing_form_or_question_fails(self):
        self.changed(lambda d: d["forms"].pop(), "FORM08_10_SCOPE_CHANGED")
        self.changed(lambda d: d["owner_decisions"].pop(),
                     "DECISION_SET_INCOMPLETE")

    def test_each_owner_choice_provenance_is_required(self):
        for index in range(12):
            ident = self.doc["owner_decisions"][index]["id"]
            with self.subTest(choice=ident):
                self.changed(
                    lambda d, i=index: d["owner_decisions"][i].update(
                        owner_decision="APPROVED", approval_reference="FAKE"),
                    "FALSE_OWNER_DECISION:" + ident)

    def test_invalid_scope_refused(self):
        self.assertEqual(mod.audit(mod.ROOT, object()), ["INVALID_REGISTER"])
        self.changed(lambda d: d.update(scope="PRODUCTION"),
                     "DRAFT_SCOPE_CHANGED")


if __name__ == "__main__":
    unittest.main()
