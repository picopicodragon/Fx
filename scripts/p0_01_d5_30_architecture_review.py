"""P0-01 D5-30: NO_GO-only architecture and redacted G2 collection design.

This pure validator uses untrusted caller-supplied design and *synthetic*
state labels. It never reads files, calls MT4, opens a broker connection,
captures actual account evidence, measures a clock, signs or persists data.
"""
from __future__ import annotations

from scripts.p0_01_d5_27_g2_g6_offline_preflight import (
    _original_evidence_is_unverified, _gaps_are_unresolved,
)

_TOP = frozenset(("origin", "schema_version", "scope", "source_ledger_id",
                  "gap_matrix_id", "g2", "g6", "approvals",
                  "phase_1", "runtime_go_no_go", "verified_values"))
_G2_FIELDS = frozenset((
    "account_identity_consistency", "current_positions",
    "current_pending_orders", "current_ea_state", "report_ids",
    "collection_state", "collection_steps", "private_only_categories",
    "git_allowed_metadata_fields", "git_raw_evidence_allowed",
    "real_receipt_created", "redaction_review_performed",
    "local_private_storage_implemented",
))
_G2_STEP_FIELDS = frozenset((
    "id", "topic", "state", "future_manual_approval_required",
    "operation_performed", "evidence_collected", "instruction",
))
_G2_TOPICS = (
    "TERMINAL_IDENTITY", "ACCOUNT_AND_SERVER_IDENTITY",
    "CONNECTION_AND_SESSION", "EA_ATTACHMENT_AND_AUTOTRADING",
    "POSITIONS", "PENDING_ORDERS", "TIMESTAMP_AND_SOURCE_PROVENANCE",
    "LOCAL_LOG_HANDLING",
)
_PRIVACY = (
    "ACCOUNT_NUMBER", "SERVER_IDENTITY", "TERMINAL_PATH",
    "SCREENSHOT_BYTES", "RAW_MT4_LOG", "IP_OR_DEVICE_IDENTIFIER",
    "API_KEY_OR_SECRET", "REAL_ORDER_OR_POSITION_DETAILS",
    "REAL_OBSERVATION_TIMESTAMP",
)
_GIT_FIELDS = ("check_id", "design_state", "simulation_only")
_G6_FIELDS = frozenset((
    "architecture_state", "components", "commit_sequence",
    "critical_limits", "failure_scenarios", "recovery_policy",
    "host_io_implemented", "host_io_approved", "stop_release_approved",
))
_COMPONENT_FIELDS = frozenset((
    "id", "name", "responsibility", "implementation_state",
    "real_world_verified",
))
_COMPONENTS = (
    "STOP_LATCH_AUTHORITY", "SINGLE_WRITER_FENCE",
    "APPEND_ONLY_JOURNAL", "REVOCATION_TOMBSTONES",
    "ATOMIC_COMMIT_COORDINATOR", "INDEPENDENT_MONOTONIC_ANCHOR",
    "KEY_AND_SIGNATURE_VERIFIER", "RECOVERY_VERIFIER",
    "MONOTONIC_CLOCK_ADAPTER",
)
_COMMIT = (
    "LATCH_STOP_BEFORE_ACTION",
    "PREPARE_JOURNAL_AND_TOMBSTONE",
    "FLUSH_DURABLE_LOCAL_STATE",
    "VERIFY_CHECKPOINT_AND_WRITER_FENCE",
    "PUBLISH_INDEPENDENT_ANCHOR",
    "FINALIZE_LOCAL_CHECKPOINT",
    "VERIFY_RECOVERY_WITH_STOP_STILL_LATCHED",
)
_LIMITS = frozenset((
    "cross_resource_atomicity_guaranteed",
    "coordinated_forgery_detectable",
    "actual_monotonic_anchor_available",
    "actual_cryptographic_signatures_available",
))
_FAILURE_FIELDS = frozenset((
    "id", "threat", "design_outcome",
    "real_fault_injected", "independent_proof_required",
))
_THREATS = (
    "ATOMIC_COMMIT_TORN", "POWER_LOSS_MID_WRITE",
    "REFERENCE_ROLLBACK", "CO_EDIT_ALL_REFERENCES",
    "REVOCATION_ERASURE", "CONCURRENT_WRITER",
    "CLOCK_RESTART_OR_ANOMALY", "SIGNATURE_KEY_TAMPER",
    "STORAGE_UNAVAILABLE", "STALE_BACKUP_RESTORE",
)
_APPROVALS = frozenset((
    "visual_review", "mt4_launch", "account_login",
    "mt4_read_only_query", "ea_ex4_execution", "order_action",
    "stop_release", "host_io", "message_send", "live_trading",
))
_CASE_FIELDS = frozenset((
    "origin", "schema_version", "g2_simulated_privacy",
    "g6_simulated_recovery", "requested_operation",
    "simulated_only", "future_approval_claim",
))
_G2_CASES = frozenset((
    "SYNTHETIC_REDACTED_METADATA_ONLY", "SYNTHETIC_RAW_SECRET_PRESENT",
    "SYNTHETIC_UNKNOWN_PROVENANCE", "SYNTHETIC_ACCOUNT_SCOPE_MISMATCH",
    "SYNTHETIC_TIME_MISSING",
))
_G6_CASES = frozenset((
    "SYNTHETIC_DESIGN_SELF_CONSISTENT", "SYNTHETIC_TORN_COMMIT",
    "SYNTHETIC_REFERENCE_ROLLBACK", "SYNTHETIC_CO_EDITED",
    "SYNTHETIC_REVOCATION_ERASED", "SYNTHETIC_WRITER_CONFLICT",
    "SYNTHETIC_CLOCK_RESTART", "SYNTHETIC_KEY_TAMPER",
    "SYNTHETIC_STORAGE_FAILURE", "SYNTHETIC_STALE_BACKUP",
))
_OPERATIONS = frozenset((
    "NONE", "VISUAL_REVIEW", "MT4_LAUNCH", "ACCOUNT_LOGIN",
    "MT4_READ_ONLY", "HOST_IO", "EA_EX4", "ORDER",
    "STOP_RELEASE", "LIVE_TRADING", "MESSAGE_SEND",
))
_FALSE_FLAGS = (
    "g2_real_world_resolved", "g6_real_world_resolved",
    "account_identity_verified", "current_positions_verified",
    "current_pending_orders_verified", "current_ea_verified",
    "evidence_provenance_authenticated", "real_evidence_collected",
    "redaction_complete_verified", "local_storage_authorized",
    "independent_trust_anchor_verified", "atomic_persistence_verified",
    "revocation_durable_verified", "recovery_verified",
    "real_fault_injection_performed", "real_transition_authorized",
    "visual_review_approved", "mt4_launch_approved",
    "account_login_approved", "mt4_read_only_approved",
    "host_io_approved", "ea_execution_authorized",
    "order_authorized", "stop_release_authorized",
    "message_send_approved", "live_activation_approved",
    "approval_verified", "action_authorized", "broker_verified",
    "production_usable", "read_only_ex4_execution_approved",
    "terminal_execution_approved", "orders_generated",
    "forward_trading_enabled",
)


