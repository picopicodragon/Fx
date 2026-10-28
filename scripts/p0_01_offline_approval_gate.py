"""P0-01 D4-2: irreversible non-authorizing boundary for offline reports.

Offline inputs can NEVER grant broker or execution permissions.
Pure Python: no IO, terminals, external services, orders, or persistence.
"""
from __future__ import annotations

from scripts.p0_01_offline_five_field_mock import (
    report_safe_status_codes_only, PASS as SYNTHETIC_PASS
)
from scripts.p0_01_offline_provenance_guard import (
    check_candidate, PENDING as CANDIDATE_PENDING
)

REVIEW = "REVIEW_REQUIRED"
PENDING = "PENDING_EVIDENCE"
BLOCKED = "BLOCKED"
ALLOWED_STAGES = frozenset(("SYNTHETIC", "MANUAL_CANDIDATE"))
REPORT_KEYS = frozenset(("status", "broker_verified", "production_usable",
                         "orders_generated", "terminal_execution_approved",
                         "forward_trading_enabled", "phase_1"))


def deny_all(stage: object, payload: object, reference_time: object = None) -> dict[str, object]:
    """Return fixed status/flags. Caller-supplied approvals are never consumed."""
    status = REVIEW
    try:
        if type(stage) is str and stage in ALLOWED_STAGES:
            if stage == "SYNTHETIC":
                result = report_safe_status_codes_only(payload)
                status = PENDING if result.get("status") == SYNTHETIC_PASS else REVIEW
            else:
                result = check_candidate(payload, reference_time)
                status = PENDING if result.get("status") == CANDIDATE_PENDING else REVIEW
    except Exception:
        status = REVIEW
    return {
        "status": status,
        "broker_verified": False,
        "production_usable": False,
        "orders_generated": False,
        "terminal_execution_approved": False,
        "forward_trading_enabled": False,
        "phase_1": BLOCKED,
    }


def invariant_holds(result: object) -> bool:
    """Only exact, non-authorizing report schemas meet the D4-2 contract."""
    try:
        return (
            type(result) is dict
            and set(result) == REPORT_KEYS
            and type(result["status"]) is str
            and result["status"] in (REVIEW, PENDING)
            and all(result[key] is False for key in (
                "broker_verified", "production_usable", "orders_generated",
                "terminal_execution_approved", "forward_trading_enabled"))
            and result["phase_1"] == BLOCKED
        )
    except Exception:
        return False
