"""D5-19: pure offline combination of synthetic evidence and stop-state gates.

Does not open files, read clocks, query MT4/brokers, authenticate, or place orders.
Even fully consistent synthetic fixtures never grant runtime authority.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from scripts.p0_01_d5_7_daily_latch import evaluate_daily_latch
from scripts.p0_01_d5_10_recovery_gate import evaluate_synthetic_recovery_gate
from scripts.p0_01_d5_18_evidence_gate import (
    evaluate_d517_evidence_ledger, evaluate_synthetic_evidence_records,
)

_INPUT_FIELDS = frozenset((
    "origin", "schema_version", "evidence_mode", "evidence",
    "daily_fixture", "snapshots", "restored_snapshot",
    "expected_day", "minimum_sequence",
))
_EVIDENCE_MODES = frozenset(("D517_LEDGER", "SYNTHETIC_RECORDS"))
_EVIDENCE_STATUSES = frozenset((
    "D517_REPORTS_NOT_RECONCILED_NO_GO",
    "SYNTHETIC_INTERNALLY_CONSISTENT_NO_GO",
    "LEDGER_REJECTED_FAIL_CLOSED",
    "SYNTHETIC_INPUT_REJECTED_FAIL_CLOSED",
    "ACCOUNT_SCOPE_MISMATCH_NO_GO",
    "EVIDENCE_CONFLICT_NO_GO",
    "EVIDENCE_INSUFFICIENT_NO_GO",
))
_DAILY_STATUSES = frozenset((
    "SYNTHETIC_MONITORING_ONLY", "RISK_REVIEW_REQUIRED",
    "REVIEW_REQUIRED", "HARD_STOP_DD5", "DAILY_STOP",
    "DAILY_STOP_LATCHED", "NEXT_DAY_REVIEW_PENDING",
    "NEXT_DAY_REVIEW_REQUIRED", "OFFLINE_REVIEW_ONLY_NEVER_AUTO_RESUME",
))
_RECOVERY_STATUSES = frozenset((
    "INTEGRATED_CLEAN_NEVER_AUTHORIZED",
    "INTEGRATED_STOP_LATCHED_SYNTHETIC_ONLY",
    "INTEGRATION_REJECTED_FAIL_CLOSED",
))
_DENY_FLAGS = (
    "broker_verified", "production_usable", "orders_generated",
    "terminal_execution_approved", "forward_trading_enabled",
)


def _iso_day(value: object) -> bool:
    if type(value) is not str or len(value) != 10:
        return False
    try:
        return date.fromisoformat(value).isoformat() == value
    except (TypeError, ValueError, OverflowError):
        return False


def _coherent_evidence_matches_daily_instant(payload: dict[str, object]) -> bool:
    """Only compare already validated synthetic timestamps; do not read clocks."""
    try:
        observed = payload["evidence"]["records"][0]["observed_at_utc"]
        clock = datetime.fromisoformat(payload["daily_fixture"]["utc_timestamp"])
        if clock.tzinfo is None or clock.utcoffset() is None or clock.microsecond:
            return False
        return (clock.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                == observed)
    except (TypeError, ValueError, KeyError, IndexError, OverflowError):
        return False


def _safe_result(result: object, allowed: frozenset[str]) -> bool:
    if type(result) is not dict or result.get("status") not in allowed:
        return False
    if (result.get("phase_1") != "BLOCKED"
            or any(result.get(k) is not False for k in _DENY_FLAGS)):
        return False
    if "daily_stop_latched" in result:
        return type(result["daily_stop_latched"]) is bool
    return (result.get("runtime_go_no_go") == "NO_GO"
            and result.get("verified_values", "MISSING") is None
            and result.get("read_only_ex4_execution_approved") is False)


def _result(
    status: str, *,
    evidence_status: str = "NOT_EVALUATED",
    daily_status: str = "NOT_EVALUATED",
    recovery_status: str = "NOT_EVALUATED",
    daily_stop_latched: bool = True,
) -> dict[str, object]:
    return {
        "status": status,
        "evidence_status": evidence_status,
        "daily_status": daily_status,
        "recovery_status": recovery_status,
        "daily_stop_latched": daily_stop_latched,
        "safety_hold_latched": True,  # Synthetic inputs cannot release policy hold.
        "runtime_go_no_go": "NO_GO",
        "verified_values": None,
        "broker_verified": False,
        "production_usable": False,
        "orders_generated": False,
        "read_only_ex4_execution_approved": False,
        "terminal_execution_approved": False,
        "forward_trading_enabled": False,
        "phase_1": "BLOCKED",
    }


def evaluate_offline_integrated_no_go(payload: object) -> dict[str, object]:
    """Combine D5-7, D5-10 and D5-18 without writing or authorizing.

    The stop chain has no account identity field. Matching records cannot
    prove that the evidence and stop state belong to the same real account.
    """
    rejected = _result("INTEGRATED_INPUT_REJECTED_FAIL_CLOSED")
    if (type(payload) is not dict or set(payload) != _INPUT_FIELDS
            or payload.get("origin") != "SYNTHETIC_ONLY"
            or type(payload.get("schema_version")) is not int
            or payload["schema_version"] != 1
            or type(payload.get("evidence_mode")) is not str
            or payload["evidence_mode"] not in _EVIDENCE_MODES
            or not _iso_day(payload.get("expected_day"))):
        return rejected
    daily_fixture = payload["daily_fixture"]
    if (type(daily_fixture) is not dict
            or not _iso_day(daily_fixture.get("previous_day_label"))
            or daily_fixture["previous_day_label"] > payload["expected_day"]):
        return rejected
    try:
        if payload["evidence_mode"] == "D517_LEDGER":
            evidence = evaluate_d517_evidence_ledger(payload["evidence"])
        else:
            evidence = evaluate_synthetic_evidence_records(payload["evidence"])
        daily = evaluate_daily_latch(daily_fixture)
        recovery = evaluate_synthetic_recovery_gate(
            payload["snapshots"], payload["restored_snapshot"],
            payload["expected_day"], payload["minimum_sequence"],
        )
        if (not _safe_result(evidence, _EVIDENCE_STATUSES)
                or not _safe_result(daily, _DAILY_STATUSES)
                or not _safe_result(recovery, _RECOVERY_STATUSES)
                or daily.get("trading_day_start_ny_date") != payload["expected_day"]):
            return rejected
        evidence_status, daily_status, recovery_status = (
            evidence["status"], daily["status"], recovery["status"],
        )
        daily_latched = daily["daily_stop_latched"]
        recovered_latched = recovery["daily_stop_latched"]
        base = {
            "evidence_status": evidence_status,
            "daily_status": daily_status,
            "recovery_status": recovery_status,
        }
        if (evidence_status.endswith("REJECTED_FAIL_CLOSED")
                or daily_status == "REVIEW_REQUIRED"
                or recovery_status == "INTEGRATION_REJECTED_FAIL_CLOSED"):
            return _result("INTEGRATED_COMPONENT_REJECTED_FAIL_CLOSED", **base)
        # D5-10 permits a structurally valid earlier-day snapshot.
        # At this integration boundary, an old snapshot is not "current".
        latest = payload["snapshots"][-1]
        if (type(latest) is not dict
                or latest.get("trading_day_start_ny_date")
                != payload["expected_day"]):
            return _result("INTEGRATED_STALE_STOP_RECORD_FAIL_CLOSED", **base)
        if daily_latched != recovered_latched:
            return _result("INTEGRATED_STOP_DISAGREEMENT_FAIL_CLOSED", **base)
        if daily_latched or recovered_latched or daily_status != "SYNTHETIC_MONITORING_ONLY":
            return _result(
                "INTEGRATED_STOP_OR_REVIEW_BLOCKED_NO_GO",
                daily_stop_latched=daily_latched or recovered_latched,
                **base,
            )
        if evidence_status != "SYNTHETIC_INTERNALLY_CONSISTENT_NO_GO":
            return _result(
                "INTEGRATED_EVIDENCE_BLOCKED_NO_GO",
                daily_stop_latched=False, **base,
            )
        if not _coherent_evidence_matches_daily_instant(payload):
            return _result(
                "INTEGRATED_EVIDENCE_TIME_MISMATCH_NO_GO",
                daily_stop_latched=False, **base,
            )
        # Even this "clean" synthetic scenario NEVER authorizes execution.
        return _result(
            "INTEGRATED_SYNTHETIC_COHERENT_NEVER_AUTHORIZED",
            daily_stop_latched=False, **base,
        )
    except Exception:
        return rejected
