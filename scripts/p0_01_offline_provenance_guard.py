"""P0-01 D4-1: pure offline provenance guard, never a broker attestation.

No IO, clock reads, trading functions, account data, or automatic promotion.
"""
from __future__ import annotations
from datetime import datetime, timezone
from decimal import Decimal
from scripts.p0_01_offline_five_field_mock import PAIRS, FIELDS, parse_positive_token

REVIEW = "REVIEW_REQUIRED"
INCOMPLETE = "INCOMPLETE"
PENDING = "PENDING_EVIDENCE"
PASS = "OFFLINE_SHAPE_PASS_NEVER_BROKER_VERIFIED"
MAX_AGE_SECONDS = 86400  # synthetic test criterion, not broker certification
EXPECTED_UNITS = {
    "min_lot": "lot", "lot_step": "lot",
    "point_quote": "quote_per_point",
    "tick_size_points": "points_per_tick",
    "tick_value_deposit_currency": "deposit_currency_per_tick",
}


def _time(value: object) -> datetime | None:
    if type(value) is not str or len(value) > 35:
        return None
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            return None
        return parsed.astimezone(timezone.utc)
    except (ValueError, TypeError, OverflowError):
        return None


def check_candidate(candidate: object, reference_time: object) -> dict[str, object]:
    """Fixed statuses only, never input values or exception messages."""
    status = REVIEW
    try:
        now = _time(reference_time)
        if now is None or type(candidate) is not dict or set(candidate) != {
            "origin", "symbols", "observed_at", "evidence_kind",
            "account_currency", "contract_basis_confirmed"
        }:
            status = REVIEW
        elif candidate["origin"] != "MANUAL_UNVERIFIED":
            status = REVIEW
        elif type(candidate["symbols"]) is not list or len(candidate["symbols"]) != 4:
            status = REVIEW
        else:
            missing = False
            invalid = False
            seen = set()
            for row in candidate["symbols"]:
                if type(row) is not dict or set(row) != {"symbol", "properties", "units"}:
                    invalid = True
                    continue
                symbol = row["symbol"]
                if type(symbol) is not str or symbol not in PAIRS or symbol in seen:
                    invalid = True
                    continue
                seen.add(symbol)
                props, units = row["properties"], row["units"]
                if type(props) is not dict or type(units) is not dict or set(props) != set(FIELDS) or set(units) != set(FIELDS):
                    invalid = True
                    continue
                for field in FIELDS:
                    if units[field] != EXPECTED_UNITS[field]:
                        invalid = True
                    if props[field] is None or props[field] == "":
                        missing = True
                    elif parse_positive_token(props[field]) is None:
                        invalid = True
            if seen != set(PAIRS):
                invalid = True
            timestamp = _time(candidate["observed_at"])
            if candidate["observed_at"] is None or candidate["observed_at"] == "":
                missing = True
            elif timestamp is None or not 0 <= (now - timestamp).total_seconds() <= MAX_AGE_SECONDS:
                invalid = True
            if candidate["evidence_kind"] is None or candidate["evidence_kind"] == "":
                missing = True
            elif candidate["evidence_kind"] != "MANUAL_SCREEN_NOTE_UNVERIFIED":
                invalid = True
            if candidate["account_currency"] is None or candidate["account_currency"] == "":
                missing = True
            elif type(candidate["account_currency"]) is not str or len(candidate["account_currency"]) != 3 or not candidate["account_currency"].isascii() or not candidate["account_currency"].isupper() or not candidate["account_currency"].isalpha():
                invalid = True
            if candidate["contract_basis_confirmed"] is not False:
                # No provenance supplied to this offline-only interface can certify it.
                invalid = True
            status = REVIEW if invalid else INCOMPLETE if missing else PENDING
    except Exception:
        status = REVIEW
    return {"status": status, "broker_verified": False,
            "production_usable": False, "orders_generated": False,
            "terminal_execution_approved": False,
            "forward_trading_enabled": False, "phase_1": "BLOCKED"}
