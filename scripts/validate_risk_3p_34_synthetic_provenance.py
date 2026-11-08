"""Offline synthetic-only 3x5 provenance contract; no private file or MT4 I/O.

This module accepts only explicitly fictional in-memory fixtures. It never verifies
a broker fact, approves P05, or performs order/EA/terminal activity.
"""
from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

PAIRS = ("USD/JPY", "EUR/JPY", "EUR/USD")
FIELDS = ("min_lot", "lot_step", "point_quote",
          "tick_size_points", "tick_value_deposit_currency")
UNITS = {
    "min_lot": "LOT",
    "lot_step": "LOT",
    "point_quote": "QUOTE_CCY_PER_POINT",
    "tick_size_points": "POINTS_PER_TICK",
    "tick_value_deposit_currency": "DEPOSIT_CCY_PER_TICK",
}
ALIASES = {
    "USD/JPY": "SIM_USDJPY",
    "EUR/JPY": "SIM_EURJPY",
    "EUR/USD": "SIM_EURUSD",
}
PACKAGE_KEYS = ("schema_version", "classification", "target_pairs",
                "target_fields", "p05_status", "runtime_go_no_go",
                "safety_hold_latched", "broker_evidence_verified",
                "mt4_read_authorized", "order_authorized", "rows")
ROW_KEYS = ("pair", "field", "synthetic_value_decimal", "unit",
            "synthetic_terminal_symbol_alias", "synthetic_timestamp_utc",
            "primary_source", "independent_source", "status")
SOURCE_KEYS = ("kind", "token")
DECIMAL_STRING = re.compile(r"(?:0|[1-9][0-9]{0,11})(?:\.[0-9]{1,12})?\Z")
SIM_TOKEN = re.compile(r"SIM_[A-Z0-9_]{1,40}\Z")
SIM_UTC = re.compile(r"SIM_(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)\Z")


def _exact(obj: object, keys: tuple[str, ...]) -> bool:
    """Never hash or compare custom Python keys from an already-built dict."""
    if type(obj) is not dict or len(obj) != len(keys):
        return False
    found = tuple(obj)
    return all(type(k) is str for k in found) and set(found) == set(keys)


def _plain_string(value: object, expected: str) -> bool:
    return type(value) is str and value == expected


def _plain_string_list(value: object, expected: tuple[str, ...]) -> bool:
    return (type(value) is list and len(value) == len(expected)
            and all(type(x) is str for x in value)
            and value == list(expected))


def _positive_decimal(value: object) -> bool:
    if type(value) is not str or DECIMAL_STRING.fullmatch(value) is None:
        return False
    try:
        return Decimal(value).is_finite() and Decimal(value) > 0
    except (InvalidOperation, ValueError):
        return False


def _fake_utc(text: object) -> bool:
    if type(text) is not str:
        return False
    match = SIM_UTC.fullmatch(text)
    if match is None:
        return False
    try:
        datetime.strptime(match.group(1), "%Y-%m-%dT%H:%M:%SZ")
        return True
    except ValueError:
        return False


def _source(obj: object) -> bool:
    return (_exact(obj, SOURCE_KEYS)
            and _plain_string(obj.get("kind"), "FICTITIOUS_TEST_SOURCE")
            and type(obj.get("token")) is str
            and SIM_TOKEN.fullmatch(obj["token"]) is not None)


