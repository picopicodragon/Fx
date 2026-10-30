"""G6-02 D5-41 independent anchor candidate comparison: design-only tests."""
from __future__ import annotations

import copy
import json
from pathlib import Path
from unittest import TestCase, main
from unittest.mock import patch

from scripts.p0_01_d5_41_anchor_selection_review import (
    _FALSE, _CANDIDATES, _AXES, _FAULTS,
    _NO_CLAIM, _MATRIX_FLAGS, _PARENT_KEYS,
    review_d541_anchor_candidates,
)
from scripts.p0_01_d5_40_trust_boundary_review import review_d540_trust_boundary
from scripts.p0_01_d5_36_readiness_gate import _BUNDLE_FIELDS

ROOT = Path(__file__).resolve().parents[1]
_MISSING = object()


def read(name):
    with (ROOT / "specs" / name).open(encoding="utf-8") as source:
        return json.load(source)


def contract(): return read("p0_01_d5_41_anchor_selection_contract.json")
def matrix(): return read("p0_01_d5_41_candidate_evidence_matrix.json")


def predecessor():
    bundle = {
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
    names = (
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
        zip(_BUNDLE_FIELDS, (read(n) for n in names))
    )
    p39["d539_predecessors"] = p38
    bundle["d540_predecessor_bundle"] = p39
    return bundle


class D541AnchorSelectionTests(TestCase):
    def check(self, expected, c=_MISSING, m=_MISSING, p=_MISSING):
        result = review_d541_anchor_candidates(
            contract() if c is _MISSING else c,
            matrix() if m is _MISSING else m,
            predecessor() if p is _MISSING else p,
        )
        self.assertEqual(result["status"], expected)
        self.assertEqual(result["runtime_go_no_go"], "NO_GO")
        self.assertEqual(result["phase_1"], "BLOCKED")
        self.assertIsNone(result["verified_values"])
        self.assertIs(result["safety_hold_latched"], True)
        self.assertEqual(result["effective_approved_actions"], [])
        self.assertEqual(result["account_identity_consistency"], "NOT_RECONCILED")
        for k in ("current_positions", "current_pending_orders",
                  "current_ea_state"):
            self.assertEqual(result[k], "UNKNOWN")
        for k, expected_value in (
            ("candidate_comparison_count", 2),
            ("design_evidence_requirements", 28),
            ("design_fault_cases", 16),
            ("real_candidates_selected", 0),
            ("real_independent_evidence_verified", 0),
            ("real_trust_anchors_implemented", 0),
            ("real_evidence_items_collected", 0),
            ("real_work_packages_executed", 0),
            ("real_acceptance_criteria_completed", 0),
        ):
            self.assertEqual(result[k], expected_value, k)
        for k in _FALSE:
            self.assertIs(result[k], False, k)
        self.assertEqual(set(result), set(_FALSE) | {
            "status", "d540_status", "candidate_comparison_count",
            "design_evidence_requirements", "design_fault_cases",
            "real_candidates_selected", "real_independent_evidence_verified",
            "real_trust_anchors_implemented", "real_evidence_items_collected",
            "real_work_packages_executed", "real_acceptance_criteria_completed",
            "effective_approved_actions", "safety_hold_latched",
            "account_identity_consistency", "current_positions",
            "current_pending_orders", "current_ea_state", "phase_1",
            "runtime_go_no_go", "verified_values",
        })
        return result

    def test_baseline_is_unselected_no_go(self):
        r = self.check(
            "D541_EVIDENCE_MATRIX_COMPLETE_NO_SELECTION_OR_REAL_PROOF")
        self.assertEqual(
            r["d540_status"],
            "D540_TRUST_BOUNDARY_CANDIDATES_DOCUMENTED_NO_REAL_ANCHOR",
        )

    def test_hardware_and_remote_are_only_compared_candidates(self):
        self.assertEqual(
            contract()["candidate_ids"],
            [c[0] for c in _CANDIDATES],
        )
        self.assertEqual(len(_CANDIDATES), 2)
        self.check("D541_EVIDENCE_MATRIX_COMPLETE_NO_SELECTION_OR_REAL_PROOF")

    def test_no_local_mirror_mistaken_as_root(self):
        self.assertNotIn("SAME_PROCESS_MIRROR", contract()["candidate_ids"])
        self.check("D541_EVIDENCE_MATRIX_COMPLETE_NO_SELECTION_OR_REAL_PROOF")

    def test_no_same_host_different_user_as_independent_root(self):
        self.assertNotIn("SAME_HOST_DIFFERENT_USER", contract()["candidate_ids"])
        self.check("D541_EVIDENCE_MATRIX_COMPLETE_NO_SELECTION_OR_REAL_PROOF")

    def test_ten_g6_01_axes_preserved(self):
        from scripts.p0_01_d5_40_trust_boundary_review import _TESTS
        self.assertEqual(
            tuple(contract()["comparison_axes"][:10]), _TESTS,
        )
        self.check("D541_EVIDENCE_MATRIX_COMPLETE_NO_SELECTION_OR_REAL_PROOF")

    def test_cost_operational_recovery_residency_also_covered(self):
        self.assertEqual(contract()["comparison_axes"][-4:], [
            "LIFECYCLE_COST", "OPERATIONAL_BURDEN",
            "FAILURE_RECOVERY", "DATA_RESIDENCY",
        ])
        self.check("D541_EVIDENCE_MATRIX_COMPLETE_NO_SELECTION_OR_REAL_PROOF")

    def test_no_numeric_price_or_vendor_quoted(self):
        self.assertTrue(all(
            c["real_cost_quote"] is None and c["real_provider_id"] is None
            for c in matrix()["candidates"]
        ))
        self.assertTrue(all(
            r["real_cost_amount"] is None
            for r in matrix()["evidence_requirements"]
        ))
        self.check("D541_EVIDENCE_MATRIX_COMPLETE_NO_SELECTION_OR_REAL_PROOF")

    def test_no_private_anchor_endpoint_in_design(self):
        self.assertTrue(all(
            c["real_anchor_endpoint"] is None for c in matrix()["candidates"]
        ))
        self.check("D541_EVIDENCE_MATRIX_COMPLETE_NO_SELECTION_OR_REAL_PROOF")

    def test_no_auto_selection_or_weighted_score(self):
        self.assertEqual(
            contract()["selection_policy"],
            "NO_WEIGHTED_SCORE_OR_AUTO_WINNER",
        )
        self.assertIsNone(contract()["chosen_architecture"])
        self.check("D541_EVIDENCE_MATRIX_COMPLETE_NO_SELECTION_OR_REAL_PROOF")

    def test_independent_real_attestation_is_future_requirement(self):
        self.assertEqual(
            contract()["real_acceptance_evidence_policy"],
            "OUT_OF_BAND_AND_INDEPENDENT_REQUIRED",
        )
        self.check("D541_EVIDENCE_MATRIX_COMPLETE_NO_SELECTION_OR_REAL_PROOF")

    def test_human_selection_required_not_granted(self):
        self.assertIs(contract()["human_design_selection_required"], True)
        self.assertIs(contract()["real_human_approval_granted"], False)
        self.check("D541_EVIDENCE_MATRIX_COMPLETE_NO_SELECTION_OR_REAL_PROOF")

    def test_external_g8_approval_not_verified(self):
        self.assertEqual(contract()["external_approval_gate"], "G8")
        self.assertIs(matrix()["external_g8_approval_verified"], False)
        self.check("D541_EVIDENCE_MATRIX_COMPLETE_NO_SELECTION_OR_REAL_PROOF")

    def test_faults_all_hold_stop(self):
        self.assertTrue(all(
            s["expected_reaction"] == "DENY_AND_HOLD_STOP"
            and s["test_state"] == "NOT_RUN"
            for s in matrix()["failure_scenarios"]
        ))
        self.check("D541_EVIDENCE_MATRIX_COMPLETE_NO_SELECTION_OR_REAL_PROOF")

    def test_no_unsupported_real_fee_estimation(self):
        self.assertEqual(contract()["cost_evidence_policy"],
                         "NO_UNVERIFIED_CURRENCY_PRICE_OR_PROVIDER_SLA")
        self.check("D541_EVIDENCE_MATRIX_COMPLETE_NO_SELECTION_OR_REAL_PROOF")

    def test_28_expected_criteria_exact_and_unique(self):
        ids = [r["criterion_id"] for r in matrix()["evidence_requirements"]]
        self.assertEqual(len(ids), 28)
        self.assertEqual(len(set(ids)), 28)
        self.check("D541_EVIDENCE_MATRIX_COMPLETE_NO_SELECTION_OR_REAL_PROOF")

    def test_16_fault_ids_exact_and_unique(self):
        ids = [r["scenario_id"] for r in matrix()["failure_scenarios"]]
        self.assertEqual(len(ids), 16)
        self.assertEqual(len(set(ids)), 16)
        self.check("D541_EVIDENCE_MATRIX_COMPLETE_NO_SELECTION_OR_REAL_PROOF")

    def test_contract_wrong_target_denied(self):
        c = contract()
        c["target_criterion"] = "G6-01"
        self.check("D541_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_contract_removing_g6_01_dependency_denied(self):
        c = contract()
        c["depends_on"] = []
        self.check("D541_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_contract_removed_privacy_dependency_denied(self):
        c = contract()
        c["privacy_dependencies"].pop()
        self.check("D541_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_contract_removing_g8_denied(self):
        c = contract()
        c["external_approval_gate"] = "NONE"
        self.check("D541_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_contract_reordering_candidates_denied(self):
        c = contract()
        c["candidate_ids"].reverse()
        self.check("D541_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_contract_swapping_evidence_axes_denied(self):
        c = contract()
        c["comparison_axes"].reverse()
        self.check("D541_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_contract_fake_cost_quote_policy_denied(self):
        c = contract()
        c["cost_evidence_policy"] = "COST_CONFIRMED"
        self.check("D541_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_contract_fake_auto_winner_denied(self):
        c = contract()
        c["selection_policy"] = "AUTO_PICK_CHEAPEST"
        self.check("D541_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_contract_fake_architecture_chosen_denied(self):
        c = contract()
        c["chosen_architecture"] = _CANDIDATES[0][0]
        self.check("D541_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_contract_boolean_schema_denied(self):
        c = contract()
        c["schema_version"] = True
        self.check("D541_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_contract_fake_go_denied(self):
        c = contract()
        c["runtime_go_no_go"] = "GO"
        self.check("D541_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_contract_forged_verified_values_denied(self):
        c = contract()
        c["verified_values"] = {}
        self.check("D541_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_contract_extra_real_secret_field_denied(self):
        c = contract()
        c["real_secret"] = "SYNTHETIC_PLACEHOLDER"
        self.check("D541_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_matrix_candidate_order_denied(self):
        m = matrix()
        m["candidates"].reverse()
        self.check("D541_EVIDENCE_MATRIX_SCHEMA_REJECTED_FAIL_CLOSED", m=m)

    def test_matrix_evidence_order_denied(self):
        m = matrix()
        m["evidence_requirements"].reverse()
        self.check("D541_EVIDENCE_MATRIX_SCHEMA_REJECTED_FAIL_CLOSED", m=m)

    def test_matrix_duplicate_evidence_denied(self):
        m = matrix()
        m["evidence_requirements"][1] = copy.deepcopy(m["evidence_requirements"][0])
        self.check("D541_EVIDENCE_MATRIX_SCHEMA_REJECTED_FAIL_CLOSED", m=m)

    def test_matrix_missing_evidence_denied(self):
        m = matrix()
        m["evidence_requirements"].pop()
        self.check("D541_EVIDENCE_MATRIX_SCHEMA_REJECTED_FAIL_CLOSED", m=m)

    def test_matrix_fault_reorder_denied(self):
        m = matrix()
        m["failure_scenarios"].reverse()
        self.check("D541_EVIDENCE_MATRIX_SCHEMA_REJECTED_FAIL_CLOSED", m=m)

    def test_matrix_fault_duplicate_denied(self):
        m = matrix()
        m["failure_scenarios"][1] = copy.deepcopy(m["failure_scenarios"][0])
        self.check("D541_EVIDENCE_MATRIX_SCHEMA_REJECTED_FAIL_CLOSED", m=m)

    def test_matrix_fault_missing_denied(self):
        m = matrix()
        m["failure_scenarios"].pop()
        self.check("D541_EVIDENCE_MATRIX_SCHEMA_REJECTED_FAIL_CLOSED", m=m)

    def test_matrix_fake_cost_amount_denied(self):
        m = matrix()
        m["evidence_requirements"][-4]["real_cost_amount"] = 100
        self.check("D541_EVIDENCE_MATRIX_SCHEMA_REJECTED_FAIL_CLOSED", m=m)

    def test_matrix_real_evidence_payload_denied(self):
        m = matrix()
        m["evidence_requirements"][0]["actual_evidence"] = "SYNTHETIC"
        self.check("D541_EVIDENCE_MATRIX_SCHEMA_REJECTED_FAIL_CLOSED", m=m)

    def test_matrix_fake_real_quote_denied(self):
        m = matrix()
        m["candidates"][0]["real_cost_quote"] = "SYNTHETIC"
        self.check("D541_EVIDENCE_MATRIX_SCHEMA_REJECTED_FAIL_CLOSED", m=m)

    def test_matrix_real_operator_identity_denied(self):
        m = matrix()
        m["candidates"][1]["real_provider_id"] = "SYNTHETIC"
        self.check("D541_EVIDENCE_MATRIX_SCHEMA_REJECTED_FAIL_CLOSED", m=m)

    def test_matrix_unknown_time_denied(self):
        m = matrix()
        m["observed_at_utc"] = "2026-10-30T00:00:00Z"
        self.check("D541_EVIDENCE_MATRIX_SCHEMA_REJECTED_FAIL_CLOSED", m=m)

    def test_matrix_unknown_account_state_denied(self):
        m = matrix()
        m["current_pending_orders"] = "NONE"
        self.check("D541_EVIDENCE_MATRIX_SCHEMA_REJECTED_FAIL_CLOSED", m=m)

    def test_matrix_unresolved_gates_immutable(self):
        m = matrix()
        m["unresolved_gates"] = ["G6"]
        self.check("D541_EVIDENCE_MATRIX_SCHEMA_REJECTED_FAIL_CLOSED", m=m)

    def test_matrix_unrecognized_fault_denied(self):
        m = matrix()
        m["failure_scenarios"][0]["fault_id"] = "ACTUAL_CRASH"
        self.check("D541_EVIDENCE_MATRIX_SCHEMA_REJECTED_FAIL_CLOSED", m=m)

    def test_matrix_fault_stop_policy_cannot_relax(self):
        m = matrix()
        m["failure_scenarios"][0]["expected_reaction"] = "AUTO_RETRY"
        self.check("D541_EVIDENCE_MATRIX_SCHEMA_REJECTED_FAIL_CLOSED", m=m)

    def test_matrix_signed_attestation_does_not_unlock_anything(self):
        m = matrix()
        m["real_signed_attestation_verified"] = True
        self.check("D541_FALSE_EVIDENCE_OR_SELECTION_NO_GO", m=m)

    def test_matrix_rejected_candidate_status_is_not_selected(self):
        m = matrix()
        m["candidates"][0]["actual_candidate_selected"] = True
        self.check("D541_FALSE_EVIDENCE_OR_SELECTION_NO_GO", m=m)

    def test_predecessor_bundle_must_have_three_items(self):
        self.check("D541_PREDECESSOR_BUNDLE_REJECTED_FAIL_CLOSED", p={})

    def test_predecessor_refuses_trust_root_claim(self):
        p = predecessor()
        p["d540_matrix"]["external_anchor_verified"] = True
        self.check("D541_PREDECESSOR_NOT_COHERENT_NO_GO", p=p)

    def test_predecessor_refuses_private_data_egress(self):
        p = predecessor()
        p["d540_predecessor_bundle"]["d539_manifest"]["items"][0][
            "private_data_attached"] = True
        self.check("D541_PREDECESSOR_NOT_COHERENT_NO_GO", p=p)

    def test_predecessor_refuses_real_mt4_access(self):
        p = predecessor()
        p["d540_contract"]["mt4_access_approved"] = True
        self.check("D541_PREDECESSOR_NOT_COHERENT_NO_GO", p=p)

    def test_forged_child_go_rejected(self):
        with patch(
            "scripts.p0_01_d5_41_anchor_selection_review.review_d540_trust_boundary",
            return_value={
                "status":"D540_TRUST_BOUNDARY_CANDIDATES_DOCUMENTED_NO_REAL_ANCHOR",
                "runtime_go_no_go":"GO",
            },
        ):
            self.check("D541_PREDECESSOR_SAFETY_INVARIANT_FAIL_CLOSED")

    def test_forged_child_anchor_implemented_rejected(self):
        p = predecessor()
        child = review_d540_trust_boundary(*(p[k] for k in _PARENT_KEYS))
        child["real_trust_anchors_implemented"] = 1
        with patch(
            "scripts.p0_01_d5_41_anchor_selection_review.review_d540_trust_boundary",
            return_value=child,
        ):
            self.check("D541_PREDECESSOR_SAFETY_INVARIANT_FAIL_CLOSED")

    def test_forged_child_status_rejected(self):
        p = predecessor()
        child = review_d540_trust_boundary(*(p[k] for k in _PARENT_KEYS))
        child["status"] = "REAL_VERIFIED"
        with patch(
            "scripts.p0_01_d5_41_anchor_selection_review.review_d540_trust_boundary",
            return_value=child,
        ):
            self.check("D541_PREDECESSOR_NOT_COHERENT_NO_GO")

    def test_reviewer_has_no_os_io(self):
        args = (contract(), matrix(), predecessor())
        with patch("builtins.open", side_effect=AssertionError("No OS I/O")):
            v = review_d541_anchor_candidates(*args)
        self.assertEqual(v["runtime_go_no_go"], "NO_GO")

    def test_reviewer_does_not_mutate_untrusted_inputs(self):
        args = (contract(), matrix(), predecessor())
        original = copy.deepcopy(args)
        review_d541_anchor_candidates(*args)
        self.assertEqual(args, original)

    def test_no_sensitive_input_echoed(self):
        m = matrix()
        m["actual_secret"] = "SYNTHETIC_MARKER_NOT_SECRET"
        r = self.check("D541_EVIDENCE_MATRIX_SCHEMA_REJECTED_FAIL_CLOSED", m=m)
        self.assertNotIn("SYNTHETIC_MARKER_NOT_SECRET", repr(r))

    def test_invalid_contract_types_rejected(self):
        for value in (None, True, [], {}, "GO"):
            with self.subTest(value=repr(value)):
                self.check("D541_CONTRACT_REJECTED_FAIL_CLOSED", c=value)

    def test_invalid_matrix_types_rejected(self):
        for value in (None, True, [], {}, "GO"):
            with self.subTest(value=repr(value)):
                self.check("D541_EVIDENCE_MATRIX_SCHEMA_REJECTED_FAIL_CLOSED", m=value)

    def test_repeated_calls_never_imply_approval(self):
        self.check("D541_EVIDENCE_MATRIX_COMPLETE_NO_SELECTION_OR_REAL_PROOF")
        m = matrix()
        m["actual_candidate_selected"] = True
        self.check("D541_FALSE_EVIDENCE_OR_SELECTION_NO_GO", m=m)
        self.check("D541_EVIDENCE_MATRIX_COMPLETE_NO_SELECTION_OR_REAL_PROOF")

    def test_status_zero_selection_and_evidence(self):
        s = read("p0_01_d5_41_status.json")
        self.assertEqual(s["unresolved_gates"], [f"G{i}" for i in range(1, 10)])
        self.assertEqual(s["phase_1"], "BLOCKED")
        self.assertEqual(s["runtime_go_no_go"], "NO_GO")
        self.assertIsNone(s["verified_values"])
        self.assertEqual(s["real_candidates_selected"], 0)
        self.assertEqual(s["real_trust_anchors_implemented"], 0)
        self.assertEqual(s["real_acceptance_criteria_completed"], 0)
        for k in ("g2_real_world_resolved", "g6_real_world_resolved",
                  "broker_verified", "host_io_approved",
                  "terminal_execution_approved", "forward_trading_enabled"):
            self.assertIs(s[k], False)


def _requirement_false_test(index, field, value):
    def test(self):
        m = matrix()
        m["evidence_requirements"][index][field] = value
        self.check("D541_FALSE_EVIDENCE_OR_SELECTION_NO_GO", m=m)
    return test


def _fault_false_test(index, field):
    def test(self):
        m = matrix()
        m["failure_scenarios"][index][field] = (
            "PERFORMED" if field == "test_state" else True
        )
        self.check("D541_FALSE_EVIDENCE_OR_SELECTION_NO_GO", m=m)
    return test


def _candidate_false_test(index, field):
    def test(self):
        m = matrix()
        m["candidates"][index][field] = True
        self.check("D541_FALSE_EVIDENCE_OR_SELECTION_NO_GO", m=m)
    return test


def _contract_action_test(field):
    def test(self):
        c = contract()
        c[field] = True
        self.check("D541_CONTRACT_REJECTED_FAIL_CLOSED", c=c)
    return test


def _matrix_action_test(field):
    def test(self):
        m = matrix()
        m[field] = True
        self.check("D541_FALSE_EVIDENCE_OR_SELECTION_NO_GO", m=m)
    return test


for _i in range(len(_CANDIDATES) * len(_AXES)):
    for _field, _value in (
        ("real_evidence_status", "VERIFIED"),
        ("human_review_status", "GRANTED"),
        ("actual_acceptance", True),
    ):
        setattr(D541AnchorSelectionTests, f"test_req_{_i:02d}_{_field}",
                _requirement_false_test(_i, _field, _value))

for _i in range(len(_CANDIDATES) * len(_FAULTS)):
    for _field in (
        "real_fault_executed", "real_recovery_verified",
        "stop_release_authorized", "test_state",
    ):
        setattr(D541AnchorSelectionTests, f"test_fault_{_i:02d}_{_field}",
                _fault_false_test(_i, _field))

for _i in range(len(_CANDIDATES)):
    for _field in (
        "independent_operator_verified", "real_root_attested",
        "actual_candidate_selected",
    ):
        setattr(D541AnchorSelectionTests, f"test_candidate_{_i}_{_field}",
                _candidate_false_test(_i, _field))

for _field in _NO_CLAIM:
    setattr(D541AnchorSelectionTests, f"test_contract_no_{_field}",
            _contract_action_test(_field))

for _field in _MATRIX_FLAGS:
    setattr(D541AnchorSelectionTests, f"test_matrix_no_{_field}",
            _matrix_action_test(_field))


if __name__ == "__main__":
    main()
