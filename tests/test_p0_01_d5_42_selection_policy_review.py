"""D5-42: proof-gated and non-compensable selection policy, synthetic only."""
from __future__ import annotations

import copy
import json
from pathlib import Path
from unittest import TestCase, main
from unittest.mock import patch

from scripts.p0_01_d5_42_selection_policy_review import (
    _FALSE, _CANDIDATES, _HARD, _SOFT, _KNOCKOUTS,
    _STAGES, _REAL_FLAGS, _RECORD_FALSE, _PARENT_KEYS,
    review_d542_selection_rules,
)
from scripts.p0_01_d5_41_anchor_selection_review import (
    review_d541_anchor_candidates,
)
from scripts.p0_01_d5_36_readiness_gate import _BUNDLE_FIELDS

ROOT = Path(__file__).resolve().parents[1]
_MISSING = object()


def read(name):
    with (ROOT / "specs" / name).open(encoding="utf-8") as source:
        return json.load(source)


def contract(): return read("p0_01_d5_42_selection_rules.json")
def scenario(): return read("p0_01_d5_42_synthetic_selection_review.json")


def predecessor():
    p = {
        "d541_contract": read("p0_01_d5_41_anchor_selection_contract.json"),
        "d541_matrix": read("p0_01_d5_41_candidate_evidence_matrix.json"),
    }
    p40 = {
        "d540_contract": read("p0_01_d5_40_trust_boundary_contract.json"),
        "d540_matrix": read("p0_01_d5_40_candidate_threat_matrix.json"),
    }
    p39 = {
        "d539_contract": read("p0_01_d5_39_egress_contract.json"),
        "d539_manifest": read("p0_01_d5_39_synthetic_manifest.json"),
        "d539_public_json": read("p0_01_d5_32_synthetic_fixture.json")["public_json"],
    }
    p38 = {
        "d538_design": read("p0_01_d5_38_private_vault_contract.json"),
        "d538_threat_matrix": read("p0_01_d5_38_threat_matrix.json"),
        "d537_workplan": read("p0_01_d5_37_workplan_contract.json"),
        "d537_tracking": read("p0_01_d5_37_synthetic_tracking.json"),
        "d536_contract": read("p0_01_d5_36_acceptance_contract.json"),
        "d536_readiness": read("p0_01_d5_36_readiness_register.json"),
        "d536_actions": read("p0_01_d5_36_synthetic_authorization.json"),
    }
    sources = (
        "p0_01_d5_35_handoff_contract.json",
        "p0_01_d5_34_lineage_contract.json",
        "p0_01_d5_33_proof_boundary_contract.json",
        "p0_01_d5_32_crash_matrix_contract.json",
        "p0_01_d5_31_protocol_privacy_contract.json",
        "p0_01_d5_17_evidence_reconciliation_status.json",
        "p0_01_d5_25_gap_verification_matrix.json",
        "p0_01_d5_32_synthetic_fixture.json",
        "p0_01_d5_33_synthetic_fixture.json",
        "p0_01_d5_34_synthetic_fixture.json",
        "p0_01_d5_35_synthetic_fixture.json",
    )
    p38["d536_predecessors"] = dict(
        zip(_BUNDLE_FIELDS, (read(x) for x in sources))
    )
    p39["d539_predecessors"] = p38
    p40["d540_predecessor_bundle"] = p39
    p["d541_predecessor"] = p40
    return p


