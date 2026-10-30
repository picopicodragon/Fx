"""P0-01 D5-31: strict public-metadata boundary and synthetic recovery FSM.

This module has no filesystem, OS clock, network, MT4, broker, cryptography,
storage writer, notification or order access. The inputs are UNTRUSTED. The
validator is NOT a Git hook or proof that committed data were scanned.
"""
from __future__ import annotations

import re

from scripts.p0_01_d5_27_g2_g6_offline_preflight import (
    _gaps_are_unresolved, _original_evidence_is_unverified,
)

_STAGES = (
    "LATCH_STOP_BEFORE_ACTION",
    "PREPARE_JOURNAL_AND_TOMBSTONE",
    "FLUSH_DURABLE_LOCAL_STATE",
    "VERIFY_CHECKPOINT_AND_WRITER_FENCE",
    "PUBLISH_INDEPENDENT_ANCHOR",
    "FINALIZE_LOCAL_CHECKPOINT",
    "VERIFY_RECOVERY_WITH_STOP_STILL_LATCHED",
)
_THREATS = (
    "ATOMIC_COMMIT_TORN", "POWER_LOSS_MID_WRITE",
    "REFERENCE_ROLLBACK", "CO_EDIT_ALL_REFERENCES",
    "REVOCATION_ERASURE", "CONCURRENT_WRITER",
    "CLOCK_RESTART_OR_ANOMALY", "SIGNATURE_KEY_TAMPER",
    "STORAGE_UNAVAILABLE", "STALE_BACKUP_RESTORE",
)
_CHECKS = tuple(f"D530-G2-{i:02d}" for i in range(1, 9))
_PUBLIC_KEYS = frozenset(("origin", "schema_version", "check_id",
                          "design_state", "simulation_only"))
_PLAN_KEYS = frozenset(("origin", "schema_version", "scope", "g2",
                       "g6", "approvals", "phase_1",
                       "runtime_go_no_go", "verified_values"))
_PLAN_G2 = frozenset(("check_ids", "public_fields", "raw_evidence_approved",
                     "private_storage_implemented", "real_collection_performed"))
_PLAN_G6 = frozenset(("commit_stages", "faults", "independent_anchor_available",
                     "atomic_storage_implemented", "recovery_verified",
                     "signatures_implemented", "cross_store_atomicity_verified",
                     "host_io_approved", "stop_release_approved"))
_APPROVALS = frozenset(("mt4_launch", "account_login", "visual_review",
                        "mt4_read_only", "host_io", "ea_ex4_execution",
                        "orders", "stop_release", "live_trading"))
_RECOVERY_KEYS = frozenset(("origin", "schema_version", "completed_stages",
                           "before", "after", "fault", "anchor_claim",
                           "storage_claim", "writer_claim", "clock_claim",
                           "revocation_claim", "simulated_stop_release_claim",
                           "simulated_only"))
_SNAPSHOT_KEYS = frozenset(("record_id", "generation", "sequence",
                            "head_hash", "revocation_tombstone", "stop_latched"))
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_RECORD = re.compile(r"SYNTHETIC_RECORD_[A-Z0-9_]{1,32}\Z")
_APPROVED_NONE = ("g2_real_world_resolved", "g6_real_world_resolved",
                  "evidence_provenance_authenticated", "account_identity_verified",
                  "positions_verified", "pending_orders_verified",
                  "ea_state_verified", "private_storage_implemented",
                  "public_export_authorized", "all_public_content_scanned",
                  "independent_trust_anchor_verified", "atomic_persistence_verified",
                  "revocation_durable_verified", "recovery_verified",
                  "cross_store_atomicity_verified", "real_fault_injected",
                  "mt4_launch_approved", "account_login_approved",
                  "visual_review_approved", "mt4_read_only_approved",
                  "host_io_approved", "ea_execution_authorized",
                  "order_authorized", "stop_release_authorized",
                  "approval_verified", "action_authorized",
                  "real_transition_authorized", "broker_verified",
                  "production_usable", "terminal_execution_approved",
                  "read_only_ex4_execution_approved", "orders_generated",
                  "forward_trading_enabled")
