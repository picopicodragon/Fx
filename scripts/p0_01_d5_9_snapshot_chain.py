"""P0-01 D5-9: pure in-memory synthetic stop snapshot chain audit.

Not durable storage, cryptographic authentication, or broker/trading authorization.
"""
from __future__ import annotations

from datetime import date
from scripts.p0_01_d5_8_stop_restore import (
    FIELDS, STATUSES, STOP_STATUSES, restore_synthetic_stop_state
)

def audit_synthetic_snapshot_chain(snapshots: object, expected_day: object) -> dict[str, object]:
    status = "CHAIN_REJECTED_FAIL_CLOSED"
    stop_latched = True
    try:
        if (type(snapshots) is list and 1 <= len(snapshots) <= 100
                and type(expected_day) is str and len(expected_day) == 10
                and date.fromisoformat(expected_day).isoformat() == expected_day):
            valid = True
            previous = None
            for current in snapshots:
                if (type(current) is not dict or set(current) != FIELDS
                        or type(current["sequence"]) is not int
                        or type(current["trading_day_start_ny_date"]) is not str):
                    valid = False
                    break
                restored = restore_synthetic_stop_state(
                    current, expected_day, current["sequence"])
                if restored["status"] == "RESTORE_REJECTED_FAIL_CLOSED":
                    valid = False
                    break
                if previous is not None:
                    # No sequence gaps, duplicates or rollbacks.
                    if current["sequence"] != previous["sequence"] + 1:
                        valid = False
                        break
                    if current["trading_day_start_ny_date"] < previous["trading_day_start_ny_date"]:
                        valid = False
                        break
                    # A stop cannot disappear solely from a later snapshot.
                    if previous["daily_stop_latched"] and not current["daily_stop_latched"]:
                        valid = False
                        break
                    # Hard stop cannot downgrade into a routine status.
                    if previous["last_status"] == "HARD_STOP_DD5" and current["last_status"] != "HARD_STOP_DD5":
                        valid = False
                        break
                previous = current
            if valid:
                stop_latched = any(item["daily_stop_latched"] for item in snapshots)
                status = ("CHAIN_CONSISTENT_STOP_LATCHED_SYNTHETIC_ONLY"
                          if stop_latched else "CHAIN_CONSISTENT_NEVER_AUTHORIZED")
    except (ValueError, TypeError, OverflowError, KeyError, ArithmeticError):
        status = "CHAIN_REJECTED_FAIL_CLOSED"
    return {"status": status, "daily_stop_latched": stop_latched,
            "broker_verified": False, "production_usable": False,
            "orders_generated": False, "terminal_execution_approved": False,
            "forward_trading_enabled": False, "phase_1": "BLOCKED"}
