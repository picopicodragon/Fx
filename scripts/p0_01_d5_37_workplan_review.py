"""P0-01 D5-37: inspect G2/G6 DESIGN workplan and blocked execution.

Pure in-memory requirements audit. A priority sequence is NOT permission to
collect evidence, connect MT4, write a file, enable an EA, or trade.
The original decisions, broker account and trust anchor are never inspected.
"""
from __future__ import annotations

from scripts.p0_01_d5_36_readiness_gate import (
    _FALSE as _D536_FALSE,
    _SPEC, review_d536_readiness,
)

_ORDER = (
    "G2-06", "G2-07", "G6-01", "G6-02", "G6-04", "G6-05",
    "G2-01", "G2-02", "G2-03", "G2-04", "G2-05", "G6-03",
    "G6-06", "G6-07", "G6-08",
)
_DELIVERABLES = (
    ("DESIGN_PRIVATE_VAULT_AND_RETENTION",
     "VAULT_ACCESS_CONTROL_RETENTION_DELETION_REPORT"),
    ("DESIGN_SAFE_EXPORT_AND_GIT_GUARD",
     "GIT_EGRESS_ENFORCEMENT_AND_LEAKAGE_NEGATIVE_TEST"),
    ("DESIGN_EXTERNAL_TRUST_BOUNDARY",
     "THREAT_MODEL_AND_INDEPENDENT_AUTHORITY_REVIEW"),
    ("COMPARE_INDEPENDENT_ANCHOR_CANDIDATES",
     "OUT_OF_BAND_ANCHOR_MONOTONICITY_AND_OWNERSHIP_PROOF"),
    ("DESIGN_APPEND_ONLY_REVOCATION_RECORD",
     "DURABLE_JOURNAL_AND_TOMBSTONE_CRASH_EVIDENCE"),
    ("DESIGN_SINGLE_WRITER_FENCE",
     "FENCE_TOKEN_RACE_AND_RECOVERY_TEST_RESULTS"),
    ("PREPARE_ACCOUNT_SCOPE_REVIEW",
     "AUTHORITATIVE_ACCOUNT_AND_TERMINAL_IDENTITY"),
    ("PREPARE_SESSION_SERVER_REVIEW",
     "SAME_SESSION_SERVER_IDENTITY_EVIDENCE"),
    ("PREPARE_NON_EXECUTING_EA_VISUAL_CHECK",
     "TIME_SCOPED_EA_AUTOTRADING_VISUAL_EVIDENCE"),
    ("PREPARE_READ_ONLY_ORDER_RECONCILIATION",
     "CURRENT_POSITIONS_PENDING_ORDERS_AND_ACCOUNT_SCOPE"),
    ("DEFINE_TIMED_PROVENANCE_CAPTURE",
     "TRUSTED_CLOCK_AND_EVIDENCE_PROVENANCE"),
    ("DESIGN_KEY_REVOCATION_HANDOFF",
     "INDEPENDENT_KEY_ISSUER_AND_REVOCATION_ATTESTATION"),
    ("DESIGN_ATOMIC_CROSS_BOUNDARY_RECOVERY",
     "INTERRUPTED_WRITE_DURABLE_REPLAY_TEST_RESULTS"),
    ("DESIGN_RESTART_MONOTONIC_CLOCK_REVIEW",
     "RESTART_AND_UTC_MONOTONIC_TIME_ATTESTATION"),
    ("DESIGN_STOP_APPROVAL_RECOVERY_AUTHORITY",
     "HUMAN_APPROVAL_REVOCATION_AND_STOP_LATCH_PROOF"),
)
_PLAN_KEYS = frozenset((
    "origin", "schema_version", "scope", "source_spec", "selection_rule",
    "work_packages", "unresolved_gates", "allow_real_io",
    "allow_mt4_observation", "allow_ea_execution", "allow_broker_access",
    "allow_stop_release", "allow_real_trading", "human_approvals_recorded",
    "phase_1", "runtime_go_no_go", "verified_values",
))
_PACKAGE_KEYS = frozenset((
    "task_id", "criterion_id", "planning_rank", "gate",
    "design_deliverable", "future_acceptance_evidence",
    "future_verification_boundary", "privacy_class",
    "depends_on", "external_gate_dependencies",
    "separate_human_approval_required", "preparation_state",
    "implementation_allowed", "real_evidence_collected",
    "review_approved", "acceptance_allowed", "execution_allowed",
))
_FIXTURE_KEYS = frozenset((
    "origin", "schema_version", "scope", "work_packages",
    "external_g7_verified", "external_g8_verified",
    "account_identity_consistency", "current_positions",
    "current_pending_orders", "current_ea_state",
    "actual_start_requested", "actual_evidence_collection_requested",
    "stop_release_requested", "mt4_operation_requested",
    "private_export_requested", "simulation_only",
))
_ROW_KEYS = frozenset((
    "criterion_id", "implementation_state", "evidence_state",
    "approval_state", "acceptance_state",
))
_FALSE = (*_D536_FALSE, "g2_real_work_started",
          "g6_real_work_started", "g2_confidential_store_real",
          "g2_git_egress_gate_real", "g2_real_account_reconciled",
          "g6_independent_anchor_real", "g6_real_storage_recovered",
          "g6_human_release_verified", "future_implementation_authorized",
          "future_evidence_collection_authorized")