_OK_STORAGE = "SYNTHETIC_CONFIRMED"
_OK_ANCHOR = "SYNTHETIC_MATCH"
_OK_WRITER = "SYNTHETIC_SINGLE_WRITER"
_OK_CLOCK = "SYNTHETIC_CLOCK_STABLE"
_OK_REVOCATION = "SYNTHETIC_INDEX_MATCH"


def _deny(status: str) -> dict[str, object]:
    result = {key: False for key in _APPROVED_NONE}
    result.update({
        "status": status,
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
    return result


def _valid_plan(plan: object) -> bool:
    if (type(plan) is not dict or set(plan) != _PLAN_KEYS
            or plan.get("origin") != "OFFLINE_DESIGN_ONLY"
            or type(plan.get("schema_version")) is not int
            or plan["schema_version"] != 1
            or plan.get("scope") != "D531_G2_G6_SYNTHETIC_PROTOCOL_ONLY"
            or plan.get("phase_1") != "BLOCKED"
            or plan.get("runtime_go_no_go") != "NO_GO"
            or plan.get("verified_values", "MISSING") is not None):
        return False
    approvals = plan.get("approvals")
    if (type(approvals) is not dict or set(approvals) != _APPROVALS
            or any(v is not False for v in approvals.values())):
        return False
    g2 = plan.get("g2")
    if (type(g2) is not dict or set(g2) != _PLAN_G2
            or g2.get("check_ids") != list(_CHECKS)
            or g2.get("public_fields") != sorted(_PUBLIC_KEYS)
            or any(g2.get(k) is not False for k in (
                "raw_evidence_approved", "private_storage_implemented",
                "real_collection_performed"))):
        return False
    g6 = plan.get("g6")
    return (
        type(g6) is dict and set(g6) == _PLAN_G6
        and g6.get("commit_stages") == list(_STAGES)
        and g6.get("faults") == list(_THREATS)
        and all(g6.get(k) is False for k in (
            "independent_anchor_available", "atomic_storage_implemented",
            "recovery_verified", "signatures_implemented",
            "cross_store_atomicity_verified", "host_io_approved",
            "stop_release_approved"))
    )


def _public_metadata_valid(data: object) -> bool:
    # Exact allowlist. No notes, dynamic keys, nested values, IDs or real
    # timestamps. Never "sanitize and publish" sensitive untrusted content.
    return (
        type(data) is dict and set(data) == _PUBLIC_KEYS
        and data.get("origin") == "SYNTHETIC_ONLY"
        and type(data.get("schema_version")) is int
        and data["schema_version"] == 1
        and type(data.get("check_id")) is str
        and data["check_id"] in _CHECKS
        and data.get("design_state") == "NOT_PERFORMED"
        and data.get("simulation_only") is True
    )


def _snapshot_valid(s: object) -> bool:
    return (
        type(s) is dict and set(s) == _SNAPSHOT_KEYS
        and type(s.get("record_id")) is str
        and _RECORD.fullmatch(s["record_id"]) is not None
        and type(s.get("generation")) is int
        and 1 <= s["generation"] <= 1000000
        and type(s.get("sequence")) is int
        and 0 <= s["sequence"] <= 1000000
        and type(s.get("head_hash")) is str
        and _HASH.fullmatch(s["head_hash"]) is not None
        and type(s.get("revocation_tombstone")) is bool
        and type(s.get("stop_latched")) is bool
    )


def _recovery_valid(data: object) -> bool:
    if (type(data) is not dict or set(data) != _RECOVERY_KEYS
            or data.get("origin") != "SYNTHETIC_ONLY"
            or type(data.get("schema_version")) is not int
            or data["schema_version"] != 1
            or data.get("simulated_only") is not True
            or type(data.get("simulated_stop_release_claim")) is not bool
            or not _snapshot_valid(data.get("before"))
            or not _snapshot_valid(data.get("after"))):
        return False
    stages = data.get("completed_stages")
    if (type(stages) is not list or len(stages) > len(_STAGES)
            or stages != list(_STAGES[:len(stages)])):
        return False
    return (
        type(data.get("fault")) is str
        and data["fault"] in ("NONE", *_THREATS)
        and type(data.get("anchor_claim")) is str
        and data["anchor_claim"] in (_OK_ANCHOR, "SYNTHETIC_MISMATCH",
                                      "SYNTHETIC_UNKNOWN")
        and type(data.get("storage_claim")) is str
        and data["storage_claim"] in (_OK_STORAGE, "SYNTHETIC_FAILED",
                                       "SYNTHETIC_UNKNOWN")
        and type(data.get("writer_claim")) is str
        and data["writer_claim"] in (_OK_WRITER, "SYNTHETIC_CONFLICT",
                                      "SYNTHETIC_UNKNOWN")
        and type(data.get("clock_claim")) is str
        and data["clock_claim"] in (_OK_CLOCK, "SYNTHETIC_CLOCK_ANOMALY",
                                     "SYNTHETIC_UNKNOWN")
        and type(data.get("revocation_claim")) is str
        and data["revocation_claim"] in (_OK_REVOCATION,
                                          "SYNTHETIC_TOMBSTONE_MISSING",
                                          "SYNTHETIC_UNKNOWN")
    )


def review_d531_protocol(
    plan: object, original_evidence: object, gap_matrix: object,
    public_metadata: object, synthetic_recovery: object,
) -> dict[str, object]:
    """Diagnostics only, with deliberately no path to actual permissions."""
    try:
        if not _valid_plan(plan):
            return _deny("D531_DESIGN_REJECTED_FAIL_CLOSED")
        if not _original_evidence_is_unverified(original_evidence):
            return _deny("D531_SOURCE_BASELINE_REJECTED_FAIL_CLOSED")
        if not _gaps_are_unresolved(gap_matrix):
            return _deny("D531_GAP_BASELINE_REJECTED_FAIL_CLOSED")
        if not _public_metadata_valid(public_metadata):
            return _deny("D531_G2_PUBLIC_METADATA_REJECTED_FAIL_CLOSED")
        if not _recovery_valid(synthetic_recovery):
            return _deny("D531_G6_PROTOCOL_INPUT_REJECTED_FAIL_CLOSED")
        r = synthetic_recovery
        if r["simulated_stop_release_claim"]:
            return _deny("D531_UNAUTHORIZED_STOP_RELEASE_NO_GO")
        if (r["fault"] != "NONE"
                or r["anchor_claim"] != _OK_ANCHOR
                or r["storage_claim"] != _OK_STORAGE
                or r["writer_claim"] != _OK_WRITER
                or r["clock_claim"] != _OK_CLOCK
                or r["revocation_claim"] != _OK_REVOCATION):
            return _deny("D531_G6_UNTRUSTED_FAULT_NO_GO")
        before, after = r["before"], r["after"]
        if not before["stop_latched"] or not after["stop_latched"]:
            return _deny("D531_G6_STOP_LATCH_LOST_NO_GO")
        if before["record_id"] != after["record_id"]:
            return _deny("D531_G6_RECORD_SCOPE_MISMATCH_NO_GO")
        if (after["generation"] < before["generation"]
                or after["sequence"] < before["sequence"]):
            return _deny("D531_G6_ROLLBACK_NO_GO")
        if before["revocation_tombstone"] and not after["revocation_tombstone"]:
            return _deny("D531_G6_REVOCATION_ERASURE_NO_GO")
        if before["revocation_tombstone"] != after["revocation_tombstone"]:
            return _deny("D531_G6_REVOCATION_CHANGE_NO_GO")
        if (after["generation"] != before["generation"]
                or after["sequence"] != before["sequence"]):
            return _deny("D531_G6_UNPINNED_ADVANCE_NO_GO")
        if before["head_hash"] != after["head_hash"]:
            return _deny("D531_G6_HASH_MISMATCH_NO_GO")
        if len(r["completed_stages"]) != len(_STAGES):
            return _deny("D531_G6_PARTIAL_COMMIT_STOP_HELD_NO_GO")
        # Even a fully completed *synthetic* trace provides no real evidence.
        return _deny("D531_SYNTHETIC_PROTOCOL_COHERENT_NEVER_AUTHORIZED")
    except Exception:
        return _deny("D531_INPUT_EXCEPTION_FAIL_CLOSED")
