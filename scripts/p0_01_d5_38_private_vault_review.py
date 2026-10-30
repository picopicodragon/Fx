"""P0-01 D5-38: PRIVATE evidence vault design requirements, not storage.

This module does not inspect the filesystem, Git history, OS clocks, MT4,
broker connections, secrets, files, keys or any live evidence. It merely
rejects unacceptable claims in caller-supplied synthetic requirement records.
"""
from __future__ import annotations

from scripts.p0_01_d5_37_workplan_review import (
    _FALSE as _D537_FALSE, review_d537_workplan,
)

_CLASSES = (
    "ACCOUNT_TERMINAL_IDENTIFIERS", "BROKER_SESSION_AND_SERVER",
    "EA_POSITION_ORDER_EVIDENCE", "RAW_LOG_AND_SCREENSHOT",
    "SECRET_MATERIAL", "OBSERVATION_PROVENANCE",
)
_ZONES = (
    "PRIVATE_EVIDENCE_ZONE_DESIGN",
    "SYNTHETIC_PUBLIC_METADATA_ZONE",
    "INDEPENDENT_ANCHOR_ZONE_DESIGN",
    "REJECT_OR_QUARANTINE_ZONE_DESIGN",
)
_THREATS = (
    "ACCIDENTAL_GIT_COMMIT", "GIT_HISTORY_REUSE", "CI_ARTIFACT_EXPORT",
    "DEBUG_LOG_EGRESS", "TEMP_WAL_SWAP_LEAK", "BACKUP_OR_SNAPSHOT_LEAK",
    "CRASH_DUMP_LEAK", "JUNCTION_SYMLINK_ESCAPE",
    "UNAUTHORIZED_READER", "RETENTION_UNKNOWN",
    "DELETION_WITH_REPLICA", "SHARED_TRUST_ROOT",
)
_POLICY_KEYS = frozenset((
    "encryption_algorithm", "key_custody", "retention_schedule",
    "deletion_semantics", "backup_policy", "audit_provenance",
    "public_export", "g6_anchor",
))
_POLICIES = {
    "encryption_algorithm": "UNDECIDED_REQUIRES_HUMAN_REVIEW",
    "key_custody": "UNDECIDED_REQUIRES_HUMAN_REVIEW",
    "retention_schedule": "UNDECIDED_REQUIRES_HUMAN_REVIEW",
    "deletion_semantics": "DELETE_REQUEST_NOT_ERASURE_PROOF",
    "backup_policy": "UNDECIDED_REQUIRES_HUMAN_REVIEW",
    "audit_provenance": "NOT_IMPLEMENTED",
    "public_export": "NO_REAL_PUBLIC_EXPORT",
    "g6_anchor": "SEPARATE_TRUST_BOUNDARY_NOT_IMPLEMENTED",
}
_PERMISSIONS = (
    "real_evidence_collect", "real_host_read", "real_host_write",
    "real_secret_scan", "real_git_hook", "real_git_history_scan",
    "real_backup_restore", "real_crypto", "real_key_management",
    "real_anchor_operation", "real_erasure_claim", "real_mt4_access",
    "real_order_execution", "real_stop_release", "real_public_export",
)
_PLAN_KEYS = frozenset((
    "origin", "schema_version", "scope", "target_criterion",
    "dependent_criterion", "independent_boundary", "privacy_classes",
    "zones", "controls", "permissions", "phase_1", "runtime_go_no_go",
    "verified_values",
))
_MATRIX_KEYS = frozenset((
    "origin", "schema_version", "scope", "zones", "threats",
    "retention_approved", "erasure_verified", "external_anchor_verified",
    "observed_at_utc", "account_identity_consistency",
    "current_positions", "current_pending_orders", "current_ea_state",
    "unresolved_gates", "safety_hold_latched",
))
_ZONE_KEYS = frozenset((
    "zone", "implementation_state", "real_path", "real_read_allowed",
    "real_write_allowed", "git_export_allowed",
))
_THREAT_KEYS = frozenset((
    "threat_id", "synthetic_only", "classification", "requested_action",
    "destination", "control_implemented", "real_evidence_observed",
    "mitigation_state",
))
_ACTIONS = (
    "DENY_ONLY", "ALLOW_PUBLIC_EXPORT", "ALLOW_PRIVATE_EXPORT",
    "ALLOW_DELETE", "ALLOW_RESTORE", "ALLOW_HOST_IO",
    "ALLOW_ANCHOR_PUBLISH", "ALLOW_GIT_WRITE",
)
_DESTINATIONS = (
    "DENY_SINK", "PUBLIC_METADATA", "GIT_REPOSITORY",
    "CI_ARTIFACT", "G6_ANCHOR", "EXTERNAL_BACKUP", "UNKNOWN",
)
_FALSE = (*_D537_FALSE, "g2_06_vault_implemented", "g2_06_access_verified",
          "g2_06_real_retention_enforced", "g2_06_real_erasure_verified",
          "g2_06_real_git_scanning_active", "g2_06_actual_private_store",
          "g2_06_encryption_verified", "g2_06_real_secret_detected",
          "g2_06_real_secret_protection_verified",
          "g6_independent_anchor_implemented",
          "g6_real_anchor_trust_boundary_verified",
          "future_private_evidence_authorized")


