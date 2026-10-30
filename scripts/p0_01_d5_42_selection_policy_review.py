"""D5-42: G6-02 hard-knockout decision rules, strictly synthetic.

No service discovery, actual anchor verification, key generation, file I/O,
financial operation, real approval, ranking or permission can occur here.
Even a complete synthetic pass is explicitly non-evidentiary.
"""
from __future__ import annotations

from scripts.p0_01_d5_41_anchor_selection_review import (
    _FALSE as _D541_FALSE,
    _CANDIDATES as _D541_CANDIDATES,
    _AXES as _D541_AXES,
    review_d541_anchor_candidates,
)

_CANDIDATES = tuple(row[0] for row in _D541_CANDIDATES)
_HARD = (
    "ADMIN_BOUNDARY", "WRITE_BOUNDARY", "CREDENTIAL_BOUNDARY",
    "ROLLBACK_RESISTANCE", "FRESHNESS_SOURCE", "REVOCATION_DURABILITY",
    "KEY_ROTATION_AUTHORITY", "SPLIT_BRAIN_DETECTION",
    "STOP_LATCH_CONTINUITY", "PRIVACY_NON_EXPOSURE",
    "FAILURE_RECOVERY", "DATA_RESIDENCY",
)
_SOFT = ("LIFECYCLE_COST", "OPERATIONAL_BURDEN")
_KNOCKOUTS = (
    ("COMMON_ROOT_OR_ADMIN", "SHARED_ADMIN_AUTHORITY"),
    ("REPLAY_OR_ROLLBACK_ACCEPTED", "ROLLBACK_RESISTANCE"),
    ("REVOCATION_LOSS_ACCEPTED", "REVOCATION_DURABILITY"),
    ("WITNESS_OUTAGE_REENABLES_TRADING", "STOP_LATCH_CONTINUITY"),
    ("FORK_ACCEPTED_AS_CURRENT", "SPLIT_BRAIN_DETECTION"),
    ("PRIVATE_RECORDS_EXPORTED", "PRIVACY_NON_EXPOSURE"),
    ("UNAUTHENTICATED_ISSUER_ACCEPTED", "KEY_ROTATION_AUTHORITY"),
    ("CRASH_RECOVERY_UNLATCHES_STOP", "FAILURE_RECOVERY"),
)
_STAGES = (
    "G2_PRIVATE_PROTECTION_REVIEW",
    "INDEPENDENT_ROOT_OWNER_PROVENANCE_REVIEW",
    "ALL_HARD_GATES_EXTERNAL_ATTESTATION_REVIEW",
    "KNOCKOUT_FAULT_RESULTS_REVIEW",
    "SECONDARY_COST_OPERATIONS_REVIEW",
    "SEPARATE_HUMAN_DESIGN_DECISION",
)
_CONTRACT_KEYS = frozenset((
    "origin", "schema_version", "scope", "target_criterion",
    "predecessor", "candidate_ids", "noncompensable_axes",
    "secondary_axes", "knockout_ids", "approval_stages",
    "hard_gate_rule", "knockout_rule", "secondary_rule",
    "synthetic_rule", "approval_rule", "unknown_rule",
    "privacy_dependencies", "upstream_gates", "chosen_architecture",
    "real_human_design_approved", "real_runtime_approved",
    "real_proof_collected", "real_issuer_verified",
    "actual_hardware_selected", "actual_remote_witness_connected",
    "actual_anchor_constructed", "real_key_operation_approved",
    "real_network_io_approved", "real_host_io_approved",
    "real_mt4_io_approved", "phase_1", "runtime_go_no_go",
    "verified_values",
))
_RECORD_KEYS = frozenset((
    "origin", "schema_version", "scope", "hard_checks",
    "secondary_checks", "knockout_cases", "approval_steps",
    "actual_chosen_candidate", "real_design_approval",
    "real_runtime_permission", "actual_evidence_collected",
    "real_fault_tests_executed", "account_identity_consistency",
    "current_positions", "current_pending_orders", "current_ea_state",
    "unresolved_gates", "safety_hold_latched",
))
_HARD_KEYS = frozenset((
    "candidate_id", "axis", "classification",
    "simulated_outcome", "real_independent_proof", "real_approval_granted",
))
_SOFT_KEYS = frozenset((
    "candidate_id", "axis", "simulated_outcome",
    "real_quotation", "real_human_review",
))
_KNOCKOUT_KEYS = frozenset((
    "candidate_id", "knockout_id", "related_axis",
    "simulated_outcome", "real_fault_executed",
    "real_disqualification_proven",
))
_APPROVAL_KEYS = frozenset((
    "stage", "review_state", "real_evidence_reference", "real_human_signoff",
))
_REAL_FLAGS = (
    "real_human_design_approved", "real_runtime_approved",
    "real_proof_collected", "real_issuer_verified",
    "actual_hardware_selected", "actual_remote_witness_connected",
    "actual_anchor_constructed", "real_key_operation_approved",
    "real_network_io_approved", "real_host_io_approved",
    "real_mt4_io_approved",
)
_RECORD_FALSE = (
    "real_design_approval", "real_runtime_permission",
    "actual_evidence_collected", "real_fault_tests_executed",
)
_PARENT_KEYS = ("d541_contract", "d541_matrix", "d541_predecessor")
_FALSE = (*_D541_FALSE,
          "g6_02_real_knockout_verified",
          "g6_02_real_hard_gates_verified",
          "g6_02_real_human_design_approved",
          "g6_02_actual_choice_approved",
          "g6_02_real_anchor_construction_allowed",
          "g6_02_real_runtime_approval",
          "g6_02_real_fault_tests_passed",
          "g6_02_cost_can_override_safety",
          "g6_02_synthetic_pass_as_proof",
          "g6_02_stop_release_authorized")


