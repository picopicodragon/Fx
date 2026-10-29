"""P0-01 D5-3: deterministic, wholly synthetic contract consistency checks.

All values MUST be explicit hypothetical fixture values. This is NOT broker data,
broker verification, FX conversion sourcing, risk sizing, or permission to trade.
No filesystem, network, terminal access, orders, or clock reads.
"""
from __future__ import annotations

from decimal import Decimal, localcontext
from scripts.p0_01_offline_five_field_mock import (
    PAIRS, FIELDS, parse_positive_token, compare_synthetic_field_invariants, PASS
)

REVIEW = "REVIEW_REQUIRED"
INCOMPLETE = "INCOMPLETE"
CONSISTENT = "SYNTHETIC_CONTRACT_CONSISTENT_NEVER_VERIFIED"
ADDITIONAL = frozenset(("contract_size_base_units_per_lot",
                        "quote_to_deposit_synthetic_rate", "requested_lots"))
EXPECTED_KEYS = frozenset(("origin", "account_currency", "symbols"))
ROW_KEYS = frozenset(("symbol", "properties", "quote_currency", "tick_value_basis",
                      "contract_size_base_units_per_lot",
                      "quote_to_deposit_synthetic_rate", "requested_lots"))
QUOTE_CURRENCIES = {"USD/JPY": "JPY", "EUR/JPY": "JPY",
                    "GBP/USD": "USD", "AUD/USD": "USD"}


def assess_synthetic_contract(fixture: object) -> dict[str, object]:
    """Fail closed. Never expose raw caller data or exception text."""
    status = REVIEW
    try:
        if (type(fixture) is dict and set(fixture) == EXPECTED_KEYS
                and fixture["origin"] == "SYNTHETIC_ONLY"
                and type(fixture["account_currency"]) is str
                and fixture["account_currency"] in ("JPY", "USD")
                and type(fixture["symbols"]) is list
                and len(fixture["symbols"]) == len(PAIRS)):
            rows = fixture["symbols"]
            if all(type(r) is dict and set(r) == ROW_KEYS for r in rows):
                standard = [{"symbol": r["symbol"], "properties": r["properties"]}
                            for r in rows]
                pre = compare_synthetic_field_invariants(standard)
                if pre == PASS:
                    incomplete = False
                    invalid = False
                    for row in rows:
                        symbol = row["symbol"]
                        quote = QUOTE_CURRENCIES[symbol]
                        if row["quote_currency"] != quote or row["tick_value_basis"] != "PER_1_LOT":
                            invalid = True
                            continue
                        extra = [row[k] for k in ADDITIONAL]
                        if any(v is None or v == "" for v in extra):
                            incomplete = True
                            continue
                        values = [parse_positive_token(v) for v in extra]
                        if any(v is None for v in values):
                            invalid = True
                            continue
                        contract = parse_positive_token(row["contract_size_base_units_per_lot"])
                        conversion = parse_positive_token(row["quote_to_deposit_synthetic_rate"])
                        lots = parse_positive_token(row["requested_lots"])
                        p = row["properties"]
                        minimum = parse_positive_token(p["min_lot"])
                        step = parse_positive_token(p["lot_step"])
                        point = parse_positive_token(p["point_quote"])
                        size = parse_positive_token(p["tick_size_points"])
                        value = parse_positive_token(p["tick_value_deposit_currency"])
                        if lots < minimum or (lots - minimum) % step != 0:
                            invalid = True
                        # In a same-currency hypothetical scenario the unit conversion must be 1.
                        if quote == fixture["account_currency"] and conversion != Decimal(1):
                            invalid = True
                        with localcontext() as ctx:
                            ctx.prec = 48
                            expected = contract * point * size * conversion
                        # Exact identity only for the internally consistent synthetic fixture.
                        # Real brokers can have other contract conventions and dynamic rates.
                        if not expected.is_finite() or expected != value:
                            invalid = True
                    status = REVIEW if invalid else INCOMPLETE if incomplete else CONSISTENT
                elif pre == INCOMPLETE:
                    status = INCOMPLETE
    except Exception:
        status = REVIEW
    return {
        "status": status, "broker_verified": False,
        "production_usable": False, "broker_queried": False,
        "orders_generated": False, "terminal_execution_approved": False,
        "forward_trading_enabled": False, "phase_1": "BLOCKED",
    }