def _deny(status: str, upstream: str = "NOT_EVALUATED") -> dict[str, object]:
    out = {key: False for key in _FALSE}
    out.update({
        "status": status, "d537_status": upstream,
        "g2_06_design_threats_documented": len(_THREATS),
        "real_evidence_items_collected": 0,
        "real_work_packages_executed": 0,
        "real_acceptance_criteria_completed": 0,
        "effective_approved_actions": [],
        "safety_hold_latched": True,
        "account_identity_consistency": "NOT_RECONCILED",
        "current_positions": "UNKNOWN",
        "current_pending_orders": "UNKNOWN", "current_ea_state": "UNKNOWN",
        "phase_1": "BLOCKED", "runtime_go_no_go": "NO_GO",
        "verified_values": None,
    })
    return out


def _valid_design(p: object) -> bool:
    return (
        type(p) is dict and set(p) == _PLAN_KEYS
        and p.get("origin") == "OFFLINE_DESIGN_ONLY"
        and type(p.get("schema_version")) is int
        and p["schema_version"] == 1
        and p.get("scope") == "D538_G2_06_PRIVATE_EVIDENCE_VAULT_REQUIREMENTS_ONLY"
        and p.get("target_criterion") == "G2-06"
        and p.get("dependent_criterion") == "G2-07"
        and p.get("independent_boundary") == "G6-02"
        and p.get("privacy_classes") == list(_CLASSES)
        and p.get("zones") == list(_ZONES)
        and type(p.get("controls")) is dict
        and set(p["controls"]) == _POLICY_KEYS
        and p["controls"] == _POLICIES
        and type(p.get("permissions")) is dict
        and set(p["permissions"]) == set(_PERMISSIONS)
        and all(p["permissions"][k] is False for k in _PERMISSIONS)
        and p.get("phase_1") == "BLOCKED"
        and p.get("runtime_go_no_go") == "NO_GO"
        and "verified_values" in p and p["verified_values"] is None
    )


def _valid_matrix_shape(m: object) -> bool:
    if not (
        type(m) is dict and set(m) == _MATRIX_KEYS
        and m.get("origin") == "SYNTHETIC_ONLY"
        and type(m.get("schema_version")) is int and m["schema_version"] == 1
        and m.get("scope") == "D538_THREAT_MATRIX_DESIGN_ONLY"
        and m.get("unresolved_gates") == [f"G{i}" for i in range(1, 10)]
        and m.get("account_identity_consistency") == "NOT_RECONCILED"
        and all(m.get(k) == "UNKNOWN" for k in (
            "current_positions", "current_pending_orders", "current_ea_state"))
        and m.get("safety_hold_latched") is True
        and "observed_at_utc" in m and m["observed_at_utc"] is None
        and all(type(m.get(k)) is bool for k in (
            "retention_approved", "erasure_verified",
            "external_anchor_verified"))
    ):
        return False
    zones = m.get("zones")
    if type(zones) is not list or len(zones) != len(_ZONES):
        return False
    for zone, name in zip(zones, _ZONES):
        if (type(zone) is not dict or set(zone) != _ZONE_KEYS
                or zone.get("zone") != name
                or type(zone.get("implementation_state")) is not str
                or "real_path" not in zone or zone["real_path"] is not None
                or any(type(zone.get(k)) is not bool for k in (
                    "real_read_allowed", "real_write_allowed",
                    "git_export_allowed"))):
            return False
    rows = m.get("threats")
    if type(rows) is not list or len(rows) != len(_THREATS):
        return False
    for i, (row, threat) in enumerate(zip(rows, _THREATS)):
        if (type(row) is not dict or set(row) != _THREAT_KEYS
                or row.get("threat_id") != threat
                or row.get("classification") != _CLASSES[i % len(_CLASSES)]
                or row.get("synthetic_only") is not True
                or type(row.get("requested_action")) is not str
                or row["requested_action"] not in _ACTIONS
                or type(row.get("destination")) is not str
                or row["destination"] not in _DESTINATIONS
                or type(row.get("control_implemented")) is not bool
                or type(row.get("real_evidence_observed")) is not bool
                or type(row.get("mitigation_state")) is not str):
            return False
    return True