def _deny(status: str, upstream: str = "NOT_EVALUATED") -> dict[str, object]:
    result = {k: False for k in _FALSE}
    result.update({
        "status": status, "d541_status": upstream,
        "comparison_candidates": len(_CANDIDATES),
        "noncompensable_requirements": len(_CANDIDATES) * len(_HARD),
        "secondary_requirements": len(_CANDIDATES) * len(_SOFT),
        "knockout_scenarios": len(_CANDIDATES) * len(_KNOCKOUTS),
        "approval_stages_pending": len(_STAGES),
        "real_candidates_selected": 0,
        "real_independent_evidence_verified": 0,
        "real_fault_cases_executed": 0,
        "real_trust_anchors_implemented": 0,
        "real_evidence_items_collected": 0,
        "real_work_packages_executed": 0,
        "real_acceptance_criteria_completed": 0,
        "effective_approved_actions": [],
        "safety_hold_latched": True,
        "account_identity_consistency": "NOT_RECONCILED",
        "current_positions": "UNKNOWN",
        "current_pending_orders": "UNKNOWN",
        "current_ea_state": "UNKNOWN",
        "phase_1": "BLOCKED", "runtime_go_no_go": "NO_GO",
        "verified_values": None,
    })
    return result


def _contract_valid(c: object) -> bool:
    return (
        type(c) is dict and set(c) == _CONTRACT_KEYS
        and c.get("origin") == "OFFLINE_DESIGN_ONLY"
        and type(c.get("schema_version")) is int and c["schema_version"] == 1
        and c.get("scope") == "D542_G6_02_HARD_KNOCKOUT_SELECTION_RULES_ONLY"
        and c.get("target_criterion") == "G6-02"
        and c.get("predecessor") ==
            "D541_EVIDENCE_MATRIX_COMPLETE_NO_SELECTION_OR_REAL_PROOF"
        and c.get("candidate_ids") == list(_CANDIDATES)
        and c.get("noncompensable_axes") == list(_HARD)
        and c.get("secondary_axes") == list(_SOFT)
        and set(_HARD).isdisjoint(_SOFT)
        and set(_HARD) | set(_SOFT) == {r[0] for r in _D541_AXES}
        and c.get("knockout_ids") == [r[0] for r in _KNOCKOUTS]
        and c.get("approval_stages") == list(_STAGES)
        and c.get("hard_gate_rule") ==
            "ALL_TWELVE_REAL_INDEPENDENTLY_VERIFIED_OR_NOT_ELIGIBLE"
        and c.get("knockout_rule") ==
            "ANY_REAL_KNOCKOUT_DISQUALIFIES_NO_OVERRIDE"
        and c.get("secondary_rule") ==
            "ONLY_AFTER_ALL_HARD_GATES_AND_NO_KNOCKOUT"
        and c.get("synthetic_rule") ==
            "SYNTHETIC_PASS_IS_NEVER_REAL_EVIDENCE"
        and c.get("approval_rule") ==
            "SEPARATE_HUMAN_DESIGN_SELECTION_AND_SEPARATE_RUNTIME_APPROVAL"
        and c.get("unknown_rule") == "UNKNOWN_OR_MISSING_MEANS_NO_GO"
        and c.get("privacy_dependencies") == ["G2-06", "G2-07"]
        and c.get("upstream_gates") == ["G6-01", "G8"]
        and "chosen_architecture" in c and c["chosen_architecture"] is None
        and all(c.get(k) is False for k in _REAL_FLAGS)
        and c.get("phase_1") == "BLOCKED"
        and c.get("runtime_go_no_go") == "NO_GO"
        and "verified_values" in c and c["verified_values"] is None
    )


