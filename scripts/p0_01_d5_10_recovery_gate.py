"""D5-10: in-memory synthetic integration gate for restore + chain audit.

No files, clock, broker, terminal, order authority, or automatic reactivation.
"""
from __future__ import annotations

from scripts.p0_01_d5_8_stop_restore import restore_synthetic_stop_state
from scripts.p0_01_d5_9_snapshot_chain import audit_synthetic_snapshot_chain

RESTORE_OK = frozenset((
    "RESTORED_STOP_STILL_LATCHED",
    "RESTORED_SYNTHETIC_ONLY_NO_RUNTIME_AUTHORITY",
))
CHAIN_OK = frozenset((
    "CHAIN_CONSISTENT_STOP_LATCHED_SYNTHETIC_ONLY",
    "CHAIN_CONSISTENT_NEVER_AUTHORIZED",
))


def evaluate_synthetic_recovery_gate(
    snapshots: object, restored_snapshot: object,
    expected_day: object, minimum_sequence: object,
) -> dict[str, object]:
    """Require exact latest record, valid restore, and valid history.

    All outcomes deny trading. Unknown or conflicting evidence means stop.
    """
    status = "INTEGRATION_REJECTED_FAIL_CLOSED"
    stopped = True
    try:
        if (type(snapshots) is list and snapshots
                and type(restored_snapshot) is dict
                and type(minimum_sequence) is int
                and 0 <= minimum_sequence <= 1000000000):
            chain = audit_synthetic_snapshot_chain(snapshots, expected_day)
            restore = restore_synthetic_stop_state(
                restored_snapshot, expected_day, minimum_sequence)
            if (chain["status"] in CHAIN_OK
                    and restore["status"] in RESTORE_OK
                    and type(snapshots[-1]) is dict
                    and restored_snapshot == snapshots[-1]
                    and type(restored_snapshot.get("sequence")) is int
                    and restored_snapshot["sequence"] >= minimum_sequence
                    and chain["daily_stop_latched"] == restore["daily_stop_latched"]):
                stopped = restore["daily_stop_latched"]
                status = ("INTEGRATED_STOP_LATCHED_SYNTHETIC_ONLY" if stopped
                          else "INTEGRATED_CLEAN_NEVER_AUTHORIZED")
    except (TypeError, ValueError, KeyError, OverflowError, ArithmeticError):
        pass
    return {"status": status, "daily_stop_latched": stopped,
            "broker_verified": False, "production_usable": False,
            "orders_generated": False, "terminal_execution_approved": False,
            "forward_trading_enabled": False, "phase_1": "BLOCKED"}