def _deny(status: str) -> dict[str, object]:
    result = {key: False for key in _FALSE_FLAGS}
    result.update({
        "status": status, "effective_approved_actions": [],
        "safety_hold_latched": True,
        "account_identity_consistency": "NOT_RECONCILED",
        "current_positions": "UNKNOWN",
        "current_pending_orders": "UNKNOWN",
        "current_ea_state": "UNKNOWN",
        "phase_1": "BLOCKED", "runtime_go_no_go": "NO_GO",
        "verified_values": None,
    })
    return result


def _text(value: object) -> bool:
    return type(value) is str and 1 <= len(value.strip()) <= 350


def _valid_plan(plan: object) -> bool:
    if (type(plan) is not dict or set(plan) != _TOP
            or plan.get("origin") != "OFFLINE_DESIGN_ONLY"
            or type(plan.get("schema_version")) is not int
            or plan["schema_version"] != 1
            or plan.get("scope") != "G2_G6_ARCHITECTURE_NO_RUNTIME"
            or plan.get("source_ledger_id")
                != "P0-01-D5-17-ACCOUNT-EVIDENCE-RECONCILIATION"
            or plan.get("gap_matrix_id")
                != "P0-01-D5-25-GAP-VERIFICATION-MATRIX"
            or plan.get("phase_1") != "BLOCKED"
            or plan.get("runtime_go_no_go") != "NO_GO"
            or "verified_values" not in plan
            or plan["verified_values"] is not None):
        return False
    approvals = plan.get("approvals")
    if (type(approvals) is not dict or set(approvals) != _APPROVALS
            or any(approvals[k] is not False for k in _APPROVALS)):
        return False
    g2 = plan.get("g2")
    if type(g2) is not dict or set(g2) != _G2_FIELDS:
        return False
    if (g2.get("account_identity_consistency") != "NOT_RECONCILED"
            or any(g2.get(k) != "UNKNOWN" for k in (
                "current_positions", "current_pending_orders", "current_ea_state"))
            or g2.get("report_ids") != ["EV-OLD", "EV-NEW"]
            or g2.get("collection_state") != "NOT_PERFORMED"
            or g2.get("private_only_categories") != list(_PRIVACY)
            or g2.get("git_allowed_metadata_fields") != list(_GIT_FIELDS)
            or any(g2.get(k) is not False for k in (
                "git_raw_evidence_allowed", "real_receipt_created",
                "redaction_review_performed",
                "local_private_storage_implemented"))):
        return False
    steps = g2.get("collection_steps")
    if type(steps) is not list or len(steps) != len(_G2_TOPICS):
        return False
    for i, item in enumerate(steps):
        if (type(item) is not dict or set(item) != _G2_STEP_FIELDS
                or item.get("id") != f"D530-G2-{i+1:02d}"
                or item.get("topic") != _G2_TOPICS[i]
                or item.get("state") != "NOT_PERFORMED"
                or item.get("future_manual_approval_required") is not True
                or item.get("operation_performed") is not False
                or item.get("evidence_collected") is not False
                or not _text(item.get("instruction"))):
            return False
    g6 = plan.get("g6")
    if type(g6) is not dict or set(g6) != _G6_FIELDS:
        return False
    if (g6.get("architecture_state") != "PROPOSED_NOT_IMPLEMENTED"
            or g6.get("commit_sequence") != list(_COMMIT)
            or g6.get("recovery_policy") !=
                "DEFAULT_STOP_UNLESS_INDEPENDENT_PROOFS_AND_EXPLICIT_APPROVAL"
            or any(g6.get(k) is not False for k in (
                "host_io_implemented", "host_io_approved",
                "stop_release_approved"))):
        return False
    limits = g6.get("critical_limits")
    if (type(limits) is not dict or set(limits) != _LIMITS
            or any(limits[k] is not False for k in _LIMITS)):
        return False
    components = g6.get("components")
    if type(components) is not list or len(components) != len(_COMPONENTS):
        return False
    for i, item in enumerate(components):
        if (type(item) is not dict or set(item) != _COMPONENT_FIELDS
                or item.get("id") != f"D530-G6-C{i+1:02d}"
                or item.get("name") != _COMPONENTS[i]
                or item.get("implementation_state") != "DESIGN_ONLY"
                or item.get("real_world_verified") is not False
                or not _text(item.get("responsibility"))):
            return False
    faults = g6.get("failure_scenarios")
    if type(faults) is not list or len(faults) != len(_THREATS):
        return False
    for i, item in enumerate(faults):
        if (type(item) is not dict or set(item) != _FAILURE_FIELDS
                or item.get("id") != f"D530-G6-F{i+1:02d}"
                or item.get("threat") != _THREATS[i]
                or item.get("design_outcome") != "STOP_LATCHED_NO_GO"
                or item.get("real_fault_injected") is not False
                or item.get("independent_proof_required") is not True):
            return False
    return True