def _child_safe(c: object) -> bool:
    return (
        type(c) is dict
        and type(c.get("status")) is str
        and type(c.get("d536_status")) is str
        and type(c.get("work_packages_planned")) is int
        and c["work_packages_planned"] == 15
        and type(c.get("work_packages_executed")) is int
        and c["work_packages_executed"] == 0
        and type(c.get("real_acceptance_criteria_completed")) is int
        and c["real_acceptance_criteria_completed"] == 0
        and type(c.get("effective_approved_actions")) is list
        and c["effective_approved_actions"] == []
        and c.get("safety_hold_latched") is True
        and c.get("phase_1") == "BLOCKED"
        and c.get("runtime_go_no_go") == "NO_GO"
        and "verified_values" in c and c["verified_values"] is None
        and c.get("account_identity_consistency") == "NOT_RECONCILED"
        and all(c.get(k) == "UNKNOWN" for k in (
            "current_positions", "current_pending_orders", "current_ea_state"))
        and all(c.get(k) is False for k in _D537_FALSE)
        and set(c) == set(_D537_FALSE) | {
            "status", "d536_status", "work_packages_planned",
            "work_packages_executed", "real_acceptance_criteria_completed",
            "effective_approved_actions", "safety_hold_latched",
            "account_identity_consistency", "current_positions",
            "current_pending_orders", "current_ea_state",
            "phase_1", "runtime_go_no_go", "verified_values",
        }
    )


def review_d538_private_vault(
    design: object, threat_matrix: object,
    workplan: object, tracking: object,
    d536_contract: object, d536_readiness: object,
    d536_actions: object, d536_predecessors: object,
) -> dict[str, object]:
    """Inspect immutable synthetic G2-06 controls; all outcomes deny real IO."""
    try:
        if not _valid_design(design):
            return _deny("D538_G2_06_DESIGN_CONTRACT_REJECTED_FAIL_CLOSED")
        if not _valid_matrix_shape(threat_matrix):
            return _deny("D538_G2_06_THREAT_SCHEMA_REJECTED_FAIL_CLOSED")
        if any(threat_matrix[k] for k in (
            "retention_approved", "erasure_verified", "external_anchor_verified")):
            return _deny("D538_FALSE_ERASURE_RETENTION_ANCHOR_CLAIM_NO_GO")
        for zone in threat_matrix["zones"]:
            if (zone["implementation_state"] != "NOT_IMPLEMENTED"
                    or zone["real_read_allowed"] or zone["real_write_allowed"]
                    or zone["git_export_allowed"]):
                return _deny("D538_UNAUTHORIZED_STORAGE_ZONE_CLAIM_NO_GO")
        for row in threat_matrix["threats"]:
            if row["destination"] != "DENY_SINK":
                return _deny("D538_G2_G6_PRIVACY_EGRESS_DENIED_NO_GO")
            if row["requested_action"] != "DENY_ONLY":
                return _deny("D538_UNAUTHORIZED_DATA_OPERATION_NO_GO")
            if (row["control_implemented"] or row["real_evidence_observed"]
                    or row["mitigation_state"] != "DESIGN_REQUIRED"):
                return _deny("D538_FALSE_PROTECTION_IMPLEMENTED_CLAIM_NO_GO")
        child = review_d537_workplan(
            workplan, tracking, d536_contract, d536_readiness,
            d536_actions, d536_predecessors,
        )
        if not _child_safe(child):
            return _deny("D538_PREDECESSOR_SAFETY_INVARIANT_FAIL_CLOSED")
        if child["status"] != "D537_DESIGN_WORKPLAN_COHERENT_REAL_WORK_BLOCKED":
            return _deny("D538_PREDECESSOR_NOT_COHERENT_NO_GO", child["status"])
        return _deny("D538_VAULT_REQUIREMENTS_DESIGNED_NO_REAL_STORAGE_OR_ERASURE",
                     child["status"])
    except Exception:
        return _deny("D538_INPUT_EXCEPTION_FAIL_CLOSED")