def _deny(status: str, upstream: str = "NOT_EVALUATED") -> dict[str, object]:
    out = {k: False for k in _FALSE}
    out.update({
        "status": status, "d536_status": upstream,
        "work_packages_planned": 15,
        "work_packages_executed": 0,
        "real_acceptance_criteria_completed": 0,
        "effective_approved_actions": [],
        "safety_hold_latched": True,
        "account_identity_consistency": "NOT_RECONCILED",
        "current_positions": "UNKNOWN",
        "current_pending_orders": "UNKNOWN",
        "current_ea_state": "UNKNOWN",
        "phase_1": "BLOCKED",
        "runtime_go_no_go": "NO_GO",
        "verified_values": None,
    })
    return out


def _valid_plan(plan: object) -> bool:
    if (
        type(plan) is not dict or set(plan) != _PLAN_KEYS
        or plan.get("origin") != "OFFLINE_DESIGN_ONLY"
        or type(plan.get("schema_version")) is not int
        or plan["schema_version"] != 1
        or plan.get("scope") != "D537_G2_G6_PLANNING_ONLY"
        or plan.get("source_spec") !=
            "D536_G2_G6_ACCEPTANCE_READINESS_DESIGN_ONLY"
        or plan.get("selection_rule") !=
            "PROTECTION_AND_TRUST_DESIGN_BEFORE_OPERATIONAL_EVIDENCE"
        or plan.get("unresolved_gates") != [f"G{i}" for i in range(1, 10)]
        or any(plan.get(k) is not False for k in (
            "allow_real_io", "allow_mt4_observation", "allow_ea_execution",
            "allow_broker_access", "allow_stop_release",
            "allow_real_trading", "human_approvals_recorded"))
        or plan.get("phase_1") != "BLOCKED"
        or plan.get("runtime_go_no_go") != "NO_GO"
        or "verified_values" not in plan or plan["verified_values"] is not None
    ):
        return False
    packages = plan.get("work_packages")
    if type(packages) is not list or len(packages) != len(_ORDER):
        return False
    spec = {r[0]: r for r in _SPEC}
    completed_design_ids = set()
    for i, (row, ident, deliverable) in enumerate(
            zip(packages, _ORDER, _DELIVERABLES), 1):
        expected = spec[ident]
        if (
            type(row) is not dict or set(row) != _PACKAGE_KEYS
            or row.get("task_id") != f"D537-WP-{i:02d}"
            or row.get("criterion_id") != ident
            or type(row.get("planning_rank")) is not int
            or row["planning_rank"] != i
            or row.get("gate") != expected[1]
            or row.get("design_deliverable") != deliverable[0]
            or row.get("future_acceptance_evidence") != deliverable[1]
            or row.get("future_verification_boundary") != expected[2]
            or row.get("privacy_class") != expected[3]
            or row.get("depends_on") != expected[4]
            or row.get("external_gate_dependencies") != expected[5]
            or row.get("separate_human_approval_required") is not True
            or row.get("preparation_state") != "DESIGN_NOT_STARTED"
            or any(row.get(k) is not False for k in (
                "implementation_allowed", "real_evidence_collected",
                "review_approved", "acceptance_allowed", "execution_allowed"))
            or not set(expected[4]).issubset(completed_design_ids)
        ):
            return False
        completed_design_ids.add(ident)
    return True