def _valid_case(case: object) -> bool:
    return (
        type(case) is dict and set(case) == _CASE_FIELDS
        and case.get("origin") == "SYNTHETIC_ONLY"
        and type(case.get("schema_version")) is int
        and case["schema_version"] == 1
        and type(case.get("g2_simulated_privacy")) is str
        and case["g2_simulated_privacy"] in _G2_CASES
        and type(case.get("g6_simulated_recovery")) is str
        and case["g6_simulated_recovery"] in _G6_CASES
        and type(case.get("requested_operation")) is str
        and case["requested_operation"] in _OPERATIONS
        and case.get("simulated_only") is True
        and type(case.get("future_approval_claim")) is bool
    )


def review_d530_offline_architecture(
    plan: object, original_evidence: object,
    gap_matrix: object, synthetic_case: object,
) -> dict[str, object]:
    """Check an untrusted design; NOTHING here permits operational work."""
    try:
        if not _valid_plan(plan):
            return _deny("D530_DESIGN_REJECTED_FAIL_CLOSED")
        if not _original_evidence_is_unverified(original_evidence):
            return _deny("D530_SOURCE_BASELINE_REJECTED_FAIL_CLOSED")
        if not _gaps_are_unresolved(gap_matrix):
            return _deny("D530_GAP_BASELINE_REJECTED_FAIL_CLOSED")
        if not _valid_case(synthetic_case):
            return _deny("D530_CASE_REJECTED_FAIL_CLOSED")
        if (synthetic_case["requested_operation"] != "NONE"
                or synthetic_case["future_approval_claim"]):
            return _deny("D530_UNAUTHORIZED_OPERATION_DENIED_NO_GO")
        if synthetic_case["g2_simulated_privacy"] != (
                "SYNTHETIC_REDACTED_METADATA_ONLY"):
            return _deny("D530_G2_CAPTURE_OR_PRIVACY_UNSAFE_NO_GO")
        if synthetic_case["g6_simulated_recovery"] != (
                "SYNTHETIC_DESIGN_SELF_CONSISTENT"):
            return _deny("D530_G6_RECOVERY_UNTRUSTED_NO_GO")
        return _deny("D530_ARCHITECTURE_DESIGN_COHERENT_NEVER_AUTHORIZED")
    except Exception:
        return _deny("D530_INPUT_EXCEPTION_FAIL_CLOSED")
