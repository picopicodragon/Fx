"""D5-22: offline synthetic approval-state transitions, never runtime authority.

All timestamps and lifecycle events are caller-provided UNTRUSTED synthetic data.
No identity verification, durable anti-replay storage, filesystem/clock/MT4/broker
access, order submission, genuine approval, or stop-release functionality.
"""
from __future__ import annotations

from datetime import datetime, timezone
import re

from scripts.p0_01_d5_21_authority_audit import (
    audit_offline_authority_separation,
)

_ACTIONS = frozenset((
    "VISUAL_REVIEW", "MT4_LAUNCH", "ACCOUNT_LOGIN", "READ_ONLY_QUERY",
    "EA_EXECUTION", "ORDER_ACTION", "STOP_RELEASE", "LIVE_TRADING",
))
_CAUSES = frozenset((
    "NONE", "DD4", "DD5", "DAILY_LIMIT", "COMMUNICATION",
    "CLOCK_FAULT", "MANUAL_HALT",
))
_TOP_KEYS = frozenset((
    "origin", "schema_version", "record", "events", "request", "as_of_utc",
))
_SCOPED = frozenset(("action", "account_scope", "terminal_scope", "stop_cause"))
_RECORD_KEYS = frozenset((
    "record_id", *_SCOPED, "issued_at_utc", "expires_at_utc",
))
_EVENT_KEYS = frozenset((
    "event_type", "sequence", "occurred_at_utc", "record_id",
))
_EVENTS = ("PROPOSED", "APPROVAL_CLAIMED", "REVOKED")
_TIME = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z")
_IDENTIFIER = re.compile(r"SYNTH_APPROVAL_[A-Z0-9_]{1,32}\Z")
_ACCOUNT = re.compile(r"SYNTHETIC_ACCOUNT_[A-Z0-9_]{1,24}\Z")
_TERMINAL = re.compile(r"SYNTHETIC_TERMINAL_[A-Z0-9_]{1,24}\Z")
_MAX_DURATION_SECONDS = 3600  # synthetic fixture bound, NOT a live policy
_AUTHORITY_DENIAL_STATUSES = frozenset((
    "AUTHORITY_INPUT_REJECTED_FAIL_CLOSED",
    "EVIDENCE_OR_STOP_BLOCKED_NO_GO",
    "STOP_RELEASE_CLAIM_DENIED_NO_GO",
    "UNTRUSTED_APPROVAL_CLAIM_DENIED_NO_GO",
    "EXPLICIT_APPROVAL_NOT_PRESENT_NO_GO",
))


def _denied(
    status: str, *, state: str = "INVALID", event_count: int = 0,
) -> dict[str, object]:
    return {
        "status": status,
        "lifecycle_state": state,
        "events_reviewed": event_count,
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


def _parse_time(value: object) -> datetime | None:
    if type(value) is not str or _TIME.fullmatch(value) is None:
        return None
    try:
        dt = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc,
        )
        if dt.year < 2000 or dt.strftime("%Y-%m-%dT%H:%M:%SZ") != value:
            return None
        return dt
    except (ValueError, OverflowError):
        return None


def _scopes_valid(value: object) -> bool:
    if type(value) is not dict:
        return False
    if (type(value.get("action")) is not str
            or value["action"] not in _ACTIONS
            or type(value.get("account_scope")) is not str
            or _ACCOUNT.fullmatch(value["account_scope"]) is None
            or type(value.get("terminal_scope")) is not str
            or _TERMINAL.fullmatch(value["terminal_scope"]) is None
            or type(value.get("stop_cause")) is not str
            or value["stop_cause"] not in _CAUSES):
        return False
    return ((value["action"] == "STOP_RELEASE"
             and value["stop_cause"] != "NONE")
            or (value["action"] != "STOP_RELEASE"
                and value["stop_cause"] == "NONE"))


