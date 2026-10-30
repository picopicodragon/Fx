"""P0-01 D5-27: G2 evidence-checklist and G6 failure-model OFFLINE auditor.

The inputs are untrusted design/synthetic records; this module performs NO
filesystem, OS-clock, MT4, account, broker, message or order operations.
Its output has no approval path. A PR merge cannot authorize any real action.
"""
from __future__ import annotations

_G2_TOPICS = (
    "TERMINAL_IDENTITY", "ACCOUNT_AND_SERVER_IDENTITY",
    "CONNECTION_AND_SESSION", "EA_ATTACHMENT_AND_AUTOTRADING",
    "POSITIONS", "PENDING_ORDERS",
    "TIMESTAMP_AND_SOURCE_PROVENANCE", "LOCAL_LOG_HANDLING",
)
_G6_THREATS = (
    "ATOMIC_COMMIT_TORN", "POWER_LOSS_MID_WRITE",
    "REFERENCE_ROLLBACK", "CO_EDIT_ALL_REFERENCES",
    "REVOCATION_ERASURE", "CONCURRENT_WRITER",
    "CLOCK_RESTART_OR_ANOMALY", "SIGNATURE_KEY_TAMPER",
    "STORAGE_UNAVAILABLE", "STALE_BACKUP_RESTORE",
)
_TOP = frozenset((
    "origin", "schema_version", "scope", "evidence_ledger_id",
    "gap_matrix_id", "g2", "g6", "approvals",
    "phase_1", "runtime_go_no_go", "verified_values",
))
_G2_KEYS = frozenset((
    "account_identity_consistency", "current_positions",
    "current_pending_orders", "current_ea_state",
    "report_ids", "checklist",
))
_G2_ROW_KEYS = frozenset((
    "id", "topic", "state", "evidence_reference",
    "real_world_verified", "future_operation_approved", "future_proof_required",
))
_G6_KEYS = frozenset((
    "independent_trust_anchor_implemented", "atomic_persistence_verified",
    "revocation_durable", "host_io_approved", "scenarios",
))
_G6_ROW_KEYS = frozenset((
    "id", "threat", "simulation_mode", "expected_outcome",
    "real_world_verified", "host_io_approved", "detection_limit",
    "future_proof_required",
))
_APPROVALS = frozenset((
    "visual_review", "mt4_launch", "account_login",
    "mt4_read_only_query", "ea_execution", "order_action",
    "stop_release", "host_io",
))
_CASE_KEYS = frozenset((
    "origin", "schema_version", "g2_simulation",
    "g6_failure", "simulated_stop_release_claim",
))
_G2_STATES = frozenset((
    "UNKNOWN", "SYNTHETIC_CONSISTENT", "SYNTHETIC_SCOPE_MISMATCH",
    "SYNTHETIC_TIME_MISMATCH", "SYNTHETIC_REPORT_CONFLICT",
))
_G6_STATES = frozenset(("NONE", *_G6_THREATS))
_STOP_RESULT = "SAFETY_HOLD_LATCHED_NO_GO"


def _blocked(status: str) -> dict[str, object]:
    return {
        "status": status,
        "g2_real_world_resolved": False,
        "g6_real_world_resolved": False,
        "account_identity_verified": False,
        "positions_verified": False,
        "pending_orders_verified": False,
        "ea_state_verified": False,
        "trusted_anchor_verified": False,
        "atomic_persistence_verified": False,
        "revocation_durable_verified": False,
        "real_transition_authorized": False,
        "visual_review_approved": False,
        "mt4_launch_approved": False,
        "mt4_read_only_approved": False,
        "host_io_approved": False,
        "approval_verified": False,
        "action_authorized": False,
        "ea_execution_authorized": False,
        "order_authorized": False,
        "stop_release_authorized": False,
        "effective_approved_actions": [],
        "safety_hold_latched": True,
        "runtime_go_no_go": "NO_GO",
        "phase_1": "BLOCKED",
        "verified_values": None,
        "broker_verified": False,
        "production_usable": False,
        "read_only_ex4_execution_approved": False,
        "terminal_execution_approved": False,
        "orders_generated": False,
        "forward_trading_enabled": False,
    }


def _nonempty_text(value: object) -> bool:
    return type(value) is str and 1 <= len(value.strip()) <= 400


