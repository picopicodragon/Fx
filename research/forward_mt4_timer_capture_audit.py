"""FWD-080..083: inspect copied MT4 3-pair timer CSV captures offline.

The file names and CSV values are unverified operator data. In particular,
a good CSV never attests to broker source, account mode, or trading safety.
Only accesses the explicitly supplied local directory, never MT4 or orders.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from research.forward_mt4_v2_quote import COLUMNS, MAX_BYTES, PAIRS_V2, parse
from research.offline_backtest import InputError, timestamp

SCHEMA = "fx_forward_demo_observer_capture_audit_v1"
SYMBOLS = {"USDJPY": "USD/JPY", "EURJPY": "EUR/JPY", "EURUSD": "EUR/USD"}
PATTERN = re.compile(r"^FxFwdV3_(USDJPY|EURJPY|EURUSD)_([0-9]{8}_[0-9]{6})\.csv$")
MAX_FILES = 200
EXPECTED_INTERVAL = 60
INTERVAL_TOLERANCE = 15


def inspect(directory: Path, *, asof_utc: str) -> dict:
    cutoff = timestamp(asof_utc)
    if (not isinstance(directory, Path) or directory.is_symlink()
            or not directory.is_dir()):
        raise InputError("unsafe or absent capture folder")
    entries = list(directory.iterdir())
    if len(entries) > MAX_FILES:
        raise InputError("too many files; narrow evidence folder")
    if not entries:
        raise InputError("no manually copied CSV evidence")
    grouped: dict[str, dict[str, dict]] = defaultdict(dict)
    blockers: set[str] = set()
    seen_digests: set[str] = set()
    for path in entries:
        if path.is_symlink() or not path.is_file():
            raise InputError("unsafe capture directory entry")
        match = PATTERN.fullmatch(path.name)
        if match is None:
            raise InputError("unexpected file in capture folder")
        symbol, stamp = match.groups()
        if not 0 < path.stat().st_size <= MAX_BYTES:
            raise InputError("bad CSV file length")
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if digest in seen_digests:
            raise InputError("replayed identical CSV bytes")
        seen_digests.add(digest)
        # Parse historical records against their own capture time, not
        # the current inspection time; no false classification as live.
        import csv
        import io
        try:
            reader = csv.DictReader(io.StringIO(
                raw.decode("utf-8-sig"), newline=""), strict=True)
            if tuple(reader.fieldnames or ()) != COLUMNS:
                raise InputError("unexpected CSV shape")
            rows = list(reader)
        except (csv.Error, UnicodeError) as exc:
            raise InputError("invalid CSV") from exc
        if len(rows) != 1 or None in rows[0]:
            raise InputError("invalid CSV row count")
        observed_text = rows[0].get("observed_at_utc")
        observed = timestamp(observed_text)
        if observed > cutoff:
            raise InputError("future-dated CSV evidence")
        expected = datetime.strptime(stamp, "%Y%m%d_%H%M%S").replace(
            tzinfo=timezone.utc)
        if observed != expected:
            raise InputError("filename vs observed UTC mismatch")
        sample = parse(raw, asof_utc=observed_text)
        if sample["pair"] != SYMBOLS[symbol]:
            raise InputError("filename vs row pair mismatch")
        if symbol in grouped[stamp]:
            raise InputError("duplicate pair in capture cycle")
        grouped[stamp][symbol] = sample

    ordered = sorted(grouped)
    complete = 0
    incomplete = 0
    cycle_details = []
    for stamp in ordered:
        found = grouped[stamp]
        missing = sorted(set(SYMBOLS) - set(found))
        if missing:
            incomplete += 1
            blockers.add("INCOMPLETE_THREE_PAIR_CYCLE")
        else:
            complete += 1
            # Only a format/consistency assertion, NOT authenticated pricing.
            # EURUSD's research-only quote-to-JPY uses USDJPY same-cycle BID.
            # parse() preserves numeric values as decimal strings. Compare
            # their mathematical values, not formatting: e.g. 157.940 and
            # 157.94000 represent exactly the same USDJPY conversion rate.
            # Decimal avoids binary floating point and tolerance masking.
            usd = Decimal(found["USDJPY"]["bid"])
            conversion = Decimal(
                found["EURUSD"]["quote_to_jpy_research_only"])
            if usd != conversion:
                blockers.add("EURUSD_USDJPY_CONVERSION_INCONSISTENT")
        cycle_details.append({
            "capture_utc": datetime.strptime(
                stamp, "%Y%m%d_%H%M%S").replace(
                    tzinfo=timezone.utc).isoformat().replace("+00:00", "Z"),
            "pairs_found": [SYMBOLS[s] for s in SYMBOLS if s in found],
            "missing_symbols": missing,
            "all_three_present": not missing,
        })
    intervals = []
    for a, b in zip(ordered, ordered[1:]):
        first = datetime.strptime(a, "%Y%m%d_%H%M%S")
        second = datetime.strptime(b, "%Y%m%d_%H%M%S")
        delta = int((second - first).total_seconds())
        intervals.append(delta)
        if not EXPECTED_INTERVAL - INTERVAL_TOLERANCE <= delta <= EXPECTED_INTERVAL + INTERVAL_TOLERANCE:
            blockers.add("CAPTURE_INTERVAL_NOT_60S")
    if len(ordered) < 2:
        blockers.add("INSUFFICIENT_CYCLES_TO_MEASURE_INTERVAL")
    if len(ordered) > 30:
        blockers.add("MORE_THAN_30_CYCLES_IN_FOLDER")
    blockers.update((
        "BROKER_TIME_NOT_INDEPENDENTLY_ATTESTED",
        "DEMO_ACCOUNT_NOT_INDEPENDENTLY_VERIFIED",
        "NO_TRADING_PERMISSION_FROM_CSV_EVIDENCE",
    ))
    return {
        "schema": SCHEMA,
        "status": "DEMO_TIMER_CAPTURE_OFFLINE_NO_GO",
        "asof_utc": asof_utc,
        "file_count": len(entries),
        "cycle_count": len(ordered),
        "complete_cycle_count": complete,
        "incomplete_cycle_count": incomplete,
        "cycle_intervals_seconds": intervals,
        "cycles": cycle_details,
        "blocking_reasons": sorted(blockers),
        "captures_from_actual_mt4_verified": False,
        "metaeditor_compile_warning_count_independently_verified": False,
        "auto_trading_enabled": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
        "real_orders_permitted": False,
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Inspect copied MT4 observer CSVs; always NO_GO")
    p.add_argument("--directory", required=True, type=Path)
    p.add_argument("--asof-utc", required=True)
    p.add_argument("--out", required=True, type=Path)
    a = p.parse_args(argv)
    try:
        if a.out.exists() or not a.out.parent.is_dir():
            raise InputError("refuse output overwrite")
        result = inspect(a.directory, asof_utc=a.asof_utc)
        with a.out.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2)
        print(json.dumps({
            "status": result["status"],
            "files": result["file_count"],
            "complete_cycles": result["complete_cycle_count"],
            "incomplete_cycles": result["incomplete_cycle_count"],
            "blocking_reasons": result["blocking_reasons"],
            "runtime_go_no_go": "NO_GO",
            "real_orders_permitted": False,
        }))
        return 0
    except (InputError, OSError, ValueError, TypeError, UnicodeError,
            KeyError, OverflowError):
        print(json.dumps({"status": "FAIL_CLOSED",
                          "reason": "INVALID_TIMER_CSV_EVIDENCE",
                          "runtime_go_no_go": "NO_GO",
                          "safety_hold_latched": True,
                          "real_orders_permitted": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
