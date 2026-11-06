"""Offline P05-03 reconciliation *simulation*, never a broker reconciliation.

No file reads, network access, MT4 interaction, order management, or user data.
Both simulated sources are fictional; matching them does not verify account state.
"""
from __future__ import annotations

from datetime import datetime

CATEGORIES = ("USD/JPY", "EUR/JPY", "EUR/USD", "OTHER_SYMBOLS")
PACKAGE_KEYS = ("schema_version", "classification", "owner_ui_observation",
                "account_alias", "safety", "terminal", "server")
SNAPSHOT_KEYS = ("source_kind", "source_token", "coverage",
                 "account_alias", "session_alias", "asof_utc",
                 "connection", "count_status", "rows")
COUNT_KEYS = ("category", "open_positions", "pending_orders")
SAFETY = {
    "p05_passed_checks": 0,
    "p05_03_accepted": False,
    "runtime_go_no_go": "NO_GO",
    "safety_hold_latched": True,
    "real_broker_reconciled": False,
    "real_mt4_access_authorized": False,
    "order_action_authorized": False,
    "remote_private_evidence_allowed": False,
}
SOURCES = (
    ("terminal", "SIM_TERMINAL_UI", "SIM_TERMINAL_ORIGIN",
     "SIM_TERMINAL_ACCOUNT_WIDE_EXPLICIT_ROWS"),
    ("server", "SIM_BROKER_SERVER_TEST_DOUBLE", "SIM_SERVER_ORIGIN",
     "SIM_SERVER_ACCOUNT_WIDE_EXPLICIT_ROWS"),
)
FICTITIOUS_ACCOUNT = "SIM_DEMO_ACCOUNT_A"
FICTITIOUS_SESSION = "SIM_SINGLE_TERMINAL_A"


def _exact(obj: object, keys: tuple[str, ...]) -> bool:
    return type(obj) is dict and set(obj) == set(keys)


