"""P0-01 D5-36: review acceptance *requirements*, never approve implementation.

This is pure, in-memory, deny-only logic. It does not collect G2 evidence,
use OS files/clocks, connect to MT4, inspect real Git history, implement
a trust anchor or grant any operational permissions.
"""
from __future__ import annotations

from scripts.p0_01_d5_35_handoff_review import (
    _FALSE as _D535_FALSE, review_d535_handoff,
)

# Criterion IDs, order, dependency edges, privacy boundary and test target
# labels are fixed here to reject forged plans and spuriously accepted gates.
_SPEC = (
    ("G2-01", "G2", "FUTURE_READ_ONLY", "PRIVATE_ONLY", [], [], "ACCOUNT_TERMINAL_SCOPE"),
    ("G2-02", "G2", "FUTURE_READ_ONLY", "PRIVATE_ONLY", ["G2-01"], [], "SESSION_AND_SERVER_IDENTITY"),
    ("G2-03", "G2", "FUTURE_VISUAL_REVIEW", "PRIVATE_ONLY", ["G2-01"], [], "EA_AND_AUTOTRADING_STATE"),
    ("G2-04", "G2", "FUTURE_READ_ONLY", "PRIVATE_ONLY", ["G2-01","G2-02"], [], "POSITIONS_PENDING_ORDERS"),
    ("G2-05", "G2", "FUTURE_READ_ONLY", "PRIVATE_ONLY", ["G2-01"], ["G7"], "OBSERVATION_PROVENANCE_TIME"),
    ("G2-06", "G2", "FUTURE_HOST_IO", "PRIVATE_ONLY", [], [], "PRIVATE_EVIDENCE_RETENTION"),
    ("G2-07", "G2", "FUTURE_HOST_IO", "PUBLIC_METADATA_ONLY", ["G2-06"], ["G8"], "PUBLICATION_BLOCKING_AND_SCAN"),
    ("G6-01", "G6", "FUTURE_DESIGN_REVIEW", "DESIGN_ONLY", [], [], "TRUST_BOUNDARY_AND_ISSUER_AUTHORITY"),
    ("G6-02", "G6", "FUTURE_EXTERNAL_ATTESTATION", "PRIVATE_ONLY", ["G6-01"], [], "INDEPENDENT_TRUST_ANCHOR"),
    ("G6-03", "G6", "FUTURE_EXTERNAL_ATTESTATION", "PRIVATE_ONLY", ["G6-01","G6-02"], ["G8"], "KEY_CUSTODY_ROTATION_REVOCATION"),
    ("G6-04", "G6", "FUTURE_HOST_IO", "PRIVATE_ONLY", ["G6-01"], [], "APPEND_ONLY_JOURNAL_TOMBSTONES"),
    ("G6-05", "G6", "FUTURE_HOST_IO", "PRIVATE_ONLY", ["G6-04"], [], "SINGLE_WRITER_FENCE"),
    ("G6-06", "G6", "FUTURE_HOST_IO", "PRIVATE_ONLY", ["G6-02","G6-04","G6-05"], [], "ATOMIC_COMMIT_AND_CRASH_RECOVERY"),
    ("G6-07", "G6", "FUTURE_HOST_IO", "PRIVATE_ONLY", ["G6-06"], ["G7"], "RESTART_MONOTONIC_CLOCK_CONTINUITY"),
    ("G6-08", "G6", "FUTURE_EXTERNAL_ATTESTATION", "PRIVATE_ONLY", ["G6-03","G6-06","G6-07"], ["G8"], "APPROVAL_REVOCATION_RECOVERY_ATTESTATION"),
)
_IDS = tuple(s[0] for s in _SPEC)
_CONTRACT_KEYS = frozenset((
    "origin", "schema_version", "scope", "gate_scope", "criteria",
    "real_g2_resolved", "real_g6_resolved", "mt4_and_host_approved",
    "phase_1", "runtime_go_no_go", "verified_values",
))
_CRITERION_KEYS = frozenset((
    "criterion_id", "gate", "verification_boundary", "privacy_class",
    "depends_on", "external_gate_dependencies", "success_condition",
    "requires_separate_user_approval",
))
_REGISTER_KEYS = frozenset((
    "origin", "schema_version", "scope", "criteria", "unresolved_gates",
    "account_identity_consistency", "current_positions",
    "current_pending_orders", "current_ea_state", "observed_at_utc",
    "broker_verified", "safety_hold_latched",
))
_ROW_KEYS = frozenset((
    "criterion_id", "implementation_state", "real_evidence_state",
    "human_approval_state", "acceptance_state",
))
_APPROVALS = (
    "visual_review", "mt4_launch", "account_login", "mt4_read_only",
    "host_io", "ea_ex4_execution", "order_execution", "stop_release",
    "live_trading", "public_export", "private_evidence_collection",
    "independent_trust_anchor_operation",
)
_ACTION_KEYS = frozenset(("origin", "schema_version", "scope",
                          "approvals", "simulation_only"))
