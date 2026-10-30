"""P0-01 D5-32: strict synthetic public JSON and G6 crash-cut matrix.

Pure in-memory checks only. No file scans, Git hooks, host storage, MT4,
broker access, wall clock, signatures, notification or order execution.
The old user reports, synthetic timestamps and all anchor claims are untrusted.
"""
from __future__ import annotations

import json

from scripts.p0_01_d5_27_g2_g6_offline_preflight import (
    _gaps_are_unresolved, _original_evidence_is_unverified,
)
from scripts.p0_01_d5_31_protocol_privacy_gate import (
    _APPROVED_NONE, _STAGES, _public_metadata_valid, _recovery_valid,
    review_d531_protocol,
)

_CONTRACT_KEYS = frozenset((
    "origin", "schema_version", "scope", "g2_public_max_bytes",
    "g2_public_json_encoding", "g2_canonical_json_required",
    "g6_crash_cutpoints", "g6_expected_healthy_statuses",
    "g6_independent_trust_anchor_verified", "g6_actual_crash_test_performed",
    "host_io_approved", "phase_1", "runtime_go_no_go", "verified_values",
))
_ROW_KEYS = frozenset(("id", "recovery"))
_ROW_IDS = tuple(f"D532-CUT-{i:02d}" for i in range(len(_STAGES) + 1))
_PARTIAL = "D531_G6_PARTIAL_COMMIT_STOP_HELD_NO_GO"
_COMPLETE = "D531_SYNTHETIC_PROTOCOL_COHERENT_NEVER_AUTHORIZED"
_EXPECTED = (_PARTIAL,) * len(_STAGES) + (_COMPLETE,)
_CHILD_STATUSES = frozenset((
    _PARTIAL, _COMPLETE, "D531_G6_UNTRUSTED_FAULT_NO_GO",
    "D531_G6_STOP_LATCH_LOST_NO_GO",
    "D531_G6_RECORD_SCOPE_MISMATCH_NO_GO",
    "D531_G6_ROLLBACK_NO_GO", "D531_G6_REVOCATION_ERASURE_NO_GO",
    "D531_G6_REVOCATION_CHANGE_NO_GO",
    "D531_G6_UNPINNED_ADVANCE_NO_GO",
    "D531_G6_HASH_MISMATCH_NO_GO",
    "D531_UNAUTHORIZED_STOP_RELEASE_NO_GO",
))
_OUTPUT_FALSE = (*_APPROVED_NONE,
    "g2_real_world_evidence_collected", "g2_git_hook_installed",
    "g2_git_history_scanned", "g2_real_secret_leakage_ruled_out",
    "g6_crash_recovery_real_world_verified", "g6_independent_anchor_real",
    "g6_actual_atomic_commit_verified", "g6_real_revocation_verified",
    "crash_recovery_authorized", "simulated_state_promoted_to_runtime",
)
_PUBLIC_MAX = 384