def _record_valid(r: object) -> bool:
    if not (
        type(r) is dict and set(r) == _RECORD_KEYS
        and r.get("origin") == "SYNTHETIC_ONLY"
        and type(r.get("schema_version")) is int and r["schema_version"] == 1
        and r.get("scope") == "D542_HYPOTHETICAL_SELECTION_CASES_NO_REAL_PROOF"
        and r.get("unresolved_gates") == [f"G{i}" for i in range(1, 10)]
        and r.get("safety_hold_latched") is True
        and r.get("account_identity_consistency") == "NOT_RECONCILED"
        and all(r.get(k) == "UNKNOWN" for k in (
            "current_positions", "current_pending_orders", "current_ea_state"))
        and "actual_chosen_candidate" in r and r["actual_chosen_candidate"] is None
        and all(type(r.get(k)) is bool for k in _RECORD_FALSE)
    ):
        return False
    hard = r.get("hard_checks")
    if type(hard) is not list or len(hard) != len(_CANDIDATES) * len(_HARD):
        return False
    for row, candidate, axis in zip(
        hard, (x for x in _CANDIDATES for _ in _HARD),
        _HARD * len(_CANDIDATES),
    ):
        if not (
            type(row) is dict and set(row) == _HARD_KEYS
            and row.get("candidate_id") == candidate
            and row.get("axis") == axis
            and row.get("classification") == "NON_COMPENSABLE"
            and row.get("simulated_outcome") in (
                "UNVERIFIED", "SIMULATED_PASS", "SIMULATED_FAIL")
            and "real_independent_proof" in row
            and row["real_independent_proof"] is None
            and type(row.get("real_approval_granted")) is bool
        ):
            return False
    soft = r.get("secondary_checks")
    if type(soft) is not list or len(soft) != len(_CANDIDATES) * len(_SOFT):
        return False
    for row, candidate, axis in zip(
        soft, (x for x in _CANDIDATES for _ in _SOFT),
        _SOFT * len(_CANDIDATES),
    ):
        if not (
            type(row) is dict and set(row) == _SOFT_KEYS
            and row.get("candidate_id") == candidate
            and row.get("axis") == axis
            and row.get("simulated_outcome") in (
                "UNVERIFIED", "SIMULATED_AFFORDABLE",
                "SIMULATED_EXPENSIVE")
            and "real_quotation" in row and row["real_quotation"] is None
            and type(row.get("real_human_review")) is bool
        ):
            return False
    knockouts = r.get("knockout_cases")
    if (type(knockouts) is not list
            or len(knockouts) != len(_CANDIDATES) * len(_KNOCKOUTS)):
        return False
    for row, candidate, (ident, axis) in zip(
        knockouts, (x for x in _CANDIDATES for _ in _KNOCKOUTS),
        _KNOCKOUTS * len(_CANDIDATES),
    ):
        if not (
            type(row) is dict and set(row) == _KNOCKOUT_KEYS
            and row.get("candidate_id") == candidate
            and row.get("knockout_id") == ident
            and row.get("related_axis") == axis
            and row.get("simulated_outcome") in (
                "NOT_TESTED", "SIMULATED_VIOLATION",
                "SIMULATED_NONVIOLATION")
            and type(row.get("real_fault_executed")) is bool
            and type(row.get("real_disqualification_proven")) is bool
        ):
            return False
    stages = r.get("approval_steps")
    if type(stages) is not list or len(stages) != len(_STAGES):
        return False
    return all(
        type(row) is dict and set(row) == _APPROVAL_KEYS
        and row.get("stage") == stage
        and row.get("review_state") == "PENDING"
        and "real_evidence_reference" in row
        and row["real_evidence_reference"] is None
        and type(row.get("real_human_signoff")) is bool
        for row, stage in zip(stages, _STAGES)
    )


