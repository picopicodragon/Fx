"""Pure, deterministic synthetic MT4 five-field checks. No broker observations.

No filesystem, terminal, networking, order or approval functionality exists here.
"""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation, localcontext

PAIRS = ("USD/JPY", "EUR/JPY", "GBP/USD", "AUD/USD")
FIELDS = ("min_lot", "lot_step", "point_quote",
          "tick_size_points", "tick_value_deposit_currency")
PASS = "SYNTHETIC_CHECKS_PASS_NEVER_VERIFIED"
REVIEW = "REVIEW_REQUIRED"
INCOMPLETE = "INCOMPLETE"
# Bounds are strictly synthetic sanity limits, NOT broker specifications.
TOKEN = re.compile(r"(?:0|[0-9]+)(?:\.[0-9]+)?\Z", re.ASCII)
MAX_TOKEN_LENGTH = 48
MAX_ABS_EXPONENT = 12
MAX_SIGNIFICANT_DIGITS = 18


def parse_positive_token(value: object) -> Decimal | None:
    """Reject coercion, scientific notation, huge exponents, tiny and huge values."""
    if type(value) is not str or not 1 <= len(value) <= MAX_TOKEN_LENGTH:
        return None
    if TOKEN.fullmatch(value) is None:
        return None
    try:
        result = Decimal(value)
        if (not result.is_finite() or result <= 0
                or not Decimal("1e-12") <= result <= Decimal("1e12")
                or len(result.normalize().as_tuple().digits) > MAX_SIGNIFICANT_DIGITS):
            return None
        return result
    except (InvalidOperation, ValueError, ArithmeticError):
        return None


def validate_fixture_shape(rows: object) -> str:
    """Strict 4-row list schema; do not allow duplicates, unknown or extra keys."""
    if type(rows) is not list or len(rows) != len(PAIRS):
        return REVIEW
    seen = set()
    for row in rows:
        if type(row) is not dict or set(row) != {"symbol", "properties"}:
            return REVIEW
        name = row["symbol"]
        if type(name) is not str or name not in PAIRS or name in seen:
            return REVIEW
        seen.add(name)
        if type(row["properties"]) is not dict:
            return REVIEW
        if set(row["properties"]) != set(FIELDS):
            # Missing keys are malformed schema, not equivalent to explicit null.
            return REVIEW
    return PASS if seen == set(PAIRS) else REVIEW


def validate_positive_decimal_tokens(rows: object) -> str:
    if validate_fixture_shape(rows) != PASS:
        return REVIEW
    invalid = False
    missing = False
    for row in rows:
        for name in FIELDS:
            value = row["properties"][name]
            if value is None or value == "":
                missing = True
            elif parse_positive_token(value) is None:
                invalid = True
    return REVIEW if invalid else INCOMPLETE if missing else PASS


def compare_synthetic_field_invariants(rows: object) -> str:
    preliminary = validate_positive_decimal_tokens(rows)
    if preliminary != PASS:
        return preliminary
    for row in rows:
        values = {key: parse_positive_token(row["properties"][key]) for key in FIELDS}
        if values["lot_step"] > values["min_lot"]:
            return REVIEW
        # Synthetic unit relationship only; never infer currency, contract size,
        # true broker precision or actual risk from this multiplication.
        with localcontext() as ctx:
            ctx.prec = 36
            increment = values["point_quote"] * values["tick_size_points"]
        if not increment.is_finite() or increment > Decimal("1e12") or increment < Decimal("1e-12"):
            return REVIEW
    return PASS


def report_safe_status_codes_only(rows: object) -> dict[str, object]:
    """Never echo values or exception details, including a caller's custom objects."""
    try:
        status = compare_synthetic_field_invariants(rows)
        if status not in {REVIEW, INCOMPLETE, PASS}:
            status = REVIEW
    except Exception:
        status = REVIEW
    return {"status": status, "production_usable": False,
            "broker_queried": False, "orders_generated": False,
            "terminal_execution_approved": False,
            "forward_trading_enabled": False, "phase_1": "BLOCKED"}