def _deny(status: str, child_statuses: tuple[str, ...] = ()) -> dict[str, object]:
    result = {key: False for key in _OUTPUT_FALSE}
    result.update({
        "status": status,
        "synthetic_cutpoint_statuses": list(child_statuses),
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


def _valid_contract(c: object) -> bool:
    return (
        type(c) is dict and set(c) == _CONTRACT_KEYS
        and c.get("origin") == "OFFLINE_DESIGN_ONLY"
        and type(c.get("schema_version")) is int
        and c["schema_version"] == 1
        and c.get("scope") == "D532_G2_G6_CRASH_MATRIX_SYNTHETIC_ONLY"
        and type(c.get("g2_public_max_bytes")) is int
        and c["g2_public_max_bytes"] == _PUBLIC_MAX
        and c.get("g2_public_json_encoding") == "ASCII_CANONICAL"
        and c.get("g2_canonical_json_required") is True
        and c.get("g6_crash_cutpoints") == list(_ROW_IDS)
        and c.get("g6_expected_healthy_statuses") == list(_EXPECTED)
        and all(c.get(k) is False for k in (
            "g6_independent_trust_anchor_verified",
            "g6_actual_crash_test_performed", "host_io_approved"))
        and c.get("phase_1") == "BLOCKED"
        and c.get("runtime_go_no_go") == "NO_GO"
        and "verified_values" in c and c["verified_values"] is None
    )


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    item: dict[str, object] = {}
    for key, value in pairs:
        if key in item:
            raise ValueError("duplicate synthetic key")
        item[key] = value
    return item


def _reject_nonfinite(value: str) -> None:
    raise ValueError("non-finite JSON number")


def _public_json_valid(payload: object) -> bool:
    if (type(payload) is not str
            or not 1 <= len(payload) <= _PUBLIC_MAX
            or not payload.isascii()):
        return False
    try:
        data = json.loads(
            payload,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_nonfinite,
        )
        return (
            _public_metadata_valid(data)
            and json.dumps(
                data, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                allow_nan=False,
            ) == payload
        )
    except (ValueError, TypeError, RecursionError, OverflowError):
        return False


def _child_safe(child: object) -> bool:
    if (type(child) is not dict
            or child.get("status") not in _CHILD_STATUSES
            or type(child.get("effective_approved_actions")) is not list
            or child["effective_approved_actions"] != []
            or child.get("safety_hold_latched") is not True
            or child.get("phase_1") != "BLOCKED"
            or child.get("runtime_go_no_go") != "NO_GO"
            or "verified_values" not in child or child["verified_values"] is not None):
        return False
    if any(child.get(k) is not False for k in _APPROVED_NONE):
        return False
    return (
        child.get("account_identity_consistency") == "NOT_RECONCILED"
        and all(child.get(k) == "UNKNOWN" for k in
                ("current_positions", "current_pending_orders",
                 "current_ea_state"))
        and set(child) == (
            set(_APPROVED_NONE) | {
                "status", "effective_approved_actions",
                "safety_hold_latched", "account_identity_consistency",
                "current_positions", "current_pending_orders",
                "current_ea_state", "phase_1", "runtime_go_no_go",
                "verified_values",
            }
        )
    )


def review_d532_crash_matrix(
    contract: object, d531_contract: object,
    original_evidence: object, gap_matrix: object,
    public_json: object, matrix: object,
) -> dict[str, object]:
    """Evaluate every synthetic cutpoint; never authorize any real operation."""
    try:
        if not _valid_contract(contract):
            return _deny("D532_CONTRACT_REJECTED_FAIL_CLOSED")
        if not _original_evidence_is_unverified(original_evidence):
            return _deny("D532_SOURCE_BASELINE_REJECTED_FAIL_CLOSED")
        if not _gaps_are_unresolved(gap_matrix):
            return _deny("D532_GAP_BASELINE_REJECTED_FAIL_CLOSED")
        if not _public_json_valid(public_json):
            return _deny("D532_G2_PUBLIC_JSON_REJECTED_FAIL_CLOSED")
        if type(matrix) is not list or len(matrix) != len(_ROW_IDS):
            return _deny("D532_CRASH_MATRIX_REJECTED_FAIL_CLOSED")
        parsed_public = json.loads(public_json)
        statuses: list[str] = []
        baseline = None
        for i, row in enumerate(matrix):
            if (type(row) is not dict or set(row) != _ROW_KEYS
                    or row.get("id") != _ROW_IDS[i]
                    or not _recovery_valid(row.get("recovery"))):
                return _deny("D532_CRASH_MATRIX_REJECTED_FAIL_CLOSED")
            recovery = row["recovery"]
            if recovery["completed_stages"] != list(_STAGES[:i]):
                return _deny("D532_CRASH_MATRIX_REJECTED_FAIL_CLOSED")
            if baseline is None:
                baseline = recovery["before"]
            elif recovery["before"] != baseline:
                return _deny("D532_CRASH_MATRIX_SCOPE_REJECTED_FAIL_CLOSED")
            child = review_d531_protocol(
                d531_contract, original_evidence, gap_matrix,
                parsed_public, recovery,
            )
            if not _child_safe(child):
                return _deny("D532_CHILD_DENIAL_INVARIANT_REJECTED_FAIL_CLOSED")
            statuses.append(child["status"])
        if tuple(statuses) != _EXPECTED:
            return _deny("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", tuple(statuses))
        # All cutpoints are merely synthetic labels supplied by the caller.
        return _deny("D532_SYNTHETIC_CUTPOINT_COVERAGE_NEVER_AUTHORIZED",
                     tuple(statuses))
    except Exception:
        return _deny("D532_INPUT_EXCEPTION_FAIL_CLOSED")