def audit_synthetic_approval_lifecycle(payload: object) -> dict[str, object]:
    """Inspect untrusted simulated PROPOSED -> CLAIMED -> REVOKED events.

    The EXPIRED condition is derived from caller-supplied as_of_utc, not a clock.
    A seemingly current claim remains unauthenticated and non-authorizing.
    """
    rejected = _denied("LIFECYCLE_INPUT_REJECTED_FAIL_CLOSED")
    if (type(payload) is not dict or set(payload) != _TOP_KEYS
            or payload.get("origin") != "SYNTHETIC_ONLY"
            or type(payload.get("schema_version")) is not int
            or payload["schema_version"] != 1):
        return rejected
    record = payload["record"]
    request = payload["request"]
    events = payload["events"]
    if (type(record) is not dict or set(record) != _RECORD_KEYS
            or type(request) is not dict or set(request) != _SCOPED
            or not _scopes_valid(record) or not _scopes_valid(request)
            or type(record.get("record_id")) is not str
            or _IDENTIFIER.fullmatch(record["record_id"]) is None
            or type(events) is not list or not 1 <= len(events) <= 3):
        return rejected
    start = _parse_time(record["issued_at_utc"])
    expiry = _parse_time(record["expires_at_utc"])
    as_of = _parse_time(payload["as_of_utc"])
    if (start is None or expiry is None or as_of is None
            or not start < expiry
            or not 0 < (expiry - start).total_seconds() <= _MAX_DURATION_SECONDS
            or as_of < start):
        return rejected

    state = "PROPOSED"
    previous_time = start
    for index, event in enumerate(events):
        if type(event) is not dict or set(event) != _EVENT_KEYS:
            return rejected
        occurred = _parse_time(event["occurred_at_utc"])
        if (type(event.get("sequence")) is not int
                or event["sequence"] != index
                or type(event.get("event_type")) is not str
                or event["event_type"] not in _EVENTS
                or type(event.get("record_id")) is not str
                or event["record_id"] != record["record_id"]
                or occurred is None or occurred < previous_time
                or occurred > as_of):
            return rejected
        kind = event["event_type"]
        if index == 0:
            if kind != "PROPOSED" or occurred != start:
                return rejected
        elif kind == "APPROVAL_CLAIMED":
            if state != "PROPOSED" or occurred >= expiry:
                return rejected
            state = "CLAIMED_NOT_VERIFIED"
        elif kind == "REVOKED":
            if state not in ("PROPOSED", "CLAIMED_NOT_VERIFIED"):
                return rejected
            state = "REVOKED"
        else:
            return rejected
        previous_time = occurred

    count = len(events)
    if state == "REVOKED":
        return _denied("LIFECYCLE_REVOKED_NO_GO",
                       state="REVOKED", event_count=count)
    if as_of >= expiry:
        return _denied("LIFECYCLE_EXPIRED_NO_GO",
                       state="EXPIRED", event_count=count)
    if any(record[key] != request[key] for key in _SCOPED):
        return _denied("LIFECYCLE_SCOPE_MISMATCH_NO_GO",
                       state="SCOPE_MISMATCH", event_count=count)
    if state == "CLAIMED_NOT_VERIFIED":
        return _denied("LIFECYCLE_CLAIMED_UNTRUSTED_NO_GO",
                       state=state, event_count=count)
    return _denied("LIFECYCLE_PROPOSED_NO_GO",
                   state="PROPOSED", event_count=count)


def audit_synthetic_lifecycle_with_authority(
    integrated_fixture: object, lifecycle_fixture: object,
) -> dict[str, object]:
    """Cross-check against D5-21, then enforce a strictly denial-only result.

    A lifecycle is NOT an authority token. This adapter does not issue grants.
    """
    lifecycle = audit_synthetic_approval_lifecycle(lifecycle_fixture)
    invalid = _denied("LIFECYCLE_AND_AUTHORITY_REJECTED_FAIL_CLOSED")
    invalid["authority_status"] = "NOT_EVALUATED"
    invalid["lifecycle_status"] = lifecycle["status"]
    if lifecycle["status"] == "LIFECYCLE_INPUT_REJECTED_FAIL_CLOSED":
        return invalid
    try:
        request = lifecycle_fixture["request"]
        claim = {
            "origin": "SYNTHETIC_ONLY",
            "schema_version": 1,
            "requested_action": request["action"],
            "claimed_human_approval": (
                lifecycle["lifecycle_state"] == "CLAIMED_NOT_VERIFIED"
            ),
            "claimed_safety_review_passed": False,
            "claimed_stop_release": False,
            "approval_reference": None,
        }
        # D5-21 always recomputes the evidence and stop gate from inputs.
        authority = audit_offline_authority_separation(
            integrated_fixture, claim,
        )
        if (type(authority) is not dict
                or authority.get("status") not in _AUTHORITY_DENIAL_STATUSES
                or authority.get("runtime_go_no_go") != "NO_GO"
                or authority.get("phase_1") != "BLOCKED"
                or authority.get("safety_hold_latched") is not True
                or authority.get("approval_verified") is not False
                or authority.get("action_authorized") is not False
                or authority.get("stop_release_authorized") is not False
                or authority.get("ea_execution_authorized") is not False
                or authority.get("order_authorized") is not False
                or authority.get("effective_approved_actions") != []
                or authority.get("verified_values", "MISSING") is not None
                or any(authority.get(k) is not False for k in (
                    "broker_verified", "production_usable",
                    "read_only_ex4_execution_approved",
                    "terminal_execution_approved", "orders_generated",
                    "forward_trading_enabled",
                ))):
            return invalid
        result = _denied(
            "LIFECYCLE_AND_AUTHORITY_NO_GO",
            state=lifecycle["lifecycle_state"],
            event_count=lifecycle["events_reviewed"],
        )
        result["lifecycle_status"] = lifecycle["status"]
        result["authority_status"] = authority["status"]
        return result
    except Exception:
        return invalid