class D542KnockoutTests(TestCase):
    def check(self, expected, c=_MISSING, r=_MISSING, p=_MISSING):
        result = review_d542_selection_rules(
            contract() if c is _MISSING else c,
            scenario() if r is _MISSING else r,
            predecessor() if p is _MISSING else p,
        )
        self.assertEqual(result["status"], expected)
        self.assertEqual(result["runtime_go_no_go"], "NO_GO")
        self.assertEqual(result["phase_1"], "BLOCKED")
        self.assertIsNone(result["verified_values"])
        self.assertIs(result["safety_hold_latched"], True)
        self.assertEqual(result["effective_approved_actions"], [])
        self.assertEqual(result["account_identity_consistency"], "NOT_RECONCILED")
        for key in ("current_positions", "current_pending_orders", "current_ea_state"):
            self.assertEqual(result[key], "UNKNOWN")
        for key, count in (
            ("comparison_candidates", 2),
            ("noncompensable_requirements", 24),
            ("secondary_requirements", 4),
            ("knockout_scenarios", 16),
            ("approval_stages_pending", 6),
            ("real_candidates_selected", 0),
            ("real_independent_evidence_verified", 0),
            ("real_fault_cases_executed", 0),
            ("real_trust_anchors_implemented", 0),
            ("real_evidence_items_collected", 0),
            ("real_work_packages_executed", 0),
            ("real_acceptance_criteria_completed", 0),
        ):
            self.assertEqual(result[key], count, key)
        for key in _FALSE:
            self.assertIs(result[key], False, key)
        self.assertEqual(set(result), set(_FALSE) | {
            "status", "d541_status", "comparison_candidates",
            "noncompensable_requirements", "secondary_requirements",
            "knockout_scenarios", "approval_stages_pending",
            "real_candidates_selected", "real_independent_evidence_verified",
            "real_fault_cases_executed", "real_trust_anchors_implemented",
            "real_evidence_items_collected", "real_work_packages_executed",
            "real_acceptance_criteria_completed",
            "effective_approved_actions", "safety_hold_latched",
            "account_identity_consistency", "current_positions",
            "current_pending_orders", "current_ea_state",
            "phase_1", "runtime_go_no_go", "verified_values",
        })
        return result

    def test_baseline_all_hard_evidence_unknown(self):
        self.check("D542_HARD_KNOCKOUT_POLICY_DOCUMENTED_NO_SELECTION")

    def test_12_hard_axes_per_candidate(self):
        self.assertEqual(len(_HARD), 12)
        self.assertEqual(len(scenario()["hard_checks"]), 24)
        self.check("D542_HARD_KNOCKOUT_POLICY_DOCUMENTED_NO_SELECTION")

    def test_2_soft_axes_per_candidate(self):
        self.assertEqual(_SOFT, ("LIFECYCLE_COST", "OPERATIONAL_BURDEN"))
        self.check("D542_HARD_KNOCKOUT_POLICY_DOCUMENTED_NO_SELECTION")

    def test_failure_recovery_and_data_residency_are_noncompensable(self):
        self.assertIn("FAILURE_RECOVERY", _HARD)
        self.assertIn("DATA_RESIDENCY", _HARD)
        self.check("D542_HARD_KNOCKOUT_POLICY_DOCUMENTED_NO_SELECTION")

    def test_no_score_or_cost_can_override_hard_gates(self):
        self.assertEqual(contract()["secondary_rule"],
                         "ONLY_AFTER_ALL_HARD_GATES_AND_NO_KNOCKOUT")
        self.assertEqual(contract()["knockout_rule"],
                         "ANY_REAL_KNOCKOUT_DISQUALIFIES_NO_OVERRIDE")
        self.check("D542_HARD_KNOCKOUT_POLICY_DOCUMENTED_NO_SELECTION")

    def test_all_8_disqualifiers_for_each_candidate(self):
        self.assertEqual(len(_KNOCKOUTS), 8)
        self.assertEqual(len(scenario()["knockout_cases"]), 16)
        self.check("D542_HARD_KNOCKOUT_POLICY_DOCUMENTED_NO_SELECTION")

    def test_independent_owner_and_privacy_required(self):
        self.assertEqual(contract()["privacy_dependencies"],
                         ["G2-06", "G2-07"])
        self.assertEqual(contract()["upstream_gates"],
                         ["G6-01", "G8"])
        self.check("D542_HARD_KNOCKOUT_POLICY_DOCUMENTED_NO_SELECTION")

    def test_two_independent_approvals_not_merged(self):
        self.assertEqual(contract()["approval_rule"],
            "SEPARATE_HUMAN_DESIGN_SELECTION_AND_SEPARATE_RUNTIME_APPROVAL")
        self.assertFalse(contract()["real_human_design_approved"])
        self.assertFalse(contract()["real_runtime_approved"])
        self.check("D542_HARD_KNOCKOUT_POLICY_DOCUMENTED_NO_SELECTION")

    def test_all_six_review_stages_pending(self):
        self.assertEqual(len(_STAGES), 6)
        self.assertTrue(all(x["review_state"] == "PENDING"
                            for x in scenario()["approval_steps"]))
        self.check("D542_HARD_KNOCKOUT_POLICY_DOCUMENTED_NO_SELECTION")

    def test_synthetic_pass_on_one_hard_gate_not_real_proof(self):
        r = scenario()
        r["hard_checks"][0]["simulated_outcome"] = "SIMULATED_PASS"
        self.check("D542_SYNTHETIC_PASS_NOT_INDEPENDENT_PROOF", r=r)

    def test_synthetic_full_hard_pass_still_no_selection(self):
        r = scenario()
        for item in r["hard_checks"]:
            item["simulated_outcome"] = "SIMULATED_PASS"
        for item in r["knockout_cases"]:
            item["simulated_outcome"] = "SIMULATED_NONVIOLATION"
        self.check("D542_SYNTHETIC_PASS_NOT_INDEPENDENT_PROOF", r=r)

    def test_hard_failure_overrides_cheap_candidate(self):
        r = scenario()
        r["hard_checks"][0]["simulated_outcome"] = "SIMULATED_FAIL"
        r["secondary_checks"][0]["simulated_outcome"] = "SIMULATED_AFFORDABLE"
        self.check("D542_SYNTHETIC_HARD_GATE_FAILURE_NO_SELECTION", r=r)

    def test_knockout_overrides_every_hard_pass(self):
        r = scenario()
        for item in r["hard_checks"]:
            item["simulated_outcome"] = "SIMULATED_PASS"
        r["knockout_cases"][0]["simulated_outcome"] = "SIMULATED_VIOLATION"
        self.check("D542_SYNTHETIC_HARD_KNOCKOUT_NO_SELECTION", r=r)

    def test_knockout_beats_hard_failure_in_diagnostic(self):
        r = scenario()
        r["hard_checks"][0]["simulated_outcome"] = "SIMULATED_FAIL"
        r["knockout_cases"][0]["simulated_outcome"] = "SIMULATED_VIOLATION"
        self.check("D542_SYNTHETIC_HARD_KNOCKOUT_NO_SELECTION", r=r)

    def test_only_soft_cheap_does_not_authorize(self):
        r = scenario()
        r["secondary_checks"][0]["simulated_outcome"] = "SIMULATED_AFFORDABLE"
        self.check("D542_SECONDARY_TRADEOFF_CANNOT_OVERRIDE_UNKNOWN", r=r)

    def test_only_soft_expensive_does_not_authorize(self):
        r = scenario()
        r["secondary_checks"][0]["simulated_outcome"] = "SIMULATED_EXPENSIVE"
        self.check("D542_SECONDARY_TRADEOFF_CANNOT_OVERRIDE_UNKNOWN", r=r)

    def test_soft_cheap_and_full_synthetic_pass_still_no_go(self):
        r = scenario()
        for item in r["hard_checks"]:
            item["simulated_outcome"] = "SIMULATED_PASS"
        r["secondary_checks"][0]["simulated_outcome"] = "SIMULATED_AFFORDABLE"
        self.check("D542_SECONDARY_TRADEOFF_CANNOT_OVERRIDE_UNKNOWN", r=r)

    def test_unknown_is_not_real_eligibility(self):
        self.assertEqual(contract()["unknown_rule"], "UNKNOWN_OR_MISSING_MEANS_NO_GO")
        self.check("D542_HARD_KNOCKOUT_POLICY_DOCUMENTED_NO_SELECTION")

    def test_policy_cannot_select_provider(self):
        self.assertIsNone(contract()["chosen_architecture"])
        self.assertIsNone(scenario()["actual_chosen_candidate"])
        self.check("D542_HARD_KNOCKOUT_POLICY_DOCUMENTED_NO_SELECTION")

    def test_contract_cannot_remove_rollback_axis(self):
        c = contract()
        c["noncompensable_axes"].remove("ROLLBACK_RESISTANCE")
        self.check("D542_SELECTION_RULES_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_contract_cannot_make_stop_continuity_soft(self):
        c = contract()
        c["noncompensable_axes"].remove("STOP_LATCH_CONTINUITY")
        c["secondary_axes"].append("STOP_LATCH_CONTINUITY")
        self.check("D542_SELECTION_RULES_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_contract_no_overlapping_hard_soft(self):
        c = contract()
        c["secondary_axes"].append("ADMIN_BOUNDARY")
        self.check("D542_SELECTION_RULES_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_contract_cannot_auto_choose_low_cost(self):
        c = contract()
        c["secondary_rule"] = "LOWEST_COST_AUTO_WINS"
        self.check("D542_SELECTION_RULES_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_contract_cannot_relax_knockout(self):
        c = contract()
        c["knockout_rule"] = "SOFT_WARNING"
        self.check("D542_SELECTION_RULES_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_contract_cannot_collapse_human_approval(self):
        c = contract()
        c["approval_rule"] = "DESIGN_APPROVAL_ALSO_TRADING_APPROVAL"
        self.check("D542_SELECTION_RULES_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_contract_cannot_forge_selected_architecture(self):
        c = contract()
        c["chosen_architecture"] = _CANDIDATES[0]
        self.check("D542_SELECTION_RULES_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_contract_requires_g2_privacy_boundary(self):
        c = contract()
        c["privacy_dependencies"] = ["G2-06"]
        self.check("D542_SELECTION_RULES_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_contract_requires_g8(self):
        c = contract()
        c["upstream_gates"] = ["G6-01"]
        self.check("D542_SELECTION_RULES_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_contract_no_runtime_go(self):
        c = contract()
        c["runtime_go_no_go"] = "GO"
        self.check("D542_SELECTION_RULES_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_contract_no_fake_verified_values(self):
        c = contract()
        c["verified_values"] = {}
        self.check("D542_SELECTION_RULES_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_contract_schema_boolean_rejected(self):
        c = contract()
        c["schema_version"] = True
        self.check("D542_SELECTION_RULES_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_no_missing_hard_check(self):
        r = scenario()
        r["hard_checks"].pop()
        self.check("D542_SCENARIO_SCHEMA_REJECTED_FAIL_CLOSED", r=r)

    def test_no_duplicate_hard_check(self):
        r = scenario()
        r["hard_checks"][1] = copy.deepcopy(r["hard_checks"][0])
        self.check("D542_SCENARIO_SCHEMA_REJECTED_FAIL_CLOSED", r=r)

    def test_no_swapped_soft_items(self):
        r = scenario()
        r["secondary_checks"].reverse()
        self.check("D542_SCENARIO_SCHEMA_REJECTED_FAIL_CLOSED", r=r)

    def test_no_deleted_knockout_case(self):
        r = scenario()
        r["knockout_cases"].pop()
        self.check("D542_SCENARIO_SCHEMA_REJECTED_FAIL_CLOSED", r=r)

    def test_no_reordered_approval_stages(self):
        r = scenario()
        r["approval_steps"].reverse()
        self.check("D542_SCENARIO_SCHEMA_REJECTED_FAIL_CLOSED", r=r)

    def test_no_unknown_hard_outcome(self):
        r = scenario()
        r["hard_checks"][0]["simulated_outcome"] = "REAL_PASS"
        self.check("D542_SCENARIO_SCHEMA_REJECTED_FAIL_CLOSED", r=r)

    def test_no_unknown_soft_outcome(self):
        r = scenario()
        r["secondary_checks"][0]["simulated_outcome"] = "ACTUAL_QUOTE"
        self.check("D542_SCENARIO_SCHEMA_REJECTED_FAIL_CLOSED", r=r)

    def test_no_unknown_knockout_outcome(self):
        r = scenario()
        r["knockout_cases"][0]["simulated_outcome"] = "PASSED_REAL"
        self.check("D542_SCENARIO_SCHEMA_REJECTED_FAIL_CLOSED", r=r)

    def test_no_real_evidence_field(self):
        r = scenario()
        r["hard_checks"][0]["real_independent_proof"] = "SYNTHETIC_ONLY"
        self.check("D542_SCENARIO_SCHEMA_REJECTED_FAIL_CLOSED", r=r)

    def test_no_real_quote_field(self):
        r = scenario()
        r["secondary_checks"][0]["real_quotation"] = "SYNTHETIC_ONLY"
        self.check("D542_SCENARIO_SCHEMA_REJECTED_FAIL_CLOSED", r=r)

    def test_no_record_of_real_selection(self):
        r = scenario()
        r["actual_chosen_candidate"] = _CANDIDATES[1]
        self.check("D542_SCENARIO_SCHEMA_REJECTED_FAIL_CLOSED", r=r)

    def test_no_real_broker_account_state(self):
        r = scenario()
        r["current_positions"] = "EMPTY"
        self.check("D542_SCENARIO_SCHEMA_REJECTED_FAIL_CLOSED", r=r)

    def test_no_real_human_approval_reference(self):
        r = scenario()
        r["approval_steps"][0]["real_evidence_reference"] = "SYNTHETIC"
        self.check("D542_SCENARIO_SCHEMA_REJECTED_FAIL_CLOSED", r=r)

    def test_no_record_extra_raw_secret(self):
        r = scenario()
        r["broker_password"] = "SYNTHETIC_SENTINEL"
        self.check("D542_SCENARIO_SCHEMA_REJECTED_FAIL_CLOSED", r=r)

    def test_no_approval_stage_skipping(self):
        r = scenario()
        r["approval_steps"][0]["review_state"] = "DONE"
        self.check("D542_SCENARIO_SCHEMA_REJECTED_FAIL_CLOSED", r=r)

    def test_no_bool_as_int_schema(self):
        r = scenario()
        r["schema_version"] = True
        self.check("D542_SCENARIO_SCHEMA_REJECTED_FAIL_CLOSED", r=r)

    def test_invalid_contract_objects_rejected(self):
        for value in (None, [], True, {}, "GO"):
            with self.subTest(value=repr(value)):
                self.check("D542_SELECTION_RULES_CONTRACT_REJECTED_FAIL_CLOSED",
                           c=value)

    def test_invalid_scenario_objects_rejected(self):
        for value in (None, [], True, {}, "GO"):
            with self.subTest(value=repr(value)):
                self.check("D542_SCENARIO_SCHEMA_REJECTED_FAIL_CLOSED",
                           r=value)

    def test_missing_predecessor_bundle_denied(self):
        self.check("D542_PREDECESSOR_BUNDLE_REJECTED_FAIL_CLOSED", p={})

    def test_predecessor_real_anchor_forgery_denied(self):
        p = predecessor()
        p["d541_matrix"]["actual_candidate_selected"] = True
        self.check("D542_PREDECESSOR_NOT_COHERENT_NO_GO", p=p)

    def test_predecessor_independent_cost_proof_forgery_denied(self):
        p = predecessor()
        p["d541_contract"]["actual_cost_quotes_collected"] = True
        self.check("D542_PREDECESSOR_NOT_COHERENT_NO_GO", p=p)

    def test_predecessor_fake_stop_release_denied(self):
        p = predecessor()
        p["d541_predecessor"]["d540_predecessor_bundle"][
            "d539_predecessors"]["d536_predecessors"][
            "d535_case"]["stop_release_claim"] = True
        self.check("D542_PREDECESSOR_NOT_COHERENT_NO_GO", p=p)

    def test_forged_parent_runtime_go_denied(self):
        with patch(
            "scripts.p0_01_d5_42_selection_policy_review.review_d541_anchor_candidates",
            return_value={
                "status":"D541_EVIDENCE_MATRIX_COMPLETE_NO_SELECTION_OR_REAL_PROOF",
                "runtime_go_no_go":"GO",
            },
        ):
            self.check("D542_PREDECESSOR_SAFETY_INVARIANT_FAIL_CLOSED")

    def test_forged_parent_proof_count_denied(self):
        p = predecessor()
        v = review_d541_anchor_candidates(*(p[k] for k in _PARENT_KEYS))
        v["real_independent_evidence_verified"] = 28
        with patch(
            "scripts.p0_01_d5_42_selection_policy_review.review_d541_anchor_candidates",
            return_value=v,
        ):
            self.check("D542_PREDECESSOR_SAFETY_INVARIANT_FAIL_CLOSED")

    def test_forged_parent_status_denied(self):
        p = predecessor()
        v = review_d541_anchor_candidates(*(p[k] for k in _PARENT_KEYS))
        v["status"] = "REAL_VERIFIED"
        with patch(
            "scripts.p0_01_d5_42_selection_policy_review.review_d541_anchor_candidates",
            return_value=v,
        ):
            self.check("D542_PREDECESSOR_NOT_COHERENT_NO_GO")

    def test_pure_review_does_not_open_os_files(self):
        args = (contract(), scenario(), predecessor())
        with patch("builtins.open", side_effect=AssertionError("NO FILE IO")):
            v = review_d542_selection_rules(*args)
        self.assertEqual(v["runtime_go_no_go"], "NO_GO")

    def test_review_does_not_mutate_inputs(self):
        args = (contract(), scenario(), predecessor())
        before = copy.deepcopy(args)
        review_d542_selection_rules(*args)
        self.assertEqual(args, before)

    def test_invalid_input_no_secret_echo(self):
        r = scenario()
        r["secret"] = "SYNTHETIC_NON_SECRET_SENTINEL"
        v = self.check("D542_SCENARIO_SCHEMA_REJECTED_FAIL_CLOSED", r=r)
        self.assertNotIn("SYNTHETIC_NON_SECRET_SENTINEL", repr(v))

    def test_status_zero_real_evidence_and_selection(self):
        s = read("p0_01_d5_42_status.json")
        self.assertEqual(s["unresolved_gates"], [f"G{i}" for i in range(1, 10)])
        self.assertEqual(s["phase_1"], "BLOCKED")
        self.assertEqual(s["runtime_go_no_go"], "NO_GO")
        self.assertIsNone(s["verified_values"])
        self.assertEqual(s["real_candidates_selected"], 0)
        self.assertEqual(s["real_independent_evidence_verified"], 0)
        self.assertEqual(s["real_trust_anchors_implemented"], 0)
        self.assertEqual(s["real_acceptance_criteria_completed"], 0)
        for name in ("g2_real_world_resolved", "g6_real_world_resolved",
                     "broker_verified", "host_io_approved",
                     "terminal_execution_approved", "forward_trading_enabled"):
            self.assertIs(s[name], False)

    def test_repeated_fail_safe_evaluation(self):
        self.check("D542_HARD_KNOCKOUT_POLICY_DOCUMENTED_NO_SELECTION")
        r = scenario()
        r["knockout_cases"][0]["simulated_outcome"] = "SIMULATED_VIOLATION"
        self.check("D542_SYNTHETIC_HARD_KNOCKOUT_NO_SELECTION", r=r)
        self.check("D542_HARD_KNOCKOUT_POLICY_DOCUMENTED_NO_SELECTION")


def _hard_test(index, field, value, expected):
    def test(self):
        r = scenario()
        r["hard_checks"][index][field] = value
        self.check(expected, r=r)
    return test


def _soft_test(index, field, value, expected):
    def test(self):
        r = scenario()
        r["secondary_checks"][index][field] = value
        self.check(expected, r=r)
    return test


def _knockout_test(index, field, value, expected):
    def test(self):
        r = scenario()
        r["knockout_cases"][index][field] = value
        self.check(expected, r=r)
    return test


def _approval_test(index):
    def test(self):
        r = scenario()
        r["approval_steps"][index]["real_human_signoff"] = True
        self.check("D542_FALSE_REAL_APPROVAL_OR_PROOF_NO_GO", r=r)
    return test


def _contract_real_test(field):
    def test(self):
        c = contract()
        c[field] = True
        self.check("D542_SELECTION_RULES_CONTRACT_REJECTED_FAIL_CLOSED", c=c)
    return test


def _record_real_test(field):
    def test(self):
        r = scenario()
        r[field] = True
        self.check("D542_FALSE_REAL_APPROVAL_OR_PROOF_NO_GO", r=r)
    return test


for _i in range(2 * len(_HARD)):
    for _field, _value, _expected in (
        ("simulated_outcome", "SIMULATED_PASS",
         "D542_SYNTHETIC_PASS_NOT_INDEPENDENT_PROOF"),
        ("simulated_outcome", "SIMULATED_FAIL",
         "D542_SYNTHETIC_HARD_GATE_FAILURE_NO_SELECTION"),
        ("real_approval_granted", True,
         "D542_FALSE_REAL_APPROVAL_OR_PROOF_NO_GO"),
    ):
        setattr(D542KnockoutTests, f"test_hard_{_i:02d}_{_field}_{_value}",
                _hard_test(_i, _field, _value, _expected))

for _i in range(2 * len(_SOFT)):
    for _field, _value, _expected in (
        ("simulated_outcome", "SIMULATED_AFFORDABLE",
         "D542_SECONDARY_TRADEOFF_CANNOT_OVERRIDE_UNKNOWN"),
        ("simulated_outcome", "SIMULATED_EXPENSIVE",
         "D542_SECONDARY_TRADEOFF_CANNOT_OVERRIDE_UNKNOWN"),
        ("real_human_review", True,
         "D542_FALSE_REAL_APPROVAL_OR_PROOF_NO_GO"),
    ):
        setattr(D542KnockoutTests, f"test_soft_{_i:02d}_{_field}_{_value}",
                _soft_test(_i, _field, _value, _expected))

for _i in range(2 * len(_KNOCKOUTS)):
    for _field, _value, _expected in (
        ("simulated_outcome", "SIMULATED_VIOLATION",
         "D542_SYNTHETIC_HARD_KNOCKOUT_NO_SELECTION"),
        ("simulated_outcome", "SIMULATED_NONVIOLATION",
         "D542_SYNTHETIC_PASS_NOT_INDEPENDENT_PROOF"),
        ("real_fault_executed", True,
         "D542_FALSE_REAL_APPROVAL_OR_PROOF_NO_GO"),
        ("real_disqualification_proven", True,
         "D542_FALSE_REAL_APPROVAL_OR_PROOF_NO_GO"),
    ):
        setattr(D542KnockoutTests, f"test_knock_{_i:02d}_{_field}_{_value}",
                _knockout_test(_i, _field, _value, _expected))

for _i in range(len(_STAGES)):
    setattr(D542KnockoutTests, f"test_no_approval_step_{_i}",
            _approval_test(_i))

for _flag in _REAL_FLAGS:
    setattr(D542KnockoutTests, f"test_contract_no_real_{_flag}",
            _contract_real_test(_flag))

for _flag in _RECORD_FALSE:
    setattr(D542KnockoutTests, f"test_scenario_no_real_{_flag}",
            _record_real_test(_flag))


if __name__ == "__main__":
    main()