_BUNDLE_FIELDS = (
    "d535_contract", "d534_contract", "d533_contract", "d532_contract",
    "d531_contract", "old_evidence", "gap_matrix", "d532_fixture",
    "d533_case", "d534_case", "d535_case",
)
_FALSE = (*_D535_FALSE, "g2_criteria_accepted", "g6_criteria_accepted",
          "g2_real_evidence_verified", "g6_real_anchor_verified",
          "manual_approval_verified", "actual_acceptance_authorized",
          "private_data_export_approved", "host_file_io_approved",
          "read_only_observation_approved", "future_phase_accepted")


def _deny(status: str, child_status: str = "NOT_EVALUATED") -> dict[str, object]:
    result = {k: False for k in _FALSE}
    result.update({
        "status": status,
        "d535_status": child_status,
        "g2_design_criteria_count": 7,
        "g6_design_criteria_count": 8,
        "real_acceptance_criteria_completed": 0,
        "effective_approved_actions": [],
        "safety_hold_latched": True,
        "account_identity_consistency": "NOT_RECONCILED",
        "current_positions": "UNKNOWN", "current_pending_orders": "UNKNOWN",
        "current_ea_state": "UNKNOWN",
        "phase_1": "BLOCKED", "runtime_go_no_go": "NO_GO",
        "verified_values": None,
    })
    return result


def _contract_valid(plan: object) -> bool:
    if (
        type(plan) is not dict or set(plan) != _CONTRACT_KEYS
        or plan.get("origin") != "OFFLINE_DESIGN_ONLY"
        or type(plan.get("schema_version")) is not int
        or plan["schema_version"] != 1
        or plan.get("scope") != "D536_G2_G6_ACCEPTANCE_READINESS_DESIGN_ONLY"
        or plan.get("gate_scope") != ["G2", "G6"]
        or plan.get("real_g2_resolved") is not False
        or plan.get("real_g6_resolved") is not False
        or plan.get("mt4_and_host_approved") is not False
        or plan.get("phase_1") != "BLOCKED"
        or plan.get("runtime_go_no_go") != "NO_GO"
        or "verified_values" not in plan or plan["verified_values"] is not None
    ):
        return False
    criteria = plan.get("criteria")
    if type(criteria) is not list or len(criteria) != len(_SPEC):
        return False
    for row, expected in zip(criteria, _SPEC):
        if type(row) is not dict or set(row) != _CRITERION_KEYS:
            return False
        if (
            row.get("criterion_id") != expected[0]
            or row.get("gate") != expected[1]
            or row.get("verification_boundary") != expected[2]
            or row.get("privacy_class") != expected[3]
            or row.get("depends_on") != expected[4]
            or row.get("external_gate_dependencies") != expected[5]
            or row.get("success_condition") != expected[6]
            or row.get("requires_separate_user_approval") is not True
        ):
            return False
    return True


def _register_structure_valid(reg: object) -> bool:
    if (
        type(reg) is not dict or set(reg) != _REGISTER_KEYS
        or reg.get("origin") != "SYNTHETIC_ONLY"
        or type(reg.get("schema_version")) is not int or reg["schema_version"] != 1
        or reg.get("scope") != "READINESS_REGISTER_NOT_REAL_EVIDENCE"
        or reg.get("unresolved_gates") != [f"G{i}" for i in range(1, 10)]
        or reg.get("account_identity_consistency") != "NOT_RECONCILED"
        or any(reg.get(k) != "UNKNOWN" for k in (
            "current_positions", "current_pending_orders", "current_ea_state"))
        or "observed_at_utc" not in reg or reg["observed_at_utc"] is not None
        or reg.get("broker_verified") is not False
        or reg.get("safety_hold_latched") is not True
    ):
        return False
    rows = reg.get("criteria")
    return (
        type(rows) is list and len(rows) == len(_IDS)
        and all(type(r) is dict and set(r) == _ROW_KEYS
                and r.get("criterion_id") == ident
                and all(type(r.get(k)) is str for k in (
                    "implementation_state", "real_evidence_state",
                    "human_approval_state", "acceptance_state"))
                for r, ident in zip(rows, _IDS))
    )


