"""P0-01 D5-8: offline stop-state restoration and corruption fail-close.

Pure in-memory simulation. No file/database I/O, signatures, broker, or orders.
A structurally valid snapshot is NOT evidence of authentic persistent state.
"""
from __future__ import annotations
from datetime import date

FIELDS = frozenset(("origin", "schema_version", "trading_day_start_ny_date",
                    "daily_stop_latched", "last_status", "sequence"))
STATUSES = frozenset(("DAILY_STOP", "DAILY_STOP_LATCHED", "NEXT_DAY_REVIEW_PENDING",
                      "NEXT_DAY_REVIEW_REQUIRED", "OFFLINE_REVIEW_ONLY_NEVER_AUTO_RESUME",
                      "HARD_STOP_DD5", "REVIEW_REQUIRED", "SYNTHETIC_MONITORING_ONLY",
                      "RISK_REVIEW_REQUIRED"))
STOP_STATUSES = frozenset(("DAILY_STOP", "DAILY_STOP_LATCHED",
                           "NEXT_DAY_REVIEW_PENDING", "NEXT_DAY_REVIEW_REQUIRED",
                           "OFFLINE_REVIEW_ONLY_NEVER_AUTO_RESUME", "HARD_STOP_DD5",
                           "REVIEW_REQUIRED", "RISK_REVIEW_REQUIRED"))


def restore_synthetic_stop_state(snapshot: object, expected_day: object,
                                 minimum_sequence: object) -> dict[str, object]:
    """Reject malformed, stale, future-day, incompatible, or contradictory state.

    Even a valid non-stopped synthetic snapshot cannot authorize live trading.
    """
    status = "RESTORE_REJECTED_FAIL_CLOSED"
    latch = True
    try:
        if (type(snapshot) is dict and set(snapshot) == FIELDS
                and snapshot["origin"] == "SYNTHETIC_ONLY"
                and type(snapshot["schema_version"]) is int
                and snapshot["schema_version"] == 1
                and type(snapshot["daily_stop_latched"]) is bool
                and type(snapshot["last_status"]) is str
                and snapshot["last_status"] in STATUSES
                and type(snapshot["sequence"]) is int
                and 0 <= snapshot["sequence"] <= 1000000000
                and type(minimum_sequence) is int
                and 0 <= minimum_sequence <= 1000000000
                and snapshot["sequence"] >= minimum_sequence
                and type(expected_day) is str
                and type(snapshot["trading_day_start_ny_date"]) is str):
            day = snapshot["trading_day_start_ny_date"]
            if (len(day) == len(expected_day) == 10
                    and date.fromisoformat(day).isoformat() == day
                    and date.fromisoformat(expected_day).isoformat() == expected_day
                    and day <= expected_day):
                stopped = snapshot["daily_stop_latched"]
                contradiction = (not stopped and snapshot["last_status"] in STOP_STATUSES)
                if not contradiction:
                    # A synthetic restart cannot clear a stop, even on a new day.
                    latch = stopped
                    status = ("RESTORED_STOP_STILL_LATCHED" if stopped
                              else "RESTORED_SYNTHETIC_ONLY_NO_RUNTIME_AUTHORITY")
    except (ValueError, TypeError, OverflowError, KeyError):
        pass
    return {"status": status, "daily_stop_latched": latch,
            "broker_verified": False, "production_usable": False,
            "orders_generated": False, "terminal_execution_approved": False,
            "forward_trading_enabled": False, "phase_1": "BLOCKED"}