def _parent_safe(v: object) -> bool:
    return (
        type(v) is dict
        and type(v.get("status")) is str
        and type(v.get("d540_status")) is str
        and all(type(v.get(k)) is int and v[k] == n for k, n in (
            ("candidate_comparison_count", 2),
            ("design_evidence_requirements", 28),
            ("design_fault_cases", 16),
            ("real_candidates_selected", 0),
            ("real_independent_evidence_verified", 0),
            ("real_trust_anchors_implemented", 0),
            ("real_evidence_items_collected", 0),
            ("real_work_packages_executed", 0),
            ("real_acceptance_criteria_completed", 0)))
        and type(v.get("effective_approved_actions")) is list
        and v["effective_approved_actions"] == []
        and v.get("safety_hold_latched") is True
        and v.get("phase_1") == "BLOCKED"
        and v.get("runtime_go_no_go") == "NO_GO"
        and "verified_values" in v and v["verified_values"] is None
        and v.get("account_identity_consistency") == "NOT_RECONCILED"
        and all(v.get(k) == "UNKNOWN" for k in (
            "current_positions", "current_pending_orders", "current_ea_state"))
        and all(v.get(k) is False for k in _D541_FALSE)
        and set(v) == set(_D541_FALSE) | {
            "status", "d540_status", "candidate_comparison_count",
            "design_evidence_requirements", "design_fault_cases",
            "real_candidates_selected", "real_independent_evidence_verified",
            "real_trust_anchors_implemented", "real_evidence_items_collected",
            "real_work_packages_executed", "real_acceptance_criteria_completed",
            "effective_approved_actions", "safety_hold_latched",
            "account_identity_consistency", "current_positions",
            "current_pending_orders", "current_ea_state",
            "phase_1", "runtime_go_no_go", "verified_values",
        }
    )


def review_d542_selection_rules(
    contract: object, scenario: object, predecessor: object,
) -> dict[str, object]:
    """Evaluate hypothetical failures first; NEVER make a real selection."""
    try:
        if not _contract_valid(contract):
            return _deny("D542_SELECTION_RULES_CONTRACT_REJECTED_FAIL_CLOSED")
        if not _record_valid(scenario):
            return _deny("D542_SCENARIO_SCHEMA_REJECTED_FAIL_CLOSED")
        if (
            any(scenario[k] for k in _RECORD_FALSE)
            or any(row["real_approval_granted"] for row in scenario["hard_checks"])
            or any(row["real_human_review"] for row in scenario["secondary_checks"])
            or any(row["real_fault_executed"] or row["real_disqualification_proven"]
                   for row in scenario["knockout_cases"])
            or any(row["real_human_signoff"] for row in scenario["approval_steps"])
        ):
            return _deny("D542_FALSE_REAL_APPROVAL_OR_PROOF_NO_GO")
        if type(predecessor) is not dict or set(predecessor) != set(_PARENT_KEYS):
            return _deny("D542_PREDECESSOR_BUNDLE_REJECTED_FAIL_CLOSED")
        child = review_d541_anchor_candidates(
            *(predecessor[k] for k in _PARENT_KEYS)
        )
        if not _parent_safe(child):
            return _deny("D542_PREDECESSOR_SAFETY_INVARIANT_FAIL_CLOSED")
        if child["status"] != "D541_EVIDENCE_MATRIX_COMPLETE_NO_SELECTION_OR_REAL_PROOF":
            return _deny("D542_PREDECESSOR_NOT_COHERENT_NO_GO", child["status"])
        upstream = child["status"]
        if any(row["simulated_outcome"] == "SIMULATED_VIOLATION"
               for row in scenario["knockout_cases"]):
            return _deny("D542_SYNTHETIC_HARD_KNOCKOUT_NO_SELECTION", upstream)
        if any(row["simulated_outcome"] == "SIMULATED_FAIL"
               for row in scenario["hard_checks"]):
            return _deny("D542_SYNTHETIC_HARD_GATE_FAILURE_NO_SELECTION", upstream)
        if any(row["simulated_outcome"] in (
            "SIMULATED_AFFORDABLE", "SIMULATED_EXPENSIVE")
               for row in scenario["secondary_checks"]):
            return _deny("D542_SECONDARY_TRADEOFF_CANNOT_OVERRIDE_UNKNOWN", upstream)
        if any(row["simulated_outcome"] != "UNVERIFIED"
               for row in scenario["hard_checks"]) or any(
               row["simulated_outcome"] != "NOT_TESTED"
               for row in scenario["knockout_cases"]):
            return _deny("D542_SYNTHETIC_PASS_NOT_INDEPENDENT_PROOF", upstream)
        return _deny("D542_HARD_KNOCKOUT_POLICY_DOCUMENTED_NO_SELECTION", upstream)
    except Exception:
        return _deny("D542_INPUT_EXCEPTION_FAIL_CLOSED")
