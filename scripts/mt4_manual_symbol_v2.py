"""Safe offline migration/check for manually entered MT4 specification v2.

Never connects to MT4, sends orders, overwrites the source, or writes to Git.
Output contains local observations and must remain outside the repository.
"""
from __future__ import annotations

import argparse
import copy
import json
import re
from pathlib import Path

# Support both:
#   python -m scripts.mt4_manual_symbol_v2 ...
#   python scripts/mt4_manual_symbol_v2.py ...
# The latter adds scripts/ rather than the repository root to sys.path.
# Avoid modifying sys.path or catching unrelated ModuleNotFoundError exceptions.
if __package__:
    from .validate_mt4_manual_symbol_specs import (
        EXPECTED_PAIRS, EXPECTED_ROOT_KEYS, OFFICIAL, ROOT, TEMPLATE_FIELDS,
        compare_manual_snapshot,
    )
else:
    from validate_mt4_manual_symbol_specs import (
        EXPECTED_PAIRS, EXPECTED_ROOT_KEYS, OFFICIAL, ROOT, TEMPLATE_FIELDS,
        compare_manual_snapshot,
    )

V2_TEMPLATE = ROOT / "specs/p0_01_mt4_manual_symbol_template_v2.json"
DAYS = ("sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday")
DISPLAY_TEXT_FIELDS = (
    "margin_currency", "profit_calculation_mode",
    "margin_calculation_mode", "hedged_margin_display",
    "margin_rate_display", "trade_mode_display",
    "execution_mode_display", "gtc_mode_display",
)
DISPLAY_FIELDS = {"spread_mode", *DISPLAY_TEXT_FIELDS, "trading_hours_display"}
MAX_INPUT_BYTES = 65536


def safe_location(path: Path) -> bool:
    """Do not read or write any private observations inside the repository."""
    try:
        resolved = path.resolve()
        return not resolved.is_relative_to(ROOT.resolve())
    except (OSError, RuntimeError, ValueError):
        return False


def read_private_json(path: Path) -> object:
    if not safe_location(path):
        raise ValueError("Input must be outside Git checkout")
    if path.stat().st_size > MAX_INPUT_BYTES:
        raise ValueError("Input file size exceeds the local review limit")
    return json.loads(path.read_text(encoding="utf-8-sig"))


def v1_structure_ok(data: object) -> bool:
    if not isinstance(data, dict) or set(data) != EXPECTED_ROOT_KEYS:
        return False
    if (type(data["schema_version"]) is not int or data["schema_version"] != 1
        or data.get("kind") != "MT4_MANUAL_SYMBOL_PROPERTIES_DRAFT"
        or data.get("source_type") != "MT4_MARKET_WATCH_SPECIFICATION_MANUAL_ONLY"
        or data.get("data_state") != "UNVERIFIED_LOCAL_VALUES"
        or not isinstance(data.get("instructions"), str)
        or not isinstance(data.get("symbols"), list)
        or len(data["symbols"]) != 4):
        return False
    names = []
    for row in data["symbols"]:
        if (not isinstance(row, dict) or set(row) != {"symbol", "properties"}
            or not isinstance(row["symbol"], str)
            or not isinstance(row["properties"], dict)
            or set(row["properties"]) != set(TEMPLATE_FIELDS)):
            return False
        if any(v is not None and not isinstance(v, str)
               for v in row["properties"].values()):
            return False
        names.append(row["symbol"])
    return len(set(names)) == 4 and set(names) == set(EXPECTED_PAIRS)


def migrate_to_v2(v1: object, template: object) -> dict:
    """Copy all old values and keep every new observation null, without guessing."""
    if not v1_structure_ok(v1):
        raise ValueError("Original format or values not recognized; no migration performed")
    if not isinstance(template, dict) or template.get("schema_version") != 2:
        raise ValueError("V2 template not available")
    if not isinstance(template.get("symbols"), list):
        raise ValueError("V2 template symbols unavailable")
    out = copy.deepcopy(template)
    originals = {x["symbol"]: x["properties"] for x in v1["symbols"]}
    if {x["symbol"] for x in out["symbols"]} != set(EXPECTED_PAIRS):
        raise ValueError("V2 template symbol coverage mismatch")
    for pair in out["symbols"]:
        if set(pair["properties"]) != set(TEMPLATE_FIELDS):
            raise ValueError("V2 template numeric fields mismatch")
        pair["properties"] = copy.deepcopy(originals[pair["symbol"]])
    return out


