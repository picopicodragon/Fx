"""RISK-3P-05: documentation-only approval and provenance checks."""
from __future__ import annotations

import copy
import json
import unittest

from scripts import audit_risk_3p_05_owner_review as mod


class OwnerRiskDraftTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.draft = json.loads((mod.ROOT / mod.DRAFT).read_text(encoding="utf-8"))
        cls.source = json.loads((mod.ROOT / mod.SOURCE).read_text(encoding="utf-8"))

    def check_edit(self, change, expected):
        draft = copy.deepcopy(self.draft)
        source = copy.deepcopy(self.source)
        change(draft, source)
        result = mod.audit(mod.ROOT, draft=draft, source=source)
        self.assertIn(expected, result)

    def test_baseline_full_form_register_unapproved_and_blocked(self):
        self.assertEqual(mod.audit(), [])
        self.assertEqual([r["id"] for r in self.draft["open_reviews"]],
                         list(mod.REQUIRED_IDS))
        self.assertTrue(all(r["implementation_approved"] is False
                            and r["owner_decision"] == "NOT_RECORDED"
                            and r["real_world_evidence_verified"] is False
                            for r in self.draft["open_reviews"]))
        self.assertEqual(self.draft["phase_1"], "BLOCKED")
        self.assertEqual(self.draft["runtime_go_no_go"], "NO_GO")
        self.assertIs(self.draft["safety_hold_latched"], True)

    def test_future_pairs_3_and_old_pair_history_cannot_be_changed(self):
        self.check_edit(lambda d, s: d.update(future_design_pair_scope=[
            "USD/JPY", "EUR/JPY", "GBP/USD"]), "PAIR_SCOPE_CHANGED")
        self.check_edit(lambda d, s: d.update(historic_pair_scope=[
            "USD/JPY", "EUR/JPY", "EUR/USD"]), "PAIR_SCOPE_CHANGED")

    def test_3_by_5_draft_does_not_approve_replacing_4_by_5_g1(self):
        self.assertEqual(self.draft["proposed_g1_attributes"], 15)
        self.assertEqual(self.draft["old_g1_attributes"], 20)
        self.assertFalse(self.draft["g1_scope_change_approved"])
        self.check_edit(lambda d, s: d.update(g1_scope_change_approved=True),
                        "FALSE_APPROVAL_OR_REAL_EVIDENCE:g1_scope_change_approved")
        self.check_edit(lambda d, s: d.update(proposed_g1_attributes=20),
                        "G1_ATTRIBUTE_SCOPE_CHANGED")

    def test_safety_holds_and_limits_cannot_be_promoted(self):
        for field, val in (
            ("production_authorized", True),
            ("owner_approval_recorded", True),
            ("fx_saf_implementation_approved", True),
            ("g1_real_world_verified", True),
            ("stop_release_authorized", True),
            ("real_broker_or_cloud_actions_authorized", True),
        ):
            with self.subTest(field=field):
                self.check_edit(lambda d, s, f=field, v=val: d.update({f: v}),
                                "FALSE_APPROVAL_OR_REAL_EVIDENCE:" + field)
        for field, val in (
            ("phase_1", "ACCEPTED"),
            ("runtime_go_no_go", "GO"),
            ("safety_hold_latched", False),
            ("verified_values", {"EUR/USD": "invented"}),
        ):
            with self.subTest(field=field):
                self.check_edit(lambda d, s, f=field, v=val: d.update({f: v}),
                                "PHASE_OR_SAFETY_HOLD_PROMOTED")
        self.check_edit(lambda d, s: d["hard_limits_unchanged"].update(
            aggregate="0.02"), "HARD_LIMIT_CHANGED")

    def test_each_form_acceptance_requires_separate_owner_provenance(self):
        for row in self.draft["open_reviews"]:
            form_id = row["id"]
            with self.subTest(form=form_id):
                def approve(d, s):
                    entry = next(x for x in d["open_reviews"] if x["id"] == form_id)
                    entry.update(owner_decision="APPROVED",
                                 approval_reference="FAKE", implementation_approved=True)
                self.check_edit(approve, "FALSE_FORM_APPROVAL:" + form_id)

    def test_original_form_register_not_falsely_advanced(self):
        self.check_edit(lambda d, s: s["open_decisions"][0].update(
            owner_status="APPROVED"), "FORM_ORIGINAL_SOURCE_DRIFT:FORM-01")
        self.check_edit(lambda d, s: s["adopted_fixed_controls"].update(
            combined_risk_fraction_of_current_equity="0.02"),
            "FIXED_CONTROL_SOURCE_MISMATCH")

    def test_missing_form_and_misclassified_form_is_rejected(self):
        self.check_edit(lambda d, s: d["open_reviews"].pop(),
                        "FORM_ID_SET_DRIFT")
        self.check_edit(lambda d, s: d["open_reviews"][5].update(
            three_pair_impact="RETAIN_EXISTING_GATE"),
            "FORM_IMPACT_SCOPE_DRIFT:FORM-06")

    def test_each_proposal_has_evidence_needs_and_is_not_approval(self):
        self.check_edit(lambda d, s: d["open_reviews"][2].update(
            required_evidence=[]),
            "FORM_EVIDENCE_OR_RECOMMENDATION_MISSING:FORM-03")
        self.check_edit(lambda d, s: d["open_reviews"][1].update(
            proposed_only=False), "FALSE_FORM_APPROVAL:FORM-02")

    def test_offline_tests_cannot_be_relabelled_as_live_verification(self):
        self.check_edit(lambda d, s: d.update(previous_offline_test_scope=[
            "RISK-3P-01", "RISK-3P-02", "RISK-3P-03",
            "RISK-3P-04", "LIVE_BROKER_VERIFIED"]),
            "SYNTHETIC_SCOPE_FALSELY_EXTENDED")
        self.check_edit(lambda d, s: d.update(scope="PRODUCTION_READY"),
                        "INVALID_DRAFT_IDENTITY")


if __name__ == "__main__":
    unittest.main()
