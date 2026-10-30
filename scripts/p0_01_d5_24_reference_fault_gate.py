"""D5-24: synthetic reference comparison and storage-fault denial gate.

Pure functions only. A "reference" and all storage/clock flags are caller-
supplied mock inputs, NOT trustworthy external measurements or persistence.
No live authentication, trusted anchor, broker, MT4, clock, or order actions.
"""
from __future__ import annotations

import re

from scripts.p0_01_d5_23_history_checkpoint import (
    audit_synthetic_history_checkpoint,
)

_BUNDLE = frozenset((
    "origin", "schema_version", "history_bundle", "reference",
    "minimum_generation", "simulated_storage",
))
_REFERENCE = frozenset((
    "reference_id", "record_id", "sequence", "head_hash",
    "revocation_tombstone", "generation",
))
_STORAGE = frozenset((
    "write_state", "restore_state", "reference_read_state",
    "clock_state", "concurrent_writer_detected",
))
_REF_ID = re.compile(r"SYNTHETIC_REFERENCE_[A-Z0-9_]{1,32}\Z")
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_HISTORY_OK = "HISTORY_SYNTHETIC_CHAIN_CONSISTENT_NO_GO"
_CONFIRMED = "SYNTHETIC_CONFIRMED"
_CLOCK_OK = "SYNTHETIC_CLOCK_STABLE"
_SIM_STATES = frozenset((_CONFIRMED, "SYNTHETIC_FAILED", "SYNTHETIC_UNKNOWN"))
_CLOCK_STATES = frozenset((_CLOCK_OK, "SYNTHETIC_CLOCK_ANOMALY", "SYNTHETIC_UNKNOWN"))


def _result(status: str, history_status: str = "NOT_EVALUATED") -> dict[str, object]:
    return {
        "status": status,
        "history_status": history_status,
        "reference_authentic": False,
        "revocation_persisted": False,
        "trusted_clock_verified": False,
        "actual_replay_protection": False,
        "approval_verified": False,
        "action_authorized": False,
        "ea_execution_authorized": False,
        "order_authorized": False,
        "stop_release_authorized": False,
        "effective_approved_actions": [],
        "safety_hold_latched": True,
        "runtime_go_no_go": "NO_GO",
        "verified_values": None,
        "broker_verified": False,
        "production_usable": False,
        "read_only_ex4_execution_approved": False,
        "terminal_execution_approved": False,
        "orders_generated": False,
        "forward_trading_enabled": False,
        "phase_1": "BLOCKED",
    }


def _valid_history_denial(result: object) -> bool:
    if type(result) is not dict:
        return False
    expected = {
        "status": _HISTORY_OK, "runtime_go_no_go": "NO_GO",
        "phase_1": "BLOCKED", "verified_values": None,
        "safety_hold_latched": True,
        "approval_verified": False, "action_authorized": False,
        "ea_execution_authorized": False, "order_authorized": False,
        "stop_release_authorized": False, "effective_approved_actions": [],
        "broker_verified": False, "production_usable": False,
        "read_only_ex4_execution_approved": False,
        "terminal_execution_approved": False, "orders_generated": False,
        "forward_trading_enabled": False,
    }
    for field, value in expected.items():
        if field not in result or result[field] != value:
            return False
        if type(value) is bool and type(result[field]) is not bool:
            return False
        if type(value) is list and type(result[field]) is not list:
            return False
    return True


def _valid_reference(reference: object) -> bool:
    return (
        type(reference) is dict
        and set(reference) == _REFERENCE
        and type(reference.get("reference_id")) is str
        and _REF_ID.fullmatch(reference["reference_id"]) is not None
        and type(reference.get("record_id")) is str
        and re.fullmatch(r"SYNTH_APPROVAL_[A-Z0-9_]{1,32}", reference["record_id"]) is not None
        and type(reference.get("sequence")) is int
        and 0 <= reference["sequence"] <= 2
        and type(reference.get("head_hash")) is str
        and _HASH.fullmatch(reference["head_hash"]) is not None
        and type(reference.get("revocation_tombstone")) is bool
        and type(reference.get("generation")) is int
        and 1 <= reference["generation"] <= 1000000
    )


