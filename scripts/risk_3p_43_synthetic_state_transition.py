"""Offline order-state transition and replay guards using fictional snapshots.

No MT4 access, real market data, account identifiers, files or network.
Synthetic close-token parity cannot prove an actual close or broker statement.
"""
from __future__ import annotations

from datetime import datetime

from scripts import risk_3p_36_synthetic_order_reconciliation as recon

KEYS = ("classification", "account_alias", "before", "after", "safety")
STEP_KEYS = ("sequence", "synthetic_snapshot", "synthetic_transition_token")
SAFETY = {
    "p05_passed": 0, "p05_03_accepted": False,
    "broker_order_state_reconciled": False,
    "real_close_event_verified": False, "real_mt4_read_authorized": False,
    "order_or_ea_action_authorized": False,
    "runtime_go_no_go": "NO_GO", "safety_hold_latched": True,
}
NO_EVENT = "SIM_NO_CHANGE"
CLOSE_EVENT = "SIM_DOCUMENTED_CLOSE_TEST_EVENT"
ONLY_ACCOUNT = recon.FICTITIOUS_ACCOUNT


def fixture(*, closing: bool = False) -> dict:
    old = recon.make_fixture(exposure=closing)
    new = recon.make_fixture(exposure=False)
    new["terminal"]["asof_utc"] = "SIM_2000-01-01T00:00:01Z"
    new["server"]["asof_utc"] = "SIM_2000-01-01T00:00:01Z"
    return {
        "classification": "SYNTHETIC_TIMELINE_NOT_REAL_BROKER_EVIDENCE",
        "account_alias": ONLY_ACCOUNT,
        "before": {
            "sequence": 1, "synthetic_snapshot": old,
            "synthetic_transition_token": NO_EVENT,
        },
        "after": {
            "sequence": 2, "synthetic_snapshot": new,
            "synthetic_transition_token": CLOSE_EVENT if closing else NO_EVENT,
        },
        "safety": dict(SAFETY),
    }


def _exact(x: object, keys: tuple[str, ...]) -> bool:
    return type(x) is dict and set(x) == set(keys)


def _sum_counts(rows: list) -> int:
    return sum(row["open_positions"] + row["pending_orders"] for row in rows)


def evaluate(package: object) -> dict:
    errors: list[str] = []
    timeline = "UNKNOWN"
    if not _exact(package, KEYS):
        errors.append("P43_MALFORMED_OR_SECRET_FIELDS")
    else:
        if (package["classification"] !=
                "SYNTHETIC_TIMELINE_NOT_REAL_BROKER_EVIDENCE"
                or package["account_alias"] != ONLY_ACCOUNT):
            errors.append("P43_FAKE_SCOPE_PROMOTED_TO_BROKER")
        if package["safety"] != SAFETY:
            errors.append("P43_RUNTIME_OR_RECONCILIATION_PERMISSION_FORGED")
        steps = []
        for label, expected_seq in (("before", 1), ("after", 2)):
            step = package[label]
            if not _exact(step, STEP_KEYS):
                errors.append("P43_INCOMPLETE_OR_EXTRA_STEP:" + label)
                continue
            if type(step["sequence"]) is not int or step["sequence"] != expected_seq:
                errors.append("P43_REPLAY_OR_OUT_OF_ORDER:" + label)
            token = step["synthetic_transition_token"]
            if type(token) is not str or token not in (NO_EVENT, CLOSE_EVENT):
                errors.append("P43_UNTRUSTED_FAKE_TRANSITION:" + label)
            snap = step["synthetic_snapshot"]
            try:
                check = recon.evaluate_synthetic_reconciliation(snap)
            except (KeyError, ValueError, TypeError, IndexError, AttributeError):
                errors.append("P43_INVALID_NESTED_SNAPSHOT:" + label)
                continue
            if (check["status"] != "PASS_OFFLINE_SYNTHETIC_ONLY"
                    or check["real_broker_state_reconciled"] is not False):
                errors.append("P43_UNVERIFIED_SNAPSHOT:" + label)
                continue
            try:
                stamp = recon._synthetic_utc(snap["terminal"]["asof_utc"])
                rows = snap["terminal"]["rows"]
                count = _sum_counts(rows)
            except (KeyError, TypeError, AttributeError):
                errors.append("P43_UNVERIFIED_SNAPSHOT:" + label)
                continue
            if stamp is None:
                errors.append("P43_BAD_FAKE_UTC:" + label)
                continue
            steps.append((label, stamp, count, token))
        if len(steps) == 2:
            _, t0, c0, old_token = steps[0]
            _, t1, c1, later_token = steps[1]
            if t1 <= t0:
                errors.append("P43_REPLAYED_OR_ROLLBACK_FAKE_TIMESTAMP")
            if old_token != NO_EVENT:
                errors.append("P43_BASELINE_CANNOT_HAVE_TRANSITION")
            if c1 > c0:
                errors.append("P43_UNEXPLAINED_NEW_EXPOSURE")
            elif c1 < c0 and later_token != CLOSE_EVENT:
                errors.append("P43_MISSING_SYNTHETIC_CLOSE_TOKEN")
            elif c1 == c0 and later_token != NO_EVENT:
                errors.append("P43_FAKE_CLOSE_WITHOUT_COUNT_CHANGE")
            if not errors:
                timeline = ("SIMULATED_CLOSE_NOT_BROKER_PROOF"
                            if c1 < c0 else "SIMULATED_NO_CHANGE_NOT_BROKER_PROOF")
    return {
        "status": "PASS_SYNTHETIC_TIMELINE_ONLY" if not errors else "FAIL_CLOSED",
        "synthetic_scenario": timeline if not errors else "UNKNOWN",
        "real_broker_order_state_reconciled": False,
        "real_order_absence_verified": False,
        "real_close_event_verified": False,
        "p05_03_accepted": False, "p05_passed": 0,
        "real_mt4_access_authorized": False,
        "trading_or_ea_action_authorized": False,
        "runtime_go_no_go": "NO_GO", "safety_hold_latched": True,
        "errors": errors,
    }
