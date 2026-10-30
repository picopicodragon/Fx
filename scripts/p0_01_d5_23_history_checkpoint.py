"""D5-23: pure synthetic approval-history chain and checkpoint comparison.

A SHA-256 hash is an integrity *comparison*, NOT authentication. The record,
journal, checkpoint and UTC timestamps are ALL caller-supplied untrusted data.
There is no disk storage, trusted anchor, OS clock, MT4, broker, or order path.
"""
from __future__ import annotations

import hashlib
import json
import re

from scripts.p0_01_d5_22_approval_lifecycle import (
    audit_synthetic_approval_lifecycle,
    audit_synthetic_lifecycle_with_authority,
)

_BUNDLE_KEYS = frozenset((
    "origin", "schema_version", "lifecycle", "journal", "checkpoint",
    "integrated_fixture",
))
_JOURNAL_KEYS = frozenset(("sequence", "previous_hash", "event_hash"))
_CHECKPOINT_KEYS = frozenset(("record_id", "sequence", "head_hash"))
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_ZERO = "0" * 64
_DOMAIN = "FX_D5_23_UNTRUSTED_SYNTHETIC_HISTORY_V1"
_LIFECYCLE_ALLOWED = frozenset((
    "LIFECYCLE_PROPOSED_NO_GO",
    "LIFECYCLE_CLAIMED_UNTRUSTED_NO_GO",
    "LIFECYCLE_REVOKED_NO_GO",
    "LIFECYCLE_EXPIRED_NO_GO",
    "LIFECYCLE_SCOPE_MISMATCH_NO_GO",
))
_AUTHORITY_ALLOWED = frozenset((
    "AUTHORITY_INPUT_REJECTED_FAIL_CLOSED",
    "EVIDENCE_OR_STOP_BLOCKED_NO_GO",
    "STOP_RELEASE_CLAIM_DENIED_NO_GO",
    "UNTRUSTED_APPROVAL_CLAIM_DENIED_NO_GO",
    "EXPLICIT_APPROVAL_NOT_PRESENT_NO_GO",
))


