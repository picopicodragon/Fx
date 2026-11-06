"""Offline fail-closed safety latch simulation, never controls a broker.

No event or purported human approval can release an operational stop.
This is not a replacement for risk controls, watchdog or MT4/EA execution.
"""
from __future__ import annotations

EVENTS = {
    "SIM_COMMUNICATION_LOSS_60S": "SIM_LEVEL_1_WARNING",
    "SIM_COMMUNICATION_LOSS_600S": "SIM_LEVEL_2_WARNING",
    "SIM_DRAWDOWN_2_PCT": "SIM_LEVEL_1_WARNING",
    "SIM_DRAWDOWN_3_PCT": "SIM_LEVEL_2_REEVALUATION",
    "SIM_DRAWDOWN_4_PCT": "SIM_LEVEL_3_NEW_ENTRIES_STOP",
    "SIM_DRAWDOWN_5_PCT": "SIM_FULL_EXIT_REQUIRED_HUMAN_APPROVAL",
    "SIM_DAILY_LOSS_1_5_PCT": "SIM_FULL_EXIT_DAILY_STOP",
    "SIM_PROCESS_RESTART": "SIM_CLOCK_CONTINUITY_UNKNOWN",
    "SIM_MONOTONIC_CLOCK_ROLLBACK": "SIM_CLOCK_CONTINUITY_UNKNOWN",
    "SIM_OPERATOR_APPROVAL_CLAIM": "SIM_APPROVAL_UNTRUSTED",
    "SIM_RECOVERY_PROPOSED": "SIM_RECOVERY_NOT_AUTHORIZED",
}
STATES = ("SIM_HELD", "SIM_BLOCKED_AFTER_EVENT")
KEYS = ("classification", "sequence", "previous_sequence", "state",
        "event", "safety")
SAFETY = {
    "p05_passed": 0,
    "human_approval_independently_verified": False,
    "real_broker_close_or_exit_confirmed": False,
    "auto_resumption_allowed": False,
    "real_order_action_authorized": False,
    "real_mt4_or_ea_action_authorized": False,
    "recovery_authorized": False,
    "runtime_go_no_go": "NO_GO",
    "safety_hold_latched": True,
}


def fixture(event: str = "SIM_RECOVERY_PROPOSED") -> dict:
    return {
        "classification": "SIMULATED_LATCH_NEVER_REAL_AUTHORIZATION",
        "sequence": 2,
        "previous_sequence": 1,
        "state": "SIM_HELD",
        "event": event,
        "safety": dict(SAFETY),
    }


def evaluate(data: object) -> dict:
    errors: list[str] = []
    scenario = "UNVERIFIED"
    if type(data) is not dict or set(data) != set(KEYS):
        errors.append("P44_INVALID_OR_EXTRA_FIELDS")
    else:
        if (data["classification"] !=
                "SIMULATED_LATCH_NEVER_REAL_AUTHORIZATION"
                or data["state"] not in STATES):
            errors.append("P44_REAL_STOP_STATE_MISREPRESENTED")
        if (type(data["previous_sequence"]) is not int
                or type(data["sequence"]) is not int
                or data["previous_sequence"] < 1
                or data["sequence"] != data["previous_sequence"] + 1
                or data["sequence"] > 1000000):
            errors.append("P44_SEQUENCE_ROLLBACK_OR_GAP")
        if type(data["event"]) is not str or data["event"] not in EVENTS:
            errors.append("P44_UNKNOWN_OR_REAL_EVENT_INJECTED")
        if data["safety"] != SAFETY:
            errors.append("P44_UNAUTHORIZED_RESUMPTION_OR_EXIT_PROOF")
        if not errors:
            scenario = EVENTS[data["event"]]
    return {
        "status": "PASS_SYNTHETIC_LATCH_ONLY" if not errors else "FAIL_CLOSED",
        "simulated_state": scenario if not errors else "UNVERIFIED",
        "real_stop_release_granted": False,
        "real_exit_or_order_action_performed": False,
        "human_approval_recorded": False,
        "real_account_risk_assessed": False,
        "p05_passed": 0,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
        "errors": errors,
    }
