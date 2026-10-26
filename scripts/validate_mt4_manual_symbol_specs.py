"""Compare manually transcribed MT4 symbol facts against PUBLIC broker rules.

No network, MT4 import/login, trade calls, files written, or safety approvals.
Read only a manually maintained JSON file outside the Git working tree.
"""
from __future__ import annotations

import argparse
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OFFICIAL = ROOT / "specs/p0_01_rakuten_mt4_public_contract_evidence.json"
EXPECTED_PAIRS = ("USD/JPY", "EUR/JPY", "GBP/USD", "AUD/USD")
TEMPLATE_FIELDS = (
    "lot_size_base_units",
    "min_lot",
    "lot_step",
    "max_lot",
    "point_quote",
    "digits",
    "tick_size_points",
    "tick_value_deposit_currency",
    "stop_level_points",
    "freeze_level_points",
    "spread_points",
)
NEEDED_TO_COMPARE = (
    "lot_size_base_units",
    "min_lot",
    "lot_step",
    "point_quote",
    "tick_size_points",
    "tick_value_deposit_currency",
)
NONNEGATIVE = {"stop_level_points", "freeze_level_points", "spread_points"}
EXPECTED_ROOT_KEYS = {
    "schema_version", "kind", "source_type", "data_state",
    "instructions", "symbols",
}


def safe_decimal(value: object) -> Decimal | None:
    """Accept exact finite decimal *strings*; no float rounding guesses."""
    if not isinstance(value, str) or not value or len(value) > 48:
        return None
    try:
        number = Decimal(value)
    except InvalidOperation:
        return None
    return number if number.is_finite() else None


