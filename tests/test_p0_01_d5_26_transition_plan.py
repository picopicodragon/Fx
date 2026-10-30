"""D5-26: G1-G9 prioritized design-only transition plan tests."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import unittest

from scripts.p0_01_d5_26_transition_plan import evaluate_offline_transition_plan

_ROOT = Path(__file__).resolve().parents[1]
_IDS = ("G2", "G6", "G8", "G7", "G3", "G1", "G5", "G9", "G4")


def _read(path):
    with (_ROOT / path).open(encoding="utf-8") as stream:
        return json.load(stream)


def plan():
    return _read("specs/p0_01_d5_26_transition_priority_plan.json")


def baseline():
    return _read("specs/p0_01_d5_25_gap_verification_matrix.json")


def transition(p, name):
    return next(t for t in p["transition_proposals"] if t["id"] == name)


def gate(p, name):
    return next(t for t in p["gates"] if t["id"] == name)


class D526TransitionPlanTests(unittest.TestCase):
    def denied(self, result):
        self.assertEqual(result["phase_1"], "BLOCKED")
        self.assertEqual(result["runtime_go_no_go"], "NO_GO")
        self.assertIsNone(result["verified_values"])
        self.assertIs(result["safety_hold_latched"], True)
        self.assertEqual(result["effective_approved_actions"], [])
        self.assertEqual(result["gaps_real_world_resolved"], [])
        self.assertEqual(result["next_offline_design_focus"], ["G2", "G6"])
        self.assertEqual(result["proposed_review_priority"], list(_IDS))
        for field in (
            "real_transition_authorized", "visual_review_approved",
            "mt4_read_only_approved", "host_io_approved",
            "demo_execution_approved", "live_activation_approved",
            "approval_verified", "action_authorized", "stop_release_authorized",
            "broker_verified", "production_usable",
            "read_only_ex4_execution_approved",
            "terminal_execution_approved", "orders_generated",
            "forward_trading_enabled",
        ):
            self.assertIs(result[field], False)

    def check(self, p, b, status):
        result = evaluate_offline_transition_plan(p, b)
        self.denied(result)
        self.assertEqual(result["status"], status)
        return result

    def test_actual_plan_matches_baseline_and_is_still_no_go(self):
        self.check(plan(), baseline(),
                   "PLAN_DESIGN_VALIDATED_REAL_TRANSITIONS_BLOCKED_NO_GO")

    def test_proposed_review_priority_not_real_permission(self):
        r = self.check(plan(), baseline(),
                       "PLAN_DESIGN_VALIDATED_REAL_TRANSITIONS_BLOCKED_NO_GO")
        self.assertEqual(r["proposed_review_priority"][:2], ["G2", "G6"])
        self.assertIs(r["real_transition_authorized"], False)

    def test_all_nine_gaps_unresolved(self):
        p = plan()
        self.assertEqual([x["id"] for x in p["gates"]], list(_IDS))
        for item in p["gates"]:
            self.assertEqual(item["readiness"], "UNRESOLVED")
            self.assertIs(item["release_blocker"], True)
            self.assertIs(item["real_world_verified"], False)
        self.denied(evaluate_offline_transition_plan(p, baseline()))

    def test_g2_and_g6_can_be_designed_without_real_environment(self):
        p = plan()
        for gid in ("G2", "G6"):
            self.assertEqual(gate(p, gid)["depends_on"], [])
            self.assertTrue(gate(p, gid)["offline_next"])
            self.assertTrue(gate(p, gid)["external_evidence_required"])
        self.check(p, baseline(),
                   "PLAN_DESIGN_VALIDATED_REAL_TRANSITIONS_BLOCKED_NO_GO")

    def test_all_future_real_steps_are_not_approved(self):
        p = plan()
        self.assertEqual(len(p["transition_proposals"]), 6)
        for t in p["transition_proposals"][1:]:
            self.assertEqual(t["status"], "NOT_APPROVED")
            self.assertIs(t["requires_explicit_approval"], True)
        self.denied(evaluate_offline_transition_plan(p, baseline()))

    def test_offline_documentation_not_terminal_permission(self):
        p = plan()
        t = transition(p, "OFFLINE_SPEC_REVIEW")
        self.assertEqual(t["scope_rule"], "DOCUMENTATION_ONLY_NO_RUNTIME")
        self.assertIs(t["requires_explicit_approval"], False)
        self.check(p, baseline(),
                   "PLAN_DESIGN_VALIDATED_REAL_TRANSITIONS_BLOCKED_NO_GO")

    def test_single_environment_observation_is_not_approved(self):
        p = plan()
        t = transition(p, "SINGLE_ENV_VISUAL_REVIEW")
        self.assertEqual(t["status"], "NOT_APPROVED")
        self.assertEqual(t["target_gaps"], ["G2"])
        self.assertIs(t["requires_explicit_approval"], True)
        self.denied(evaluate_offline_transition_plan(p, baseline()))

    def test_read_only_mt4_does_not_imply_ea_execution(self):
        p = plan()
        t = transition(p, "MT4_READ_ONLY_PREFLIGHT")
        self.assertEqual(t["scope_rule"], "SEPARATE_APPROVAL_NO_EA_OR_ORDERS")
        self.denied(evaluate_offline_transition_plan(p, baseline()))

    def test_host_io_lab_is_separate_from_mt4_and_still_unapproved(self):
        p = plan()
        t = transition(p, "OFFLINE_PERSISTENCE_LAB")
        self.assertEqual(t["target_gaps"], ["G6", "G7"])
        self.assertIs(t["requires_explicit_approval"], True)
        self.denied(evaluate_offline_transition_plan(p, baseline()))

    def test_demo_execution_design_has_prerequisites_but_no_grant(self):
        p = plan()
        t = transition(p, "DEMO_EXECUTION_EVALUATION")
        self.assertEqual(t["requires_verified_gates"],
                         ["G1", "G2", "G6", "G7", "G8"])
        self.denied(evaluate_offline_transition_plan(p, baseline()))

    def test_live_activation_requires_all_nine_and_separate_consent(self):
        p = plan()
        t = transition(p, "LIVE_ACTIVATION")
        self.assertEqual(set(t["requires_verified_gates"]), set(_IDS))
        self.assertEqual(t["status"], "NOT_APPROVED")
        self.assertIs(t["requires_explicit_approval"], True)
        self.denied(evaluate_offline_transition_plan(p, baseline()))

    def test_false_positive_g2_resolved_rejected(self):
        p = plan()
        gate(p, "G2")["readiness"] = "RESOLVED"
        self.check(p, baseline(), "PLAN_GAPS_REJECTED_FAIL_CLOSED")

    def test_false_positive_g6_real_world_verified_rejected(self):
        p = plan()
        gate(p, "G6")["real_world_verified"] = True
        self.check(p, baseline(), "PLAN_GAPS_REJECTED_FAIL_CLOSED")

    def test_gap_release_blocker_cannot_be_removed(self):
        p = plan()
        gate(p, "G8")["release_blocker"] = False
        self.check(p, baseline(), "PLAN_GAPS_REJECTED_FAIL_CLOSED")

    def test_gap_false_not_bool_rejected(self):
        p = plan()
        gate(p, "G2")["real_world_verified"] = 0
        self.check(p, baseline(), "PLAN_GAPS_REJECTED_FAIL_CLOSED")

    def test_gap_bool_rank_rejected(self):
        p = plan()
        gate(p, "G2")["rank"] = True
        self.check(p, baseline(), "PLAN_GAPS_REJECTED_FAIL_CLOSED")

    def test_gap_priority_order_change_rejected(self):
        p = plan()
        p["gates"][0], p["gates"][1] = p["gates"][1], p["gates"][0]
        self.check(p, baseline(), "PLAN_GAPS_REJECTED_FAIL_CLOSED")

    def test_gap_duplicate_id_rejected(self):
        p = plan()
        p["gates"][1]["id"] = "G2"
        self.check(p, baseline(), "PLAN_GAPS_REJECTED_FAIL_CLOSED")

    def test_gap_missing_or_extra_field_rejected(self):
        p = plan()
        del gate(p, "G2")["external_evidence_required"]
        self.check(p, baseline(), "PLAN_GAPS_REJECTED_FAIL_CLOSED")
        p = plan()
        gate(p, "G6")["is_trusted_anchor_verified"] = True
        self.check(p, baseline(), "PLAN_GAPS_REJECTED_FAIL_CLOSED")

    def test_empty_offline_work_rejected(self):
        p = plan()
        gate(p, "G2")["offline_next"] = []
        self.check(p, baseline(), "PLAN_GAPS_REJECTED_FAIL_CLOSED")

    def test_external_evidence_may_not_be_blank(self):
        p = plan()
        gate(p, "G6")["external_evidence_required"] = [""]
        self.check(p, baseline(), "PLAN_GAPS_REJECTED_FAIL_CLOSED")

    def test_external_evidence_may_not_be_silently_replaced(self):
        p = plan()
        gate(p, "G6")["external_evidence_required"] = ["Synthetic test passed"]
        self.check(p, baseline(), "PLAN_BASELINE_ALIGNMENT_REJECTED_FAIL_CLOSED")

    def test_external_evidence_requirements_are_identical_to_d525(self):
        b = baseline()
        by_id = {x["id"]: x for x in b["gaps"]}
        for item in plan()["gates"]:
            self.assertEqual(item["external_evidence_required"],
                             by_id[item["id"]]["external_or_real_evidence_required"])

    def test_dependency_cycle_rejected(self):
        p = plan()
        gate(p, "G2")["depends_on"] = ["G4"]
        self.check(p, baseline(), "PLAN_DEPENDENCIES_REJECTED_FAIL_CLOSED")

    def test_dependency_early_g2_g6_inversion_rejected(self):
        p = plan()
        gate(p, "G6")["depends_on"] = ["G2"]
        self.check(p, baseline(), "PLAN_DEPENDENCIES_REJECTED_FAIL_CLOSED")

    def test_dependency_boolean_or_wrong_type_rejected(self):
        p = plan()
        gate(p, "G8")["depends_on"] = "G6"
        self.check(p, baseline(), "PLAN_DEPENDENCIES_REJECTED_FAIL_CLOSED")

    def test_dependency_missing_g6_for_g8_rejected(self):
        p = plan()
        gate(p, "G8")["depends_on"] = []
        self.check(p, baseline(), "PLAN_DEPENDENCIES_REJECTED_FAIL_CLOSED")

    def test_transition_status_approved_cannot_be_declared(self):
        p = plan()
        transition(p, "MT4_READ_ONLY_PREFLIGHT")["status"] = "APPROVED"
        self.check(p, baseline(), "PLAN_TRANSITIONS_REJECTED_FAIL_CLOSED")

    def test_transition_approval_requirement_cannot_be_bypassed(self):
        p = plan()
        transition(p, "SINGLE_ENV_VISUAL_REVIEW")[
            "requires_explicit_approval"] = False
        self.check(p, baseline(), "PLAN_TRANSITIONS_REJECTED_FAIL_CLOSED")

    def test_transition_fake_bool_approval_rejected(self):
        p = plan()
        transition(p, "LIVE_ACTIVATION")[
            "requires_explicit_approval"] = 1
        self.check(p, baseline(), "PLAN_TRANSITIONS_REJECTED_FAIL_CLOSED")

    def test_transition_unknown_live_scope_rejected(self):
        p = plan()
        transition(p, "LIVE_ACTIVATION")["scope_rule"] = "LIVE_TRADING_GO"
        self.check(p, baseline(), "PLAN_TRANSITIONS_REJECTED_FAIL_CLOSED")

    def test_transition_circular_prior_rejected(self):
        p = plan()
        transition(p, "MT4_READ_ONLY_PREFLIGHT")[
            "prior_transition"] = "LIVE_ACTIVATION"
        self.check(p, baseline(), "PLAN_TRANSITIONS_REJECTED_FAIL_CLOSED")

    def test_transition_early_demo_order_route_rejected(self):
        p = plan()
        transition(p, "DEMO_EXECUTION_EVALUATION")[
            "requires_verified_gates"] = []
        self.check(p, baseline(), "PLAN_TRANSITIONS_REJECTED_FAIL_CLOSED")

    def test_transition_live_must_require_all_gates(self):
        p = plan()
        transition(p, "LIVE_ACTIVATION")[
            "requires_verified_gates"].pop()
        self.check(p, baseline(), "PLAN_TRANSITIONS_REJECTED_FAIL_CLOSED")

    def test_transition_extra_automatic_grant_flag_rejected(self):
        p = plan()
        transition(p, "LIVE_ACTIVATION")["auto_activate"] = True
        self.check(p, baseline(), "PLAN_TRANSITIONS_REJECTED_FAIL_CLOSED")

    def test_extra_top_level_permission_field_rejected(self):
        p = plan()
        p["orders_authorized"] = True
        self.check(p, baseline(), "PLAN_INPUT_REJECTED_FAIL_CLOSED")

    def test_removed_top_level_field_rejected(self):
        p = plan()
        del p["approval_state"]
        self.check(p, baseline(), "PLAN_INPUT_REJECTED_FAIL_CLOSED")

    def test_changed_environment_mode_rejected(self):
        p = plan()
        p["environment_policy"] = "DUAL_DEMO_B"
        self.check(p, baseline(), "PLAN_INPUT_REJECTED_FAIL_CLOSED")

    def test_rakuten_inquiry_cannot_be_enabled(self):
        p = plan()
        p["rakuten_inquiry"] = "SEND_EMAIL"
        self.check(p, baseline(), "PLAN_INPUT_REJECTED_FAIL_CLOSED")

    def test_verified_values_or_runtime_go_rejected(self):
        p = plan()
        p["verified_values"] = {}
        self.check(p, baseline(), "PLAN_INPUT_REJECTED_FAIL_CLOSED")
        p = plan()
        p["runtime_go_no_go"] = "GO"
        self.check(p, baseline(), "PLAN_INPUT_REJECTED_FAIL_CLOSED")

    def test_bool_schema_version_and_invalid_types_rejected(self):
        p = plan()
        p["schema_version"] = True
        self.check(p, baseline(), "PLAN_INPUT_REJECTED_FAIL_CLOSED")
        for obj in ([], None, "OFFLINE", True):
            with self.subTest(obj=repr(obj)):
                self.check(obj, baseline(), "PLAN_INPUT_REJECTED_FAIL_CLOSED")

    def test_missing_or_false_baseline_release_blocker_rejected(self):
        b = baseline()
        b["gaps"][0]["release_blocker"] = False
        self.check(plan(), b, "PLAN_BASELINE_REJECTED_FAIL_CLOSED")
        b = baseline()
        b["gaps"].pop()
        self.check(plan(), b, "PLAN_BASELINE_REJECTED_FAIL_CLOSED")

    def test_forged_baseline_verified_rejected(self):
        b = baseline()
        b["gaps"][1]["real_world_verified"] = True
        self.check(plan(), b, "PLAN_BASELINE_REJECTED_FAIL_CLOSED")
        b = baseline()
        b["real_order_execution_approved"] = True
        self.check(plan(), b, "PLAN_BASELINE_REJECTED_FAIL_CLOSED")

    def test_corrupted_baseline_severity_or_duplicate_rejected(self):
        b = baseline()
        b["gaps"][0]["severity"] = "LOW"
        self.check(plan(), b, "PLAN_BASELINE_REJECTED_FAIL_CLOSED")
        b = baseline()
        b["gaps"][0]["id"] = "G2"
        self.check(plan(), b, "PLAN_BASELINE_REJECTED_FAIL_CLOSED")

    def test_invalid_baseline_schema_rejected(self):
        for b in (None, [], {}, "LIVE", True):
            with self.subTest(obj=repr(b)):
                self.check(plan(), b, "PLAN_BASELINE_REJECTED_FAIL_CLOSED")

    def test_mutable_inputs_unchanged(self):
        p, b = plan(), baseline()
        old_p, old_b = copy.deepcopy(p), copy.deepcopy(b)
        self.denied(evaluate_offline_transition_plan(p, b))
        self.assertEqual(p, old_p)
        self.assertEqual(b, old_b)

    def test_consecutive_calls_never_inherit_approval(self):
        p, b = plan(), baseline()
        self.check(p, b, "PLAN_DESIGN_VALIDATED_REAL_TRANSITIONS_BLOCKED_NO_GO")
        modified = copy.deepcopy(p)
        transition(modified, "LIVE_ACTIVATION")["status"] = "APPROVED"
        self.check(modified, b, "PLAN_TRANSITIONS_REJECTED_FAIL_CLOSED")
        self.check(p, b, "PLAN_DESIGN_VALIDATED_REAL_TRANSITIONS_BLOCKED_NO_GO")

    def test_every_documented_stage_is_design_only(self):
        p = plan()
        for entry in p["transition_proposals"]:
            with self.subTest(ident=entry["id"]):
                self.assertIn(entry["status"], ("DESIGN_ONLY", "NOT_APPROVED"))
                if entry["status"] == "DESIGN_ONLY":
                    self.assertEqual(entry["scope_rule"],
                                     "DOCUMENTATION_ONLY_NO_RUNTIME")
        self.denied(evaluate_offline_transition_plan(p, baseline()))


if __name__ == "__main__":
    unittest.main()