def _tracking_valid(tracking: object) -> bool:
    if (
        type(tracking) is not dict or set(tracking) != _FIXTURE_KEYS
        or tracking.get("origin") != "SYNTHETIC_ONLY"
        or type(tracking.get("schema_version")) is not int
        or tracking["schema_version"] != 1
        or tracking.get("scope") != "D537_NO_ACTIONS_REVIEW_ONLY"
        or tracking.get("account_identity_consistency") != "NOT_RECONCILED"
        or any(tracking.get(k) != "UNKNOWN" for k in (
            "current_positions", "current_pending_orders", "current_ea_state"))
        or tracking.get("simulation_only") is not True
        or any(type(tracking.get(k)) is not bool for k in (
            "external_g7_verified", "external_g8_verified",
            "actual_start_requested", "actual_evidence_collection_requested",
            "stop_release_requested", "mt4_operation_requested",
            "private_export_requested"))
    ):
        return False
    items = tracking.get("work_packages")
    return (
        type(items) is list and len(items) == 15
        and all(
            type(item) is dict and set(item) == _ROW_KEYS
            and item.get("criterion_id") == ident
            and all(type(item.get(k)) is str for k in (
                "implementation_state", "evidence_state",
                "approval_state", "acceptance_state"))
            for ident, item in zip(_ORDER, items)
        )
    )


def _tracking_false_claims(t: dict[str, object]) -> bool:
    return (
        any(t[k] for k in (
            "external_g7_verified", "external_g8_verified",
            "actual_start_requested", "actual_evidence_collection_requested",
            "stop_release_requested", "mt4_operation_requested",
            "private_export_requested"))
        or any(
            r["implementation_state"] != "NOT_IMPLEMENTED"
            or r["evidence_state"] != "NOT_COLLECTED"
            or r["approval_state"] != "NOT_GRANTED"
            or r["acceptance_state"] != "BLOCKED"
            for r in t["work_packages"]
        )
    )


def _check_d536_child(child: object) -> bool:
    return (
        type(child) is dict
        and type(child.get("status")) is str
        and type(child.get("d535_status")) is str
        and type(child.get("g2_design_criteria_count")) is int
        and child["g2_design_criteria_count"] == 7
        and type(child.get("g6_design_criteria_count")) is int
        and child["g6_design_criteria_count"] == 8
        and type(child.get("real_acceptance_criteria_completed")) is int
        and child["real_acceptance_criteria_completed"] == 0
        and type(child.get("effective_approved_actions")) is list
        and child["effective_approved_actions"] == []
        and child.get("safety_hold_latched") is True
        and child.get("phase_1") == "BLOCKED"
        and child.get("runtime_go_no_go") == "NO_GO"
        and "verified_values" in child and child["verified_values"] is None
        and child.get("account_identity_consistency") == "NOT_RECONCILED"
        and all(child.get(k) == "UNKNOWN" for k in (
            "current_positions", "current_pending_orders", "current_ea_state"))
        and all(child.get(k) is False for k in _D536_FALSE)
        and set(child) == set(_D536_FALSE) | {
            "status", "d535_status", "g2_design_criteria_count",
            "g6_design_criteria_count", "real_acceptance_criteria_completed",
            "effective_approved_actions", "safety_hold_latched",
            "account_identity_consistency", "current_positions",
            "current_pending_orders", "current_ea_state",
            "phase_1", "runtime_go_no_go", "verified_values",
        }
    )


def review_d537_workplan(
    plan: object, tracking: object,
    d536_contract: object, d536_readiness: object,
    d536_actions: object, d536_predecessors: object,
) -> dict[str, object]:
    """Audit an offline plan. No task is scheduled or marked accepted."""
    try:
        if not _valid_plan(plan):
            return _deny("D537_WORKPLAN_REJECTED_FAIL_CLOSED")
        if not _tracking_valid(tracking):
            return _deny("D537_TRACKING_SCHEMA_REJECTED_FAIL_CLOSED")
        if _tracking_false_claims(tracking):
            return _deny("D537_UNAUTHORIZED_PROGRESS_OR_ACTION_NO_GO")
        child = review_d536_readiness(
            d536_contract, d536_readiness, d536_actions,
            d536_predecessors,
        )
        if not _check_d536_child(child):
            return _deny("D537_PREDECESSOR_SAFETY_INVARIANT_FAIL_CLOSED")
        if child["status"] != (
                "D536_DESIGN_CRITERIA_DOCUMENTED_REAL_ACCEPTANCE_BLOCKED"):
            return _deny("D537_PREDECESSOR_NOT_COHERENT_NO_GO", child["status"])
        return _deny("D537_DESIGN_WORKPLAN_COHERENT_REAL_WORK_BLOCKED",
                     child["status"])
    except Exception:
        return _deny("D537_INPUT_EXCEPTION_FAIL_CLOSED")