def compare_manual_snapshot(data: object, reference: object) -> dict:
    """Return only public field names/statuses; never output user-entered values."""
    if not isinstance(data, dict) or set(data) != EXPECTED_ROOT_KEYS:
        return {"status": "REVIEW_REQUIRED", "findings": ["DOCUMENT_SCHEMA"], "pairs": []}
    if (data.get("schema_version") != 1
        or data.get("kind") != "MT4_MANUAL_SYMBOL_PROPERTIES_DRAFT"
        or data.get("source_type") != "MT4_MARKET_WATCH_SPECIFICATION_MANUAL_ONLY"
        or data.get("data_state") != "UNVERIFIED_LOCAL_VALUES"
        or not isinstance(data.get("instructions"), str)):
        return {"status": "REVIEW_REQUIRED", "findings": ["DOCUMENT_IDENTITY"], "pairs": []}

    if not isinstance(reference, dict) or "pair_evidence" not in reference:
        return {"status": "REVIEW_REQUIRED", "findings": ["OFFICIAL_REFERENCE"], "pairs": []}
    official_pairs = {r["symbol"]: r for r in reference["pair_evidence"]}
    official_rules = {r["id"]: r for r in reference["public_broker_rules"]}
    if set(official_pairs) != set(EXPECTED_PAIRS) or not {"RR-01", "RR-03"} <= set(official_rules):
        return {"status": "REVIEW_REQUIRED", "findings": ["OFFICIAL_REFERENCE"], "pairs": []}

    symbols = data.get("symbols")
    if not isinstance(symbols, list) or len(symbols) != 4:
        return {"status": "REVIEW_REQUIRED", "findings": ["SYMBOL_SET"], "pairs": []}
    if any(not isinstance(r, dict) or set(r) != {"symbol", "properties"}
           or not isinstance(r["properties"], dict) for r in symbols):
        return {"status": "REVIEW_REQUIRED", "findings": ["ROW_SCHEMA"], "pairs": []}
    names = [r["symbol"] for r in symbols]
    if any(not isinstance(name, str) for name in names):
        return {"status": "REVIEW_REQUIRED", "findings": ["SYMBOL_SET"], "pairs": []}
    if len(set(names)) != 4 or set(names) != set(EXPECTED_PAIRS):
        return {"status": "REVIEW_REQUIRED", "findings": ["SYMBOL_SET"], "pairs": []}

    results = []
    has_review = False
    has_incomplete = False
    for row in symbols:
        symbol = row["symbol"]
        props = row["properties"]
        findings = []
        if set(props) != set(TEMPLATE_FIELDS):
            findings.append("FIELDS_MISSING_OR_EXTRA")
        numbers: dict[str, Decimal] = {}
        for field in TEMPLATE_FIELDS:
            value = props.get(field)
            if value is None:
                continue
            numeric = safe_decimal(value)
            if numeric is None:
                findings.append(field + ":INVALID_DECIMAL")
                continue
            if field in NONNEGATIVE:
                valid_range = numeric >= 0
            else:
                valid_range = numeric > 0
            if field == "digits":
                valid_range = numeric == numeric.to_integral_value() and 1 <= numeric <= 10
            if not valid_range:
                findings.append(field + ":INVALID_RANGE")
                continue
            numbers[field] = numeric

        fixed = {
            "lot_size_base_units": Decimal(official_rules["RR-01"]["value"]),
            "min_lot": Decimal(official_rules["RR-03"]["value"]),
            "point_quote": Decimal(official_pairs[symbol]["public_one_point_quote"]),
        }
        for field, expected in fixed.items():
            if field in numbers and numbers[field] != expected:
                findings.append(field + ":PUBLIC_RULE_DIFFERS")
        if ("lot_step" in numbers and "min_lot" in numbers
                and numbers["lot_step"] > numbers["min_lot"]):
            findings.append("lot_step:GREATER_THAN_MINIMUM")
        if ("max_lot" in numbers and "min_lot" in numbers
                and numbers["max_lot"] < numbers["min_lot"]):
            findings.append("max_lot:LESS_THAN_MINIMUM")
        if "point_quote" in numbers and "digits" in numbers:
            if numbers["point_quote"] != Decimal(10) ** (-int(numbers["digits"])):
                findings.append("point_quote:DIGITS_INCONSISTENT")

        missing_required = [f for f in NEEDED_TO_COMPARE if f not in numbers]
        if findings:
            status = "REVIEW_REQUIRED"
            has_review = True
        elif missing_required:
            status = "INCOMPLETE"
            has_incomplete = True
        else:
            status = "COMPARED_FIELDS_ONLY"
        results.append({
            "symbol": symbol,
            "status": status,
            "missing_fields": missing_required,
            "findings": sorted(set(findings)),
        })

    overall = ("REVIEW_REQUIRED" if has_review else
               "INCOMPLETE" if has_incomplete else "COMPARED_FIELDS_ONLY")
    return {"status": overall, "findings": [], "pairs": results}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(
        "Check manually copied public MT4 symbol properties offline; never authorizes orders."
    ))
    parser.add_argument("--input", type=Path, required=True,
                        help="Private manually edited JSON outside the Git repository.")
    args = parser.parse_args(argv)
    if args.input.resolve().is_relative_to(ROOT.resolve()):
        print("REVIEW_REQUIRED: Private observations must remain outside the Git repository.")
        return 1
    try:
        data = json.loads(args.input.read_text(encoding="utf-8-sig"))
        official = json.loads(OFFICIAL.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError):
        print("REVIEW_REQUIRED: Cannot read or validate the private input and public reference.")
        return 1
    result = compare_manual_snapshot(data, official)
    print("MT4 manual contract crosscheck (NO TRADING AUTHORIZATION)")
    for pair in result["pairs"]:
        print(f'{pair["symbol"]}: {pair["status"]}')
        if pair["missing_fields"]:
            print("  PENDING FIELDS: " + ", ".join(pair["missing_fields"]))
        if pair["findings"]:
            print("  REVIEW FIELDS: " + ", ".join(pair["findings"]))
    if result["findings"]:
        print("REVIEW: " + ", ".join(result["findings"]))
    print("SUMMARY: " + result["status"])
    print("Public rules versus unverified manual entry only. "
          "No live orders; FORM-01/03 and PHASE-1 remain BLOCKED.")
    return {"COMPARED_FIELDS_ONLY": 0, "REVIEW_REQUIRED": 1, "INCOMPLETE": 2}[result["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