def _closed(
    status: str, *, lifecycle_status: str = "NOT_EVALUATED",
    downstream_status: str = "NOT_EVALUATED", events_checked: int = 0,
) -> dict[str, object]:
    return {
        "status": status,
        "lifecycle_status": lifecycle_status,
        "downstream_status": downstream_status,
        "events_checked": events_checked,
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


def _closed_downstream(value: object) -> bool:
    if type(value) is not dict or value.get("status") != "LIFECYCLE_AND_AUTHORITY_NO_GO":
        return False
    required = {
        "approval_verified": False,
        "action_authorized": False,
        "ea_execution_authorized": False,
        "order_authorized": False,
        "stop_release_authorized": False,
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
        "effective_approved_actions": [],
    }
    for k, expected in required.items():
        if k not in value or value[k] != expected:
            return False
        if type(expected) is bool and type(value[k]) is not bool:
            return False
        if type(expected) is list and type(value[k]) is not list:
            return False
    if value.get("authority_status") not in _AUTHORITY_ALLOWED:
        return False
    if value.get("lifecycle_status") not in _LIFECYCLE_ALLOWED:
        return False
    return True


def build_synthetic_history_chain(lifecycle: object) -> list[dict[str, object]] | None:
    """Make test-only hash fixtures, WITHOUT signing or trustworthy persistence."""
    try:
        check = audit_synthetic_approval_lifecycle(lifecycle)
        if check["status"] not in _LIFECYCLE_ALLOWED:
            return None
        record = lifecycle["record"]
        events = lifecycle["events"]
        previous = _ZERO
        chain: list[dict[str, object]] = []
        for event in events:
            canonical = json.dumps(
                {
                    "domain": _DOMAIN,
                    "record": record,
                    "event": event,
                    "previous_hash": previous,
                },
                sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                allow_nan=False,
            ).encode("utf-8")
            digest = hashlib.sha256(canonical).hexdigest()
            chain.append({
                "sequence": event["sequence"], "previous_hash": previous,
                "event_hash": digest,
            })
            previous = digest
        return chain
    except (TypeError, KeyError, ValueError, OverflowError, UnicodeError):
        return None


def audit_synthetic_history_checkpoint(bundle: object) -> dict[str, object]:
    """Fail closed on replay/rollback against an explicitly supplied checkpoint.

    NOT guaranteed anti-replay: a forger can replace *both* journal and
    checkpoint. No persistent or independently trusted reference exists.
    """
    rejected = _closed("HISTORY_INPUT_REJECTED_FAIL_CLOSED")
    if (type(bundle) is not dict or set(bundle) != _BUNDLE_KEYS
            or bundle.get("origin") != "SYNTHETIC_ONLY"
            or type(bundle.get("schema_version")) is not int
            or bundle["schema_version"] != 1):
        return rejected

    lifecycle = bundle["lifecycle"]
    chain = build_synthetic_history_chain(lifecycle)
    if chain is None:
        return _closed("HISTORY_LIFECYCLE_REJECTED_FAIL_CLOSED")
    lifecycle_status = audit_synthetic_approval_lifecycle(lifecycle)["status"]
    journal = bundle["journal"]
    checkpoint = bundle["checkpoint"]
    if (type(journal) is not list or not 1 <= len(journal) <= 3
            or type(checkpoint) is not dict
            or set(checkpoint) != _CHECKPOINT_KEYS
            or type(checkpoint.get("record_id")) is not str
            or type(checkpoint.get("sequence")) is not int
            or checkpoint["sequence"] < 0
            or type(checkpoint.get("head_hash")) is not str
            or _HASH.fullmatch(checkpoint["head_hash"]) is None):
        return rejected
    count = len(chain)
    if len(journal) != count:
        return _closed("HISTORY_CHAIN_MISMATCH_NO_GO",
                       lifecycle_status=lifecycle_status)
    for idx, actual in enumerate(journal):
        if (type(actual) is not dict or set(actual) != _JOURNAL_KEYS
                or type(actual.get("sequence")) is not int
                or type(actual.get("previous_hash")) is not str
                or type(actual.get("event_hash")) is not str
                or _HASH.fullmatch(actual["previous_hash"]) is None
                or _HASH.fullmatch(actual["event_hash"]) is None
                or actual != chain[idx]):
            return _closed("HISTORY_CHAIN_MISMATCH_NO_GO",
                           lifecycle_status=lifecycle_status,
                           events_checked=idx)
    if checkpoint["record_id"] != lifecycle["record"]["record_id"]:
        return _closed("HISTORY_CHECKPOINT_MISMATCH_NO_GO",
                       lifecycle_status=lifecycle_status, events_checked=count)
    if checkpoint["sequence"] >= count:
        return _closed("HISTORY_ROLLBACK_DETECTED_NO_GO",
                       lifecycle_status=lifecycle_status, events_checked=count)
    anchor = chain[checkpoint["sequence"]]
    if checkpoint["head_hash"] != anchor["event_hash"]:
        return _closed("HISTORY_CHECKPOINT_MISMATCH_NO_GO",
                       lifecycle_status=lifecycle_status, events_checked=count)
    if checkpoint["sequence"] != count - 1:
        return _closed("HISTORY_CHECKPOINT_STALE_NO_GO",
                       lifecycle_status=lifecycle_status, events_checked=count)
    try:
        downstream = audit_synthetic_lifecycle_with_authority(
            bundle["integrated_fixture"], lifecycle,
        )
        if (not _closed_downstream(downstream)
                or downstream.get("lifecycle_status") != lifecycle_status):
            return _closed("HISTORY_DOWNSTREAM_REJECTED_FAIL_CLOSED",
                           lifecycle_status=lifecycle_status, events_checked=count)
        return _closed(
            "HISTORY_SYNTHETIC_CHAIN_CONSISTENT_NO_GO",
            lifecycle_status=lifecycle_status,
            downstream_status=downstream["authority_status"],
            events_checked=count,
        )
    except Exception:
        return _closed("HISTORY_DOWNSTREAM_REJECTED_FAIL_CLOSED",
                       lifecycle_status=lifecycle_status, events_checked=count)