def _valid_storage(st: object) -> bool:
    return (
        type(st) is dict and set(st) == _STORAGE
        and all(type(st[k]) is str and st[k] in _SIM_STATES
                for k in ("write_state", "restore_state", "reference_read_state"))
        and type(st["clock_state"]) is str
        and st["clock_state"] in _CLOCK_STATES
        and type(st["concurrent_writer_detected"]) is bool
    )


def build_synthetic_reference_fixture(
    history_bundle: object, generation: int = 1,
) -> dict[str, object] | None:
    """Make an explicitly untrusted synthetic baseline for tests only."""
    if type(generation) is not int or not 1 <= generation <= 1000000:
        return None
    try:
        result = audit_synthetic_history_checkpoint(history_bundle)
        if not _valid_history_denial(result):
            return None
        checkpoint = history_bundle["checkpoint"]
        lifecycle = history_bundle["lifecycle"]
        return {
            "reference_id": "SYNTHETIC_REFERENCE_TEST",
            "record_id": checkpoint["record_id"],
            "sequence": checkpoint["sequence"],
            "head_hash": checkpoint["head_hash"],
            "revocation_tombstone": any(
                event["event_type"] == "REVOKED"
                for event in lifecycle["events"]
            ),
            "generation": generation,
        }
    except (KeyError, TypeError, ValueError, IndexError):
        return None


def audit_synthetic_reference_and_failures(payload: object) -> dict[str, object]:
    """Compare simulated reference with D5-23; deny on all outcomes."""
    rejected = _result("ANCHOR_INPUT_REJECTED_FAIL_CLOSED")
    if (type(payload) is not dict or set(payload) != _BUNDLE
            or payload.get("origin") != "SYNTHETIC_ONLY"
            or type(payload.get("schema_version")) is not int
            or payload["schema_version"] != 1
            or type(payload.get("minimum_generation")) is not int
            or not 1 <= payload["minimum_generation"] <= 1000000
            or not _valid_reference(payload.get("reference"))
            or not _valid_storage(payload.get("simulated_storage"))):
        return rejected
    reference = payload["reference"]
    st = payload["simulated_storage"]
    if (any(st[k] != _CONFIRMED for k in
            ("write_state", "restore_state", "reference_read_state"))):
        return _result("ANCHOR_STORAGE_UNCERTAIN_NO_GO")
    if st["clock_state"] != _CLOCK_OK or st["concurrent_writer_detected"]:
        return _result("ANCHOR_CONTINUITY_UNTRUSTED_NO_GO")
    if reference["generation"] < payload["minimum_generation"]:
        return _result("ANCHOR_REFERENCE_GENERATION_ROLLBACK_NO_GO")
    try:
        hb = payload["history_bundle"]
        history = audit_synthetic_history_checkpoint(hb)
        if not _valid_history_denial(history):
            return _result("ANCHOR_HISTORY_BLOCKED_NO_GO",
                           history.get("status", "INVALID")
                           if type(history) is dict
                           and type(history.get("status")) is str else "INVALID")
        latest = hb["checkpoint"]
        lifecycle = hb["lifecycle"]
        status = history["status"]
        if reference["record_id"] != lifecycle["record"]["record_id"]:
            return _result("ANCHOR_RECORD_MISMATCH_NO_GO", status)
        if reference["sequence"] > latest["sequence"]:
            return _result("ANCHOR_HISTORY_ROLLBACK_NO_GO", status)
        if reference["sequence"] < latest["sequence"]:
            return _result("ANCHOR_REFERENCE_STALE_NO_GO", status)
        revoked_now = any(
            event["event_type"] == "REVOKED" for event in lifecycle["events"]
        )
        if reference["revocation_tombstone"] != revoked_now:
            return _result("ANCHOR_REVOCATION_MISMATCH_NO_GO", status)
        if reference["head_hash"] != latest["head_hash"]:
            return _result("ANCHOR_HEAD_MISMATCH_NO_GO", status)
        # This cannot prove actual anchor independence, storage or authenticity.
        return _result("ANCHOR_SYNTHETIC_REFERENCE_MATCH_NO_GO", status)
    except Exception:
        return rejected