def _design_is_valid(d: object) -> bool:
    if (type(d) is not dict or set(d) != _TOP
            or d.get("origin") != "OFFLINE_DESIGN_ONLY"
            or type(d.get("schema_version")) is not int
            or d["schema_version"] != 1
            or d.get("scope") != "SINGLE_MT4_ENVIRONMENT_NO_RUNTIME"
            or d.get("evidence_ledger_id")
            != "P0-01-D5-17-ACCOUNT-EVIDENCE-RECONCILIATION"
            or d.get("gap_matrix_id") != "P0-01-D5-25-GAP-VERIFICATION-MATRIX"
            or d.get("phase_1") != "BLOCKED"
            or d.get("runtime_go_no_go") != "NO_GO"
            or d.get("verified_values", "MISSING") is not None):
        return False
    a = d.get("approvals")
    if type(a) is not dict or set(a) != _APPROVALS:
        return False
    if any(a[k] is not False for k in _APPROVALS):
        return False
    g2 = d.get("g2")
    if type(g2) is not dict or set(g2) != _G2_KEYS:
        return False
    if (g2.get("account_identity_consistency") != "NOT_RECONCILED"
            or any(g2.get(key) != "UNKNOWN"
                   for key in ("current_positions", "current_pending_orders",
                               "current_ea_state"))
            or g2.get("report_ids") != ["EV-OLD", "EV-NEW"]):
        return False
    rows = g2.get("checklist")
    if type(rows) is not list or len(rows) != len(_G2_TOPICS):
        return False
    for i, row in enumerate(rows):
        if type(row) is not dict or set(row) != _G2_ROW_KEYS:
            return False
        if (row.get("id") != f"P27-G2-{i+1:02d}"
                or row.get("topic") != _G2_TOPICS[i]
                or row.get("state") != "NOT_PERFORMED"
                or row.get("evidence_reference", "MISSING") is not None
                or row.get("real_world_verified") is not False
                or row.get("future_operation_approved") is not False
                or not _nonempty_text(row.get("future_proof_required"))):
            return False
    g6 = d.get("g6")
    if type(g6) is not dict or set(g6) != _G6_KEYS:
        return False
    if any(g6.get(key) is not False for key in (
            "independent_trust_anchor_implemented",
            "atomic_persistence_verified", "revocation_durable",
            "host_io_approved")):
        return False
    rows = g6.get("scenarios")
    if type(rows) is not list or len(rows) != len(_G6_THREATS):
        return False
    for i, row in enumerate(rows):
        if type(row) is not dict or set(row) != _G6_ROW_KEYS:
            return False
        if (row.get("id") != f"P27-G6-{i+1:02d}"
                or row.get("threat") != _G6_THREATS[i]
                or row.get("simulation_mode") != "SYNTHETIC_ONLY"
                or row.get("expected_outcome") != _STOP_RESULT
                or row.get("real_world_verified") is not False
                or row.get("host_io_approved") is not False
                or row.get("detection_limit") != (
                    "UNDETECTABLE_WITH_UNTRUSTED_INPUTS"
                    if row["threat"] == "CO_EDIT_ALL_REFERENCES"
                    else "SYNTHETIC_REJECTION_ONLY")
                or not _nonempty_text(row.get("future_proof_required"))):
            return False
    return True