def _check_synthetic_package_impl(package: object) -> dict:
    """Never returns submitted data or tokens; errors use fixed codes/row indices."""
    errors: list[str] = []
    if not _exact(package, PACKAGE_KEYS):
        errors.append("P34_PACKAGE_SHAPE_OR_UNKNOWN_FIELDS")
    else:
        if (type(package["schema_version"]) is not int
                or package["schema_version"] != 1
                or not _plain_string(package["classification"],
                                     "SYNTHETIC_ONLY_NOT_BROKER_DATA")
                or not _plain_string_list(package["target_pairs"], PAIRS)
                or not _plain_string_list(package["target_fields"], FIELDS)):
            errors.append("P34_SCOPE_OR_CLASSIFICATION_DRIFT")
        if (not _plain_string(package["p05_status"], "BLOCKED")
                or not _plain_string(package["runtime_go_no_go"], "NO_GO")
                or package["safety_hold_latched"] is not True
                or package["broker_evidence_verified"] is not False
                or package["mt4_read_authorized"] is not False
                or package["order_authorized"] is not False):
            errors.append("P34_SAFETY_PERMISSION_FALSELY_PROMOTED")
        rows = package["rows"]
        if type(rows) is not list or len(rows) != 15:
            errors.append("P34_EXACTLY_15_ROWS_REQUIRED")
        else:
            for i, (pair, field) in enumerate(
                    (p, f) for p in PAIRS for f in FIELDS):
                row = rows[i]
                code = str(i + 1)
                if not _exact(row, ROW_KEYS):
                    errors.append("P34_ROW_SHAPE_OR_SECRET_FIELD:" + code)
                    continue
                if (not _plain_string(row["pair"], pair)
                        or not _plain_string(row["field"], field)
                        or not _plain_string(row["status"],
                                             "SYNTHETIC_NO_BROKER_PROOF")):
                    errors.append("P34_PAIR_FIELD_OR_STATUS_MISMATCH:" + code)
                if (not _positive_decimal(row["synthetic_value_decimal"])
                        or not _plain_string(row["unit"], UNITS[field])
                        or not _plain_string(
                            row["synthetic_terminal_symbol_alias"],
                            ALIASES[pair]) or not _fake_utc(
                            row["synthetic_timestamp_utc"])):
                    errors.append("P34_UNITS_VALUE_OR_FAKE_TIME_INVALID:" + code)
                primary, independent = (row["primary_source"],
                                        row["independent_source"])
                if (not _source(primary) or not _source(independent)
                        or (type(primary) is dict and type(independent) is dict
                            and primary.get("token") == independent.get("token"))):
                    errors.append("P34_SYNTHETIC_SOURCES_NOT_INDEPENDENT:" + code)
    return {
        "status": "PASS_SYNTHETIC_CONTRACT_ONLY" if not errors else "FAIL_CLOSED",
        "synthetic_rows_expected": 15,
        "real_broker_values_verified": 0,
        "p05_passed": 0,
        "real_mt4_read_authorized": False,
        "order_authorized": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
        "errors": errors,
    }



def check_synthetic_package(package: object) -> dict:
    """All malformed synthetic inputs fail closed with constant public codes.

    This is a narrow in-memory validation boundary, not a Python sandbox.
    """
    try:
        return _check_synthetic_package_impl(package)
    except Exception:
        return {
            "status": "FAIL_CLOSED",
            "synthetic_rows_expected": 15,
            "real_broker_values_verified": 0,
            "p05_passed": 0,
            "real_mt4_read_authorized": False,
            "order_authorized": False,
            "runtime_go_no_go": "NO_GO",
            "safety_hold_latched": True,
            "errors": ["P34_SYNTHETIC_VALIDATION_EXCEPTION"],
        }


def make_synthetic_fixture() -> dict:
    """Construct a clearly fictional example entirely in memory."""
    rows = []
    for i, (pair, field) in enumerate(
            (p, f) for p in PAIRS for f in FIELDS):
        token_id = f"{i + 1:02d}"
        rows.append({
            "pair": pair,
            "field": field,
            "synthetic_value_decimal": "7.77",
            "unit": UNITS[field],
            "synthetic_terminal_symbol_alias": ALIASES[pair],
            "synthetic_timestamp_utc": "SIM_2000-01-01T00:00:00Z",
            "primary_source": {"kind": "FICTITIOUS_TEST_SOURCE",
                               "token": "SIM_PRIMARY_" + token_id},
            "independent_source": {"kind": "FICTITIOUS_TEST_SOURCE",
                                   "token": "SIM_INDEPENDENT_" + token_id},
            "status": "SYNTHETIC_NO_BROKER_PROOF",
        })
    return {
        "schema_version": 1,
        "classification": "SYNTHETIC_ONLY_NOT_BROKER_DATA",
        "target_pairs": list(PAIRS),
        "target_fields": list(FIELDS),
        "p05_status": "BLOCKED",
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
        "broker_evidence_verified": False,
        "mt4_read_authorized": False,
        "order_authorized": False,
        "rows": rows,
    }
