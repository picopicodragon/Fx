"""D5-40 G6-01 independent authority/trust-domain offline design tests."""
from __future__ import annotations

import copy
import json
from pathlib import Path
from unittest import TestCase, main
from unittest.mock import patch

from scripts.p0_01_d5_40_trust_boundary_review import (
    _FALSE, _CANDIDATES, _THREATS, _ROLES, _TESTS, _PARENT_KEYS,
    _ACTION_FLAGS, review_d540_trust_boundary,
)
from scripts.p0_01_d5_36_readiness_gate import _BUNDLE_FIELDS
from scripts.p0_01_d5_39_egress_gate import review_d539_egress

ROOT = Path(__file__).resolve().parents[1]
_MISSING = object()


def read(name):
    with (ROOT / "specs" / name).open(encoding="utf-8") as f:
        return json.load(f)


def contract(): return read("p0_01_d5_40_trust_boundary_contract.json")
def matrix(): return read("p0_01_d5_40_candidate_threat_matrix.json")


def predecessor():
    p = {
        "d539_contract": read("p0_01_d5_39_egress_contract.json"),
        "d539_manifest": read("p0_01_d5_39_synthetic_manifest.json"),
    }
    p["d539_public_json"] = read("p0_01_d5_32_synthetic_fixture.json")["public_json"]
    prev = {
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
    prev["d536_predecessors"] = dict(
        zip(_BUNDLE_FIELDS, (read(x) for x in sources))
    )
    p["d539_predecessors"] = prev
    return p


class D540TrustBoundaryTests(TestCase):
    def check(self, expected, c=_MISSING, m=_MISSING, p=_MISSING):
        result = review_d540_trust_boundary(
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
        self.assertEqual(result["design_candidate_count"], 4)
        self.assertEqual(result["design_threat_count"], 12)
        for field in (
            "real_trust_anchors_implemented",
            "real_evidence_items_collected", "real_work_packages_executed",
            "real_acceptance_criteria_completed",
        ):
            self.assertEqual(result[field], 0)
        for field in ("current_positions", "current_pending_orders",
                      "current_ea_state"):
            self.assertEqual(result[field], "UNKNOWN")
        for field in _FALSE:
            self.assertIs(result[field], False, field)
        self.assertEqual(set(result), set(_FALSE) | {
            "status", "d539_status", "design_candidate_count",
            "design_threat_count", "real_trust_anchors_implemented",
            "real_evidence_items_collected", "real_work_packages_executed",
            "real_acceptance_criteria_completed",
            "effective_approved_actions", "safety_hold_latched",
            "account_identity_consistency", "current_positions",
            "current_pending_orders", "current_ea_state",
            "phase_1", "runtime_go_no_go", "verified_values",
        })
        return result

    def test_baseline_is_never_an_independent_anchor(self):
        result = self.check(
            "D540_TRUST_BOUNDARY_CANDIDATES_DOCUMENTED_NO_REAL_ANCHOR"
        )
        self.assertEqual(
            result["d539_status"],
            "D539_SYNTHETIC_EGRESS_MANIFEST_COHERENT_NO_REAL_EGRESS",
        )

    def test_four_candidate_classifications_preserved(self):
        self.assertEqual(len(_CANDIDATES), 4)
        self.assertEqual(
            [c["candidate_id"] for c in matrix()["candidates"]],
            [r[0] for r in _CANDIDATES],
        )
        self.check("D540_TRUST_BOUNDARY_CANDIDATES_DOCUMENTED_NO_REAL_ANCHOR")

    def test_same_process_mirror_never_independent(self):
        self.assertEqual(_CANDIDATES[0][4], "NOT_INDEPENDENT")
        self.check("D540_TRUST_BOUNDARY_CANDIDATES_DOCUMENTED_NO_REAL_ANCHOR")

    def test_same_host_second_user_not_verified_independent(self):
        self.assertEqual(_CANDIDATES[1][4],
                         "INSUFFICIENT_EXTERNAL_INDEPENDENCE")
        self.check("D540_TRUST_BOUNDARY_CANDIDATES_DOCUMENTED_NO_REAL_ANCHOR")

    def test_hardware_candidate_requires_external_proof(self):
        self.assertEqual(_CANDIDATES[2][4], "CONDITIONAL_DESIGN_ONLY")
        self.check("D540_TRUST_BOUNDARY_CANDIDATES_DOCUMENTED_NO_REAL_ANCHOR")

    def test_remote_witness_requires_independent_admin_proof(self):
        self.assertEqual(_CANDIDATES[3][4], "CONDITIONAL_DESIGN_ONLY")
        self.check("D540_TRUST_BOUNDARY_CANDIDATES_DOCUMENTED_NO_REAL_ANCHOR")

    def test_all_roles_are_distinct_authority_functions(self):
        self.assertEqual(contract()["authority_roles"], list(_ROLES))
        self.assertEqual(len(set(_ROLES)), 5)
        self.check("D540_TRUST_BOUNDARY_CANDIDATES_DOCUMENTED_NO_REAL_ANCHOR")

    def test_ten_independence_acceptance_checks_planned(self):
        self.assertEqual(contract()["mandatory_independence_tests"],
                         list(_TESTS))
        self.assertEqual(len(_TESTS), 10)
        self.check("D540_TRUST_BOUNDARY_CANDIDATES_DOCUMENTED_NO_REAL_ANCHOR")

    def test_twelve_threats_cover_shared_authority_and_replay(self):
        self.assertEqual(len(_THREATS), 12)
        self.assertIn("JOURNAL_ANCHOR_COORDINATED_FORGERY",
                      [x[0] for x in _THREATS])
        self.assertIn("SPLIT_BRAIN_WITNESS", [x[0] for x in _THREATS])
        self.check("D540_TRUST_BOUNDARY_CANDIDATES_DOCUMENTED_NO_REAL_ANCHOR")

    def test_all_candidates_have_null_real_addresses_and_operators(self):
        for row in matrix()["candidates"]:
            self.assertIsNone(row["real_anchor_address"])
            self.assertIsNone(row["real_operator_identity"])
        self.check("D540_TRUST_BOUNDARY_CANDIDATES_DOCUMENTED_NO_REAL_ANCHOR")

    def test_no_architecture_chosen(self):
        self.assertIsNone(contract()["chosen_architecture"])
        self.check("D540_TRUST_BOUNDARY_CANDIDATES_DOCUMENTED_NO_REAL_ANCHOR")

    def test_g2_06_g2_07_privacy_boundary_preserved(self):
        self.assertEqual(contract()["privacy_dependencies"], ["G2-06", "G2-07"])
        self.check("D540_TRUST_BOUNDARY_CANDIDATES_DOCUMENTED_NO_REAL_ANCHOR")

    def test_g6_02_next_phase_not_marked_accepted(self):
        self.assertEqual(contract()["next_criterion"], "G6-02")
        self.check("D540_TRUST_BOUNDARY_CANDIDATES_DOCUMENTED_NO_REAL_ANCHOR")

    def test_candidate_reorder_denied(self):
        m = matrix()
        m["candidates"].reverse()
        self.check("D540_CANDIDATE_THREAT_SCHEMA_REJECTED_FAIL_CLOSED", m=m)

    def test_candidate_missing_denied(self):
        m = matrix()
        m["candidates"].pop()
        self.check("D540_CANDIDATE_THREAT_SCHEMA_REJECTED_FAIL_CLOSED", m=m)

    def test_candidate_duplicate_denied(self):
        m = matrix()
        m["candidates"][1] = copy.deepcopy(m["candidates"][0])
        self.check("D540_CANDIDATE_THREAT_SCHEMA_REJECTED_FAIL_CLOSED", m=m)

    def test_candidate_fake_real_operator_denied(self):
        m = matrix()
        m["candidates"][0]["real_operator_identity"] = "SYNTHETIC"
        self.check("D540_CANDIDATE_THREAT_SCHEMA_REJECTED_FAIL_CLOSED", m=m)

    def test_candidate_fake_real_anchor_address_denied(self):
        m = matrix()
        m["candidates"][0]["real_anchor_address"] = "SYNTHETIC_HOST"
        self.check("D540_CANDIDATE_THREAT_SCHEMA_REJECTED_FAIL_CLOSED", m=m)

    def test_candidate_false_independent_rating_denied(self):
        m = matrix()
        m["candidates"][0]["assessment"] = "INDEPENDENT_VERIFIED"
        self.check("D540_CANDIDATE_THREAT_SCHEMA_REJECTED_FAIL_CLOSED", m=m)

    def test_threat_reorder_denied(self):
        m = matrix()
        m["threats"].reverse()
        self.check("D540_CANDIDATE_THREAT_SCHEMA_REJECTED_FAIL_CLOSED", m=m)

    def test_threat_missing_denied(self):
        m = matrix()
        m["threats"].pop()
        self.check("D540_CANDIDATE_THREAT_SCHEMA_REJECTED_FAIL_CLOSED", m=m)

    def test_threat_duplicate_denied(self):
        m = matrix()
        m["threats"][1] = copy.deepcopy(m["threats"][0])
        self.check("D540_CANDIDATE_THREAT_SCHEMA_REJECTED_FAIL_CLOSED", m=m)

    def test_threat_change_denial_action_denied(self):
        m = matrix()
        m["threats"][0]["denial"] = "RETRY_AND_GO"
        self.check("D540_CANDIDATE_THREAT_SCHEMA_REJECTED_FAIL_CLOSED", m=m)

    def test_threat_unknown_attack_denied(self):
        m = matrix()
        m["threats"][0]["attack"] = "FAKE"
        self.check("D540_CANDIDATE_THREAT_SCHEMA_REJECTED_FAIL_CLOSED", m=m)

    def test_matrix_real_time_denied(self):
        m = matrix()
        m["observed_at_utc"] = "2026-10-30T00:00:00Z"
        self.check("D540_CANDIDATE_THREAT_SCHEMA_REJECTED_FAIL_CLOSED", m=m)

    def test_matrix_real_account_denied(self):
        m = matrix()
        m["account_identity_consistency"] = "RECONCILED"
        self.check("D540_CANDIDATE_THREAT_SCHEMA_REJECTED_FAIL_CLOSED", m=m)

    def test_matrix_positions_claim_denied(self):
        m = matrix()
        m["current_positions"] = "EMPTY"
        self.check("D540_CANDIDATE_THREAT_SCHEMA_REJECTED_FAIL_CLOSED", m=m)

    def test_matrix_extra_secret_denied(self):
        m = matrix()
        m["private_key"] = "SYNTHETIC_MARKER"
        self.check("D540_CANDIDATE_THREAT_SCHEMA_REJECTED_FAIL_CLOSED", m=m)

    def test_matrix_unresolved_gates_cannot_change(self):
        m = matrix()
        m["unresolved_gates"] = ["G6"]
        self.check("D540_CANDIDATE_THREAT_SCHEMA_REJECTED_FAIL_CLOSED", m=m)

    def test_matrix_false_broker_verified_denied(self):
        m = matrix()
        m["broker_verified"] = True
        self.check("D540_UNAUTHORIZED_REAL_OPERATION_OR_ANCHOR_NO_GO", m=m)

    def test_matrix_false_anchor_verified_denied(self):
        m = matrix()
        m["external_anchor_verified"] = True
        self.check("D540_UNAUTHORIZED_REAL_OPERATION_OR_ANCHOR_NO_GO", m=m)

    def test_contract_chosen_candidate_denied(self):
        c = contract()
        c["chosen_architecture"] = "REMOTE_SEPARATE_WITNESS_CANDIDATE"
        self.check("D540_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_contract_unexpected_next_criterion_denied(self):
        c = contract()
        c["next_criterion"] = "G6-08"
        self.check("D540_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_contract_privacy_dependency_erased_denied(self):
        c = contract()
        c["privacy_dependencies"].pop()
        self.check("D540_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_contract_roles_reorder_denied(self):
        c = contract()
        c["authority_roles"].reverse()
        self.check("D540_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_contract_tests_removed_denied(self):
        c = contract()
        c["mandatory_independence_tests"].pop()
        self.check("D540_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_contract_issuer_id_bad_denied(self):
        c = contract()
        c["issuer_id"] = "REAL"
        self.check("D540_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_contract_runtime_go_denied(self):
        c = contract()
        c["runtime_go_no_go"] = "GO"
        self.check("D540_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_contract_verified_values_denied(self):
        c = contract()
        c["verified_values"] = {}
        self.check("D540_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_contract_bool_schema_denied(self):
        c = contract()
        c["schema_version"] = True
        self.check("D540_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_invalid_contract_types_denied(self):
        for x in (None, True, [], {}, "GO"):
            with self.subTest(v=repr(x)):
                self.check("D540_CONTRACT_REJECTED_FAIL_CLOSED", c=x)

    def test_invalid_matrix_types_denied(self):
        for x in (None, True, [], {}, "GO"):
            with self.subTest(v=repr(x)):
                self.check("D540_CANDIDATE_THREAT_SCHEMA_REJECTED_FAIL_CLOSED", m=x)

    def test_missing_predecessor_rejected(self):
        self.check("D540_PREDECESSOR_BUNDLE_REJECTED_FAIL_CLOSED", p={})

    def test_extra_real_credentials_in_predecessor_rejected(self):
        p = predecessor()
        p["real_credentials"] = "SYNTHETIC_MARKER"
        self.check("D540_PREDECESSOR_BUNDLE_REJECTED_FAIL_CLOSED", p=p)

    def test_predecessor_g2_false_secret_scan_denied(self):
        p = predecessor()
        p["d539_contract"]["real_git_hook_installed"] = True
        self.check("D540_PREDECESSOR_NOT_COHERENT_NO_GO", p=p)

    def test_predecessor_private_egress_denied(self):
        p = predecessor()
        p["d539_manifest"]["items"][0]["private_data_attached"] = True
        self.check("D540_PREDECESSOR_NOT_COHERENT_NO_GO", p=p)

    def test_predecessor_g6_false_stop_release_denied(self):
        p = predecessor()
        p["d539_predecessors"]["d536_predecessors"]["d535_case"][
            "stop_release_claim"] = True
        self.check("D540_PREDECESSOR_NOT_COHERENT_NO_GO", p=p)

    def test_forged_child_go_denied(self):
        with patch("scripts.p0_01_d5_40_trust_boundary_review.review_d539_egress",
                   return_value={"status":
                       "D539_SYNTHETIC_EGRESS_MANIFEST_COHERENT_NO_REAL_EGRESS",
                       "runtime_go_no_go": "GO"}):
            self.check("D540_PREDECESSOR_SAFETY_INVARIANT_FAIL_CLOSED")

    def test_forged_child_egress_scanned_denied(self):
        p = predecessor()
        child = review_d539_egress(*(p[k] for k in _PARENT_KEYS))
        child["real_egress_surfaces_scanned"] = 1
        with patch("scripts.p0_01_d5_40_trust_boundary_review.review_d539_egress",
                   return_value=child):
            self.check("D540_PREDECESSOR_SAFETY_INVARIANT_FAIL_CLOSED")

    def test_forged_child_broker_verified_denied(self):
        p = predecessor()
        child = review_d539_egress(*(p[k] for k in _PARENT_KEYS))
        child["broker_verified"] = True
        with patch("scripts.p0_01_d5_40_trust_boundary_review.review_d539_egress",
                   return_value=child):
            self.check("D540_PREDECESSOR_SAFETY_INVARIANT_FAIL_CLOSED")

    def test_forged_child_status_denied(self):
        p = predecessor()
        child = review_d539_egress(*(p[k] for k in _PARENT_KEYS))
        child["status"] = "REAL_GO"
        with patch("scripts.p0_01_d5_40_trust_boundary_review.review_d539_egress",
                   return_value=child):
            self.check("D540_PREDECESSOR_NOT_COHERENT_NO_GO")

    def test_function_does_not_read_host_files(self):
        args = (contract(), matrix(), predecessor())
        with patch("builtins.open", side_effect=AssertionError("NO FILE I/O")):
            r = review_d540_trust_boundary(*args)
        self.assertEqual(r["runtime_go_no_go"], "NO_GO")

    def test_function_does_not_modify_inputs(self):
        args = (contract(), matrix(), predecessor())
        original = copy.deepcopy(args)
        review_d540_trust_boundary(*args)
        self.assertEqual(args, original)

    def test_no_untrusted_identifiers_echoed(self):
        m = matrix()
        m["private_key"] = "SYNTHETIC_MARKER_DO_NOT_ECHO"
        result = self.check("D540_CANDIDATE_THREAT_SCHEMA_REJECTED_FAIL_CLOSED", m=m)
        self.assertNotIn("SYNTHETIC_MARKER_DO_NOT_ECHO", repr(result))

    def test_status_zero_real_anchor_and_approvals(self):
        s = read("p0_01_d5_40_status.json")
        self.assertEqual(s["unresolved_gates"], [f"G{i}" for i in range(1, 10)])
        self.assertEqual(s["phase_1"], "BLOCKED")
        self.assertEqual(s["runtime_go_no_go"], "NO_GO")
        self.assertIsNone(s["verified_values"])
        self.assertEqual(s["real_trust_anchors_implemented"], 0)
        self.assertEqual(s["real_acceptance_criteria_completed"], 0)
        for k in ("g2_real_world_resolved", "g6_real_world_resolved",
                  "broker_verified", "host_io_approved",
                  "terminal_execution_approved", "forward_trading_enabled"):
            self.assertIs(s[k], False)

    def test_repeated_calls_do_not_learn_authority(self):
        self.check("D540_TRUST_BOUNDARY_CANDIDATES_DOCUMENTED_NO_REAL_ANCHOR")
        m = matrix()
        m["external_anchor_verified"] = True
        self.check("D540_UNAUTHORIZED_REAL_OPERATION_OR_ANCHOR_NO_GO", m=m)
        self.check("D540_TRUST_BOUNDARY_CANDIDATES_DOCUMENTED_NO_REAL_ANCHOR")


def _candidate_flag_test(i, k):
    def test(self):
        m = matrix()
        m["candidates"][i][k] = True
        self.check("D540_FALSE_REAL_CANDIDATE_PROOF_NO_GO", m=m)
    return test


def _threat_flag_test(i, k, value):
    def test(self):
        m = matrix()
        m["threats"][i][k] = value
        self.check("D540_FALSE_THREAT_MITIGATION_OR_RELEASE_NO_GO", m=m)
    return test


def _matrix_action_test(k):
    def test(self):
        m = matrix()
        m[k] = True
        self.check("D540_UNAUTHORIZED_REAL_OPERATION_OR_ANCHOR_NO_GO", m=m)
    return test


def _contract_action_test(k):
    def test(self):
        c = contract()
        c[k] = True
        self.check("D540_CONTRACT_REJECTED_FAIL_CLOSED", c=c)
    return test


for _i in range(len(_CANDIDATES)):
    for _field in ("actual_trust_boundary_proven", "real_crypto_attested",
                   "real_rollback_prevention_attested", "human_selection_approved"):
        setattr(D540TrustBoundaryTests, f"test_candidate_{_i}_{_field}",
                _candidate_flag_test(_i, _field))

for _i in range(len(_THREATS)):
    for _field, _value in (
        ("real_fault_injection_performed", True),
        ("independent_detection_verified", True),
        ("stop_release_requested", True),
        ("actual_leakage_justified", True),
        ("mitigation_state", "VERIFIED"),
    ):
        setattr(D540TrustBoundaryTests, f"test_threat_{_i}_{_field}",
                _threat_flag_test(_i, _field, _value))

for _field in _ACTION_FLAGS:
    setattr(D540TrustBoundaryTests, "test_no_real_" + _field,
            _matrix_action_test(_field))

for _field in (
    "external_provider_selected", "independent_anchor_implemented",
    "real_key_generated", "real_signature_verified",
    "real_issuer_authenticated", "actual_human_approved",
    "host_io_approved", "mt4_access_approved",
):
    setattr(D540TrustBoundaryTests, "test_contract_no_" + _field,
            _contract_action_test(_field))


if __name__ == "__main__":
    main()