def _original_evidence_is_unverified(value: object) -> bool:
    """Do not let a new design rewrite old user reports as current facts."""
    if (type(value) is not dict
            or value.get("id") != "P0-01-D5-17-ACCOUNT-EVIDENCE-RECONCILIATION"
            or value.get("account_identity_consistency") != "NOT_RECONCILED"
            or value.get("scope") != "SINGLE_MT4_ENVIRONMENT_DESIGN_ONLY"
            or value.get("inquiry_status") != "CANCELLED_DO_NOT_SEND"
            or value.get("multiple_demo_accounts") != "OUT_OF_SCOPE"
            or value.get("broker_verified") is not False
            or value.get("terminal_execution_approved") is not False
            or value.get("runtime_go_no_go") != "NO_GO"
            or value.get("verified_values", "MISSING") is not None):
        return False
    if any(value.get(key) != "UNKNOWN"
           for key in ("positions_status", "pending_orders_status",
                       "ea_running_status")):
        return False
    reports = value.get("evidence")
    if type(reports) is not list or len(reports) != 2:
        return False
    earlier, later = reports
    if type(earlier) is not dict or type(later) is not dict:
        return False
    if (earlier.get("id") != "EV-OLD"
            or earlier.get("source_type") != "PRIOR_USER_VISUAL_REPORT"
            or earlier.get("scope_label") != "PRIOR_MT4_DEMO_A"
            or earlier.get("macd_sample") != "OBSERVED_PREVIOUSLY"
            or earlier.get("positions_or_pending_orders")
            != "PRESENT_REPORTED_PREVIOUSLY"
            or earlier.get("autotrading_display") != "OFF_LIKE"
            or later.get("id") != "EV-NEW"
            or later.get("source_type") != "LATEST_USER_REPORTED"
            or later.get("scope_label")
            != "EXISTING_RAKUTEN_ACCOUNT_UNSPECIFIED"
            or later.get("usage") != "DORMANT_REPORTED"
            or later.get("positions_and_orders") != "NONE_REPORTED"):
        return False
    for item in reports:
        if (item.get("reported_at_utc", "MISSING") is not None
                or item.get("observed_at_utc", "MISSING") is not None
                or item.get("broker_confirmed") is not False
                or item.get("current_state_verified") is not False):
            return False
    states = value.get("check_states")
    if type(states) is not list or len(states) != 8:
        return False
    for i, entry in enumerate(states):
        if (type(entry) is not dict or entry.get("id") != f"S17-{i+1:02d}"
                or entry.get("status") != "NOT_PERFORMED"
                or entry.get("evidence", "MISSING") is not None):
            return False
    approvals = value.get("approvals")
    return (type(approvals) is dict and len(approvals) == 7
            and all(v is False for v in approvals.values()))


def _gaps_are_unresolved(matrix: object) -> bool:
    if (type(matrix) is not dict
            or matrix.get("id") != "P0-01-D5-25-GAP-VERIFICATION-MATRIX"
            or matrix.get("origin") != "OFFLINE_SYNTHETIC_ONLY"
            or matrix.get("runtime_go_no_go") != "NO_GO"
            or matrix.get("phase_1") != "BLOCKED"
            or matrix.get("verified_values", "MISSING") is not None
            or matrix.get("real_mt4_access_approved") is not False
            or matrix.get("real_order_execution_approved") is not False):
        return False
    gaps = matrix.get("gaps")
    if type(gaps) is not list or len(gaps) != 9:
        return False
    seen = set()
    for item in gaps:
        if type(item) is not dict or type(item.get("id")) is not str:
            return False
        gid = item["id"]
        if (gid not in {f"G{i}" for i in range(1, 10)} or gid in seen
                or item.get("implementation_status") != "UNRESOLVED"
                or item.get("release_blocker") is not True
                or item.get("real_world_verified") is not False):
            return False
        seen.add(gid)
    return len(seen) == 9


def audit_d527_offline_preflight(
    design: object, original_evidence: object,
    gap_matrix: object, synthetic_case: object,
) -> dict[str, object]:
    """Check the design and mock faults. Never grants any real privilege."""
    try:
        if not _design_is_valid(design):
            return _blocked("D527_DESIGN_REJECTED_FAIL_CLOSED")
        if not _original_evidence_is_unverified(original_evidence):
            return _blocked("D527_EVIDENCE_BASELINE_REJECTED_FAIL_CLOSED")
        if not _gaps_are_unresolved(gap_matrix):
            return _blocked("D527_GAP_BASELINE_REJECTED_FAIL_CLOSED")
        case = synthetic_case
        if (type(case) is not dict or set(case) != _CASE_KEYS
                or case.get("origin") != "SYNTHETIC_ONLY"
                or type(case.get("schema_version")) is not int
                or case["schema_version"] != 1
                or type(case.get("g2_simulation")) is not str
                or case["g2_simulation"] not in _G2_STATES
                or type(case.get("g6_failure")) is not str
                or case["g6_failure"] not in _G6_STATES
                or type(case.get("simulated_stop_release_claim")) is not bool):
            return _blocked("D527_SYNTHETIC_CASE_REJECTED_FAIL_CLOSED")
        if case["simulated_stop_release_claim"]:
            return _blocked("D527_STOP_RELEASE_CLAIM_DENIED_NO_GO")
        if case["g6_failure"] != "NONE":
            return _blocked("D527_G6_SIMULATED_FAILURE_LATCHED_NO_GO")
        if case["g2_simulation"] != "SYNTHETIC_CONSISTENT":
            return _blocked("D527_G2_UNRECONCILED_NO_GO")
        return _blocked("D527_OFFLINE_DESIGN_COHERENT_NEVER_AUTHORIZED")
    except Exception:
        return _blocked("D527_INPUT_EXCEPTION_FAIL_CLOSED")