def valid_display_text(value: object, max_len: int = 160) -> bool:
    return (
        value is None or (
            isinstance(value, str) and 0 < len(value) <= max_len
            and value == value.strip()
            and not any(ord(ch) < 32 or ord(ch) == 127 for ch in value)
        )
    )


def check_v2(data: object, official: object) -> dict:
    """Strict format check + reuse the v1 non-authorizing public-rule crosscheck."""
    error = lambda reason: {
        "status": "REVIEW_REQUIRED", "findings": [reason], "pairs": []
    }
    if not isinstance(data, dict) or set(data) != EXPECTED_ROOT_KEYS:
        return error("V2_DOCUMENT_SCHEMA")
    if (type(data.get("schema_version")) is not int
        or data["schema_version"] != 2
        or data.get("kind") != "MT4_MANUAL_SYMBOL_PROPERTIES_V2"
        or data.get("source_type") != "MT4_MARKET_WATCH_SPECIFICATION_MANUAL_ONLY"
        or data.get("data_state") != "UNVERIFIED_LOCAL_VALUES"
        or not isinstance(data.get("instructions"), str)):
        return error("V2_DOCUMENT_IDENTITY")
    rows = data.get("symbols")
    if not isinstance(rows, list) or len(rows) != 4:
        return error("V2_SYMBOL_SET")
    if any(not isinstance(row, dict)
           or set(row) != {"symbol", "properties", "display_properties"}
           or not isinstance(row["symbol"], str)
           or not isinstance(row["properties"], dict)
           or not isinstance(row["display_properties"], dict)
           for row in rows):
        return error("V2_ROW_SCHEMA")
    names = [row["symbol"] for row in rows]
    if len(set(names)) != 4 or set(names) != set(EXPECTED_PAIRS):
        return error("V2_SYMBOL_SET")
    for row in rows:
        if (set(row["properties"]) != set(TEMPLATE_FIELDS)
            or set(row["display_properties"]) != DISPLAY_FIELDS):
            return error("V2_FIELD_SET")
        hours = row["display_properties"]["trading_hours_display"]
        if not isinstance(hours, dict) or set(hours) != set(DAYS):
            return error("V2_TRADING_HOURS_SCHEMA")

    # The existing v1 validator remains authoritative for legacy numeric
    # formats, public contract values, and incomplete/unconfirmed fields.
    v1 = {
        "schema_version": 1,
        "kind": "MT4_MANUAL_SYMBOL_PROPERTIES_DRAFT",
        "source_type": data["source_type"],
        "data_state": data["data_state"],
        "instructions": data["instructions"],
        "symbols": [
            {"symbol": row["symbol"], "properties": row["properties"]}
            for row in rows
        ],
    }
    base = compare_manual_snapshot(v1, official)
    result = {"status": base["status"], "findings": list(base["findings"]),
              "pairs": copy.deepcopy(base["pairs"])}
    if len(result["pairs"]) != 4:
        return error("V2_NUMERIC_VALIDATION")
    pending = False
    needs_review = result["status"] == "REVIEW_REQUIRED"
    for row in rows:
        display = row["display_properties"]
        summary = next(x for x in result["pairs"] if x["symbol"] == row["symbol"])
        findings = summary["findings"]
        missing = summary["missing_fields"]
        mode = display["spread_mode"]
        if mode is not None and mode not in ("FLOATING", "FIXED", "UNKNOWN"):
            findings.append("spread_mode:INVALID_ENUM")
        if mode == "FLOATING" and row["properties"]["spread_points"] is not None:
            findings.append("spread_points:FLOATING_DISPLAY_IS_NOT_NUMERIC_QUOTE")
        currency = display["margin_currency"]
        if currency is not None and (
            not isinstance(currency, str)
            or re.fullmatch(r"[A-Z]{3}", currency) is None
        ):
            findings.append("margin_currency:INVALID_CURRENCY")
        for field in DISPLAY_TEXT_FIELDS:
            if field == "margin_currency":
                continue
            if not valid_display_text(display[field]):
                findings.append(field + ":INVALID_DISPLAY_TEXT")
        for day in DAYS:
            if not valid_display_text(display["trading_hours_display"][day], 256):
                findings.append("trading_hours_display." + day + ":INVALID_TEXT")

        pending_row = (
            any(display[field] is None for field in DISPLAY_FIELDS
                if field != "trading_hours_display")
            or any(display["trading_hours_display"][day] is None for day in DAYS)
        )
        pending = pending or pending_row
        summary["findings"] = sorted(set(findings))
        summary["missing_fields"] = list(missing)
        if findings:
            summary["status"] = "REVIEW_REQUIRED"
            needs_review = True
        elif missing or pending_row:
            # v2 manual screen transcription is not a complete API attestation.
            summary["status"] = "INCOMPLETE"
    if needs_review:
        result["status"] = "REVIEW_REQUIRED"
    elif pending or any(p["status"] == "INCOMPLETE" for p in result["pairs"]):
        result["status"] = "INCOMPLETE"
    else:
        result["status"] = "COMPARED_FIELDS_ONLY"
    return result


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="MT4 v1 -> v2 manual specification migration or offline v2 check; no trading")
    sub = parser.add_subparsers(dest="command", required=True)
    migrate = sub.add_parser("migrate", help="Create new v2 file; source kept unchanged")
    migrate.add_argument("--input", type=Path, required=True)
    migrate.add_argument("--output", type=Path, required=True)
    check = sub.add_parser("check", help="Review local v2 data without printing input values")
    check.add_argument("--input", type=Path, required=True)
    args = parser.parse_args(argv)
    print("MT4 manual v2 (OFFLINE ONLY / NO TRADE OR IMPLEMENTATION APPROVAL)")
    try:
        if args.command == "migrate":
            if (not safe_location(args.input) or not safe_location(args.output)
                or args.input.resolve() == args.output.resolve()):
                print("REVIEW_REQUIRED: Source and output must be different Git-external paths.")
                return 1
            data = read_private_json(args.input)
            template = json.loads(V2_TEMPLATE.read_text(encoding="utf-8"))
            converted = migrate_to_v2(data, template)
            official = json.loads(OFFICIAL.read_text(encoding="utf-8"))
            if check_v2(converted, official)["status"] == "REVIEW_REQUIRED":
                print("REVIEW_REQUIRED: Original values inconsistent with public rules; "
                      "source unchanged and no v2 file written.")
                return 1
            # Exclusive creation is deliberate: never overwrite source or any
            # existing v2 file, even after crash/repeat invocation.
            with args.output.open("x", encoding="utf-8") as target:
                json.dump(converted, target, ensure_ascii=False, indent=2)
                target.write("\n")
            print("CREATED: New v2 file at specified Git-external path (source unchanged).")
            print("PENDING: New display properties remain null until manually transcribed.")
            return 0

        official = json.loads(OFFICIAL.read_text(encoding="utf-8"))
        result = check_v2(read_private_json(args.input), official)
        for pair in result["pairs"]:
            print(f'{pair["symbol"]}: {pair["status"]}')
            if pair["missing_fields"]:
                print("  PENDING FIELDS: " + ", ".join(pair["missing_fields"]))
            if pair["findings"]:
                print("  REVIEW FIELDS: " + ", ".join(pair["findings"]))
        if result["findings"]:
            print("REVIEW: " + ", ".join(result["findings"]))
        print("SUMMARY: " + result["status"])
        print("Even COMPARED_FIELDS_ONLY does not allow FX orders; PHASE-1 BLOCKED.")
        return {"COMPARED_FIELDS_ONLY": 0, "REVIEW_REQUIRED": 1, "INCOMPLETE": 2}[result["status"]]
    except (OSError, ValueError, TypeError, KeyError, UnicodeError):
        print("REVIEW_REQUIRED: Migration/check failed; no existing file intentionally overwritten. "
              "Verify schema, paths, public values and write permissions.")
        return 1


if __name__ == "__main__":
    raise SystemExit(run())
