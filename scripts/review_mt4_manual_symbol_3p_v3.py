"""RISK-3P-03: standalone offline review of *unverified* 3-pair MT4 entries.

Never imports the legacy four-pair contract validator, infers a contract,
validates live broker facts, connects to MT4, calculates trade sizes, writes a
file, or authorizes an order. Private input must stay outside Git. This
checker deliberately cannot produce G1 VERIFIED or runtime GO.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, localcontext
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "specs/mt4_manual_symbol_3p_v3_template.json"
PAIRS = ("USD/JPY", "EUR/JPY", "EUR/USD")
FIVE = ("min_lot", "lot_step", "point_quote",
        "tick_size_points", "tick_value_deposit_currency")
PROPERTIES = ("lot_size_base_units", "min_lot", "lot_step", "max_lot",
              "point_quote", "digits", "tick_size_points",
              "tick_value_deposit_currency", "stop_level_points",
              "freeze_level_points", "spread_points")
NONNEGATIVE = {"stop_level_points", "freeze_level_points", "spread_points"}
OBSERVATION = {"terminal_symbol", "observed_at_utc", "source_kind"}
DISPLAY_TEXT = ("margin_currency", "profit_calculation_mode",
                "margin_calculation_mode", "hedged_margin_display",
                "margin_rate_display", "trade_mode_display",
                "execution_mode_display", "gtc_mode_display")
DAYS = ("sunday", "monday", "tuesday", "wednesday", "thursday",
        "friday", "saturday")
DISPLAY = {"spread_mode", *DISPLAY_TEXT, "trading_hours_display"}
ROOT_KEYS = {"schema_version", "kind", "scope", "source_type",
             "data_state", "instructions", "symbols"}
PAIR_KEYS = {"symbol", "observation", "properties", "display_properties"}
NUMBER = re.compile(r"(?:0|[1-9][0-9]*)(?:\.[0-9]+)?\Z", re.ASCII)
TERMINAL_NAME = re.compile(r"[A-Z]{6}[a-zA-Z0-9._-]{0,16}\Z", re.ASCII)
ISO_UTC = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z\Z", re.ASCII)
INCOMPLETE = "INCOMPLETE"
REVIEW = "REVIEW_REQUIRED"
STRUCTURAL = "FIVE_FIELDS_PRESENT_UNVERIFIED"
MAX_INPUT_BYTES = 65536


def _decimal(value: object, allow_zero: bool) -> Decimal | None:
    if (type(value) is not str or len(value) > 48
            or not NUMBER.fullmatch(value)):
        return None
    try:
        num = Decimal(value)
        if (not num.is_finite() or (num < 0 if allow_zero else num <= 0)
                or num > Decimal("1e12")
                or (num != 0 and num < Decimal("1e-12"))
                or len(num.normalize().as_tuple().digits) > 18):
            return None
        return num
    except (ValueError, InvalidOperation, ArithmeticError):
        return None


def _utc_syntax(value: object) -> bool:
    if type(value) is not str or not ISO_UTC.fullmatch(value):
        return False
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.tzinfo == timezone.utc and dt.year >= 2000
    except (ValueError, TypeError, OverflowError):
        return False


def _safe_display(value: object) -> bool:
    return (
        value is None or
        (type(value) is str and 0 < len(value) <= 160
         and value == value.strip()
         and all(ord(c) >= 32 and ord(c) != 127 for c in value))
    )


def _report(status: str, findings: list[str] | None = None,
            rows: list[dict] | None = None) -> dict[str, object]:
    # Findings contain known field identifiers only, not private values.
    return {
        "status": status,
        "findings": findings or [],
        "pairs": rows or [],
        "broker_queried": False,
        "production_authorized": False,
        "broker_contract_verified": False,
        "g1_real_world_verified": False,
        "order_allowed": False,
        "automatic_retry_allowed": False,
        "stop_release_allowed": False,
        "phase_1": "BLOCKED",
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
        "verified_values": None,
    }


def review_snapshot(data: object) -> dict[str, object]:
    """Review document *shape* and five illustrative fields, never facts."""
    if type(data) is not dict or set(data) != ROOT_KEYS:
        return _report(REVIEW, ["DOCUMENT_SCHEMA"])
    if (type(data.get("schema_version")) is not int
            or data["schema_version"] != 3
            or data.get("kind") != "MT4_MANUAL_SYMBOL_PROPERTIES_3P_V3"
            or data.get("scope") != "OFFLINE_3P_DESIGN_INPUT_ONLY"
            or data.get("source_type") != "MT4_MARKET_WATCH_SPECIFICATION_MANUAL_ONLY"
            or data.get("data_state") != "UNVERIFIED_LOCAL_VALUES"
            or type(data.get("instructions")) is not str
            or not data["instructions"]):
        return _report(REVIEW, ["DOCUMENT_IDENTITY"])
    rows = data["symbols"]
    if type(rows) is not list or len(rows) != 3:
        return _report(REVIEW, ["SYMBOL_SET"])
    if any(type(r) is not dict or set(r) != PAIR_KEYS
           or type(r.get("symbol")) is not str for r in rows):
        return _report(REVIEW, ["ROW_SCHEMA"])
    symbols = [r["symbol"] for r in rows]
    if len(set(symbols)) != 3 or set(symbols) != set(PAIRS):
        return _report(REVIEW, ["SYMBOL_SET"])

    output = []
    any_review = any_incomplete = False
    for row in rows:
        symbol = row["symbol"]
        findings: list[str] = []
        missing: list[str] = []
        obs, props, display = (row["observation"], row["properties"],
                               row["display_properties"])
        if type(obs) is not dict or set(obs) != OBSERVATION:
            findings.append("OBSERVATION_SCHEMA")
        else:
            name = obs["terminal_symbol"]
            if name is None:
                missing.append("terminal_symbol")
            elif (type(name) is not str or not TERMINAL_NAME.fullmatch(name)
                  or not name.startswith(symbol.replace("/", ""))):
                findings.append("terminal_symbol:INVALID")
            when = obs["observed_at_utc"]
            if when is None:
                missing.append("observed_at_utc")
            elif not _utc_syntax(when):
                findings.append("observed_at_utc:INVALID")
            source = obs["source_kind"]
            if source is None:
                missing.append("source_kind")
            elif type(source) is not str or source != "MANUAL_MT4_SPECIFICATION":
                findings.append("source_kind:INVALID")
        numbers: dict[str, Decimal] = {}
        if type(props) is not dict or set(props) != set(PROPERTIES):
            findings.append("PROPERTY_SCHEMA")
        else:
            for field in PROPERTIES:
                v = props[field]
                if v is None:
                    if field in FIVE:
                        missing.append(field)
                    continue
                number = _decimal(v, field in NONNEGATIVE)
                if number is None:
                    findings.append(field + ":INVALID_DECIMAL_OR_RANGE")
                    continue
                if field == "digits" and (number != number.to_integral_value()
                                          or not 1 <= number <= 10):
                    findings.append("digits:INVALID_RANGE")
                    continue
                numbers[field] = number
            if ("min_lot" in numbers and "lot_step" in numbers
                    and numbers["lot_step"] > numbers["min_lot"]):
                findings.append("lot_step:GREATER_THAN_MIN_LOT")
            if ("min_lot" in numbers and "max_lot" in numbers
                    and numbers["max_lot"] < numbers["min_lot"]):
                findings.append("max_lot:LESS_THAN_MIN_LOT")
            if "point_quote" in numbers and "digits" in numbers:
                with localcontext() as context:
                    context.prec = 40
                    if numbers["point_quote"] != Decimal(10) ** -int(numbers["digits"]):
                        findings.append("point_quote:DIGITS_INCONSISTENT")
            if ("point_quote" in numbers and "tick_size_points" in numbers):
                with localcontext() as context:
                    context.prec = 40
                    increment = numbers["point_quote"] * numbers["tick_size_points"]
                if not Decimal("1e-12") <= increment <= Decimal("1e12"):
                    findings.append("tick_size_points:POINT_MULTIPLICATION_OUT_OF_RANGE")

        if type(display) is not dict or set(display) != DISPLAY:
            findings.append("DISPLAY_SCHEMA")
        else:
            if (display["spread_mode"] is not None
                    and (type(display["spread_mode"]) is not str
                         or display["spread_mode"] not in ("FLOATING", "FIXED"))):
                findings.append("spread_mode:INVALID")
            if (display["spread_mode"] == "FLOATING"
                    and type(props) is dict and props.get("spread_points") is not None):
                findings.append("spread_points:FLOATING_DISPLAY_NOT_QUOTE")
            for field in DISPLAY_TEXT:
                if not _safe_display(display[field]):
                    findings.append(field + ":INVALID")
            days = display["trading_hours_display"]
            if type(days) is not dict or set(days) != set(DAYS):
                findings.append("trading_hours_display:INVALID_SCHEMA")
            elif any(not _safe_display(days[d]) for d in DAYS):
                findings.append("trading_hours_display:INVALID_TEXT")

        status = REVIEW if findings else INCOMPLETE if missing else STRUCTURAL
        any_review |= status == REVIEW
        any_incomplete |= status == INCOMPLETE
        output.append({
            "symbol": symbol,
            "status": status,
            "missing_fields": sorted(set(missing)),
            "findings": sorted(set(findings)),
        })
    overall = REVIEW if any_review else INCOMPLETE if any_incomplete else STRUCTURAL
    return _report(overall, rows=output)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Offline 3-pair manual MT4 schema review; no broker access.")
    parser.add_argument("--input", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        resolved = args.input.resolve()
        if resolved.is_relative_to(ROOT.resolve()):
            print("REVIEW_REQUIRED: private observations must remain outside Git.")
            return 1
        if resolved.stat().st_size > MAX_INPUT_BYTES:
            print("REVIEW_REQUIRED: input limit exceeded.")
            return 1
        data = json.loads(resolved.read_text(encoding="utf-8-sig"),
                          parse_float=Decimal)
        result = review_snapshot(data)
    except (OSError, ValueError, UnicodeError, TypeError,
            OverflowError, ArithmeticError):
        print("REVIEW_REQUIRED: private input could not be reviewed.")
        return 1
    print("RISK-3P-03: structure review only, never broker evidence.")
    for pair in result["pairs"]:
        print(pair["symbol"] + ": " + pair["status"])
        if pair["missing_fields"]:
            print("  MISSING: " + ", ".join(pair["missing_fields"]))
        if pair["findings"]:
            print("  REVIEW: " + ", ".join(pair["findings"]))
    if result["findings"]:
        print("REVIEW: " + ", ".join(result["findings"]))
    print("SUMMARY: " + result["status"])
    print("G1 UNRESOLVED | PHASE-1 BLOCKED | runtime NO_GO")
    return {REVIEW: 1, INCOMPLETE: 2, STRUCTURAL: 3}[result["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