def _synthetic_utc(value: object) -> datetime | None:
    if type(value) is not str or len(value) != 24:
        return None
    if not value.startswith("SIM_") or not value.endswith("Z"):
        return None
    try:
        # Compare fake source times to each other, never to the real clock.
        return datetime.strptime(value[4:], "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return None


def _snapshot(data: object, kind: str, source_token: str,
              coverage: str) -> tuple[list[str], datetime | None, list | None]:
    errors = []
    if not _exact(data, SNAPSHOT_KEYS):
        return ["P36_INCOMPLETE_OR_EXTRA_SOURCE_FIELDS"], None, None
    if (data["source_kind"] != kind
            or data["source_token"] != source_token
            or data["coverage"] != coverage
            or data["account_alias"] != FICTITIOUS_ACCOUNT
            or data["session_alias"] != FICTITIOUS_SESSION
            or data["connection"] != "SIM_CONNECTED"
            or data["count_status"] != "SIM_EXPLICIT_COUNTS"):
        errors.append("P36_SOURCE_UNVERIFIED_OR_PARTIAL")
    stamp = _synthetic_utc(data["asof_utc"])
    if stamp is None:
        errors.append("P36_INVALID_SIMULATED_UTC")
    rows = data["rows"]
    if type(rows) is not list or len(rows) != len(CATEGORIES):
        errors.append("P36_ACCOUNT_WIDE_COVERAGE_MISSING")
        return errors, stamp, None
    for i, category in enumerate(CATEGORIES):
        row = rows[i]
        if (not _exact(row, COUNT_KEYS)
                or row.get("category") != category
                or any(type(row.get(key)) is not int
                       or row[key] < 0 or row[key] > 100000
                       for key in ("open_positions", "pending_orders"))):
            errors.append("P36_UNKNOWN_OR_INVALID_COUNT:" + str(i + 1))
    return errors, stamp, rows


def evaluate_synthetic_reconciliation(package: object) -> dict:
    """Fail closed on unknown/conflict; output contains no user-supplied data."""
    errors: list[str] = []
    scenario = "UNVERIFIED"
    if not _exact(package, PACKAGE_KEYS):
        errors.append("P36_PACKAGE_SCHEMA_OR_SENSITIVE_DATA_FIELD")
    else:
        if (type(package["schema_version"]) is not int
                or package["schema_version"] != 1
                or package["classification"] != "SIMULATION_NOT_BROKER_EVIDENCE"
                or package["owner_ui_observation"] !=
                "BALANCE_ONLY_IS_NOT_ZERO_SERVER_ORDERS"
                or package["account_alias"] != FICTITIOUS_ACCOUNT):
            errors.append("P36_UNSAFE_SCOPE_OR_OWNER_UI_INFERENCE")
        if package["safety"] != SAFETY:
            errors.append("P36_TRADING_OR_OBSERVATION_AUTHORIZATION_FORGED")
        sources = {}
        for name, kind, token, coverage in SOURCES:
            check, stamp, rows = _snapshot(
                package[name], kind, token, coverage)
            errors.extend(check)
            sources[name] = (stamp, rows)
        terminal_time, terminal_rows = sources["terminal"]
        server_time, server_rows = sources["server"]
        if terminal_time is not None and server_time is not None:
            if abs((terminal_time - server_time).total_seconds()) > 30:
                errors.append("P36_SIMULATED_SOURCE_TIME_SKEW")
        if terminal_rows is not None and server_rows is not None:
            if not any(e.startswith("P36_UNKNOWN_OR_INVALID_COUNT") for e in
                       errors):
                for i, (terminal, server) in enumerate(
                        zip(terminal_rows, server_rows)):
                    if (terminal["open_positions"] != server["open_positions"]
                            or terminal["pending_orders"] !=
                            server["pending_orders"]):
                        errors.append("P36_POSITION_OR_PENDING_MISMATCH:"
                                      + str(i + 1))
                if not errors:
                    positive = any(
                        row["open_positions"] or row["pending_orders"]
                        for row in terminal_rows)
                    scenario = (
                        "MATCHED_EXPOSURE_SYNTHETIC_ONLY" if positive
                        else "MATCHED_ZERO_SYNTHETIC_ONLY")
    return {
        "status": "PASS_OFFLINE_SYNTHETIC_ONLY" if not errors else "FAIL_CLOSED",
        "synthetic_scenario": scenario if not errors else "UNVERIFIED",
        "real_broker_state_reconciled": False,
        "real_positions_or_orders_absent_verified": False,
        "p05_03_accepted": False,
        "p05_passed_checks": 0,
        "real_mt4_session_authorized": False,
        "order_or_ea_change_authorized": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
        "errors": errors,
    }


def make_fixture(*, exposure: bool = False) -> dict:
    """Synthetic mock data only; 0 does not mean any real account is flat."""
    def rows():
        return [
            {"category": pair,
             "open_positions": 2 if exposure and pair == "OTHER_SYMBOLS" else 0,
             "pending_orders": 1 if exposure and pair == "OTHER_SYMBOLS" else 0}
            for pair in CATEGORIES
        ]

    sources = {}
    for name, kind, token, coverage in SOURCES:
        sources[name] = {
            "source_kind": kind,
            "source_token": token,
            "coverage": coverage,
            "account_alias": FICTITIOUS_ACCOUNT,
            "session_alias": FICTITIOUS_SESSION,
            "asof_utc": "SIM_2000-01-01T00:00:00Z",
            "connection": "SIM_CONNECTED",
            "count_status": "SIM_EXPLICIT_COUNTS",
            "rows": rows(),
        }
    return {
        "schema_version": 1,
        "classification": "SIMULATION_NOT_BROKER_EVIDENCE",
        "owner_ui_observation": "BALANCE_ONLY_IS_NOT_ZERO_SERVER_ORDERS",
        "account_alias": FICTITIOUS_ACCOUNT,
        "safety": dict(SAFETY),
        "terminal": sources["terminal"],
        "server": sources["server"],
    }