def _register_has_false_claims(reg: dict[str, object]) -> bool:
    return any(
        r["implementation_state"] != "NOT_IMPLEMENTED"
        or r["real_evidence_state"] != "NOT_COLLECTED"
        or r["human_approval_state"] != "NOT_GRANTED"
        or r["acceptance_state"] != "BLOCKED"
        for r in reg["criteria"]
    )


def _actions_valid(actions: object) -> bool:
    return (
        type(actions) is dict and set(actions) == _ACTION_KEYS
        and actions.get("origin") == "SYNTHETIC_ONLY"
        and type(actions.get("schema_version")) is int
        and actions["schema_version"] == 1
        and actions.get("scope") == "D536_NO_ACTION_REQUEST"
        and actions.get("simulation_only") is True
        and type(actions.get("approvals")) is dict
        and set(actions["approvals"]) == set(_APPROVALS)
        and all(type(v) is bool for v in actions["approvals"].values())
    )


def _child_safe(child: object) -> bool:
    return (
        type(child) is dict
        and type(child.get("status")) is str
        and type(child.get("d534_status")) is str
        and type(child.get("effective_approved_actions")) is list
        and child["effective_approved_actions"] == []
        and child.get("safety_hold_latched") is True
        and child.get("phase_1") == "BLOCKED"
        and child.get("runtime_go_no_go") == "NO_GO"
        and "verified_values" in child and child["verified_values"] is None
        and child.get("account_identity_consistency") == "NOT_RECONCILED"
        and all(child.get(k) == "UNKNOWN" for k in (
            "current_positions", "current_pending_orders", "current_ea_state"))
        and all(child.get(k) is False for k in _D535_FALSE)
        and set(child) == set(_D535_FALSE) | {
            "status", "d534_status", "effective_approved_actions",
            "safety_hold_latched", "account_identity_consistency",
            "current_positions", "current_pending_orders", "current_ea_state",
            "phase_1", "runtime_go_no_go", "verified_values",
        }
    )


def review_d536_readiness(
    contract: object, readiness: object, action_claims: object,
    predecessor_bundle: object,
) -> dict[str, object]:
    """Validate D5-36 admission-to-design, never any real G2/G6 acceptance."""
    try:
        if not _contract_valid(contract):
            return _deny("D536_CONTRACT_REJECTED_FAIL_CLOSED")
        if not _register_structure_valid(readiness):
            return _deny("D536_READINESS_REGISTER_REJECTED_FAIL_CLOSED")
        if _register_has_false_claims(readiness):
            return _deny("D536_FALSE_REAL_READINESS_CLAIM_NO_GO")
        if not _actions_valid(action_claims):
            return _deny("D536_ACTION_SCHEMA_REJECTED_FAIL_CLOSED")
        if any(action_claims["approvals"].values()):
            return _deny("D536_UNAUTHORIZED_ACTION_CLAIM_NO_GO")
        if (type(predecessor_bundle) is not dict
                or set(predecessor_bundle) != set(_BUNDLE_FIELDS)):
            return _deny("D536_PREDECESSOR_BUNDLE_REJECTED_FAIL_CLOSED")
        child = review_d535_handoff(
            *(predecessor_bundle[key] for key in _BUNDLE_FIELDS)
        )
        if not _child_safe(child):
            return _deny("D536_PREDECESSOR_SAFETY_INVARIANT_FAIL_CLOSED")
        prior = child["status"]
        if prior != "D535_SYNTHETIC_LIFECYCLE_COHERENT_NEVER_AUTHORIZED":
            return _deny("D536_PREDECESSOR_NOT_COHERENT_NO_GO", prior)
        return _deny("D536_DESIGN_CRITERIA_DOCUMENTED_REAL_ACCEPTANCE_BLOCKED",
                     prior)
    except Exception:
        return _deny("D536_INPUT_EXCEPTION_FAIL_CLOSED")
