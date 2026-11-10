"""FX-FWD-006A: ingest ONE manually exported MT4 DEMO quote, no terminal IO.

Only reads a bounded CSV file from local disk. The 'DEMO' field is self-
reported and NOT independently verified. This is NOT an authenticated MT4
connection, not broker pricing, and not a source of trade authorization.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from research import forward_observation as obs
from research.offline_backtest import InputError, PAIRS, decimal, timestamp

COLUMNS = ("observed_at_utc", "pair", "bid", "ask", "quote_to_jpy",
           "account_type", "origin")
MAX_BYTES = 1000
ORIGIN = "MANUAL_MT4_DEMO_EXPORT_UNVERIFIED"


def parse_quote_csv(raw: str, *, now: datetime) -> dict:
    if not isinstance(raw, str) or len(raw.encode("utf-8")) > MAX_BYTES:
        raise InputError("invalid MT4 quote export size")
    reader = csv.DictReader(io.StringIO(raw), strict=True)
    if tuple(reader.fieldnames or ()) != COLUMNS:
        raise InputError("MT4 quote columns don't match")
    rows = list(reader)
    if len(rows) != 1 or None in rows[0]:
        raise InputError("exactly one quote row expected")
    row = rows[0]
    if (row["pair"] not in PAIRS or
            row["account_type"] != "DEMO" or
            row["origin"] != ORIGIN):
        raise InputError("untrusted account type, pair or origin")
    observed = timestamp(row["observed_at_utc"])
    current = now.astimezone(timezone.utc)
    if not timedelta(0) <= current - observed <= timedelta(seconds=90):
        raise InputError("stale or future quote")
    bid = decimal(row["bid"], "bid", positive=True)
    ask = decimal(row["ask"], "ask", positive=True)
    decimal(row["quote_to_jpy"], "quote_to_jpy", positive=True)
    if ask <= bid:
        raise InputError("invalid MT4 price sides")
    return {
        "schema": obs.SCHEMA,
        "kind": "PRICE_QUOTE",
        "observed_at_utc": row["observed_at_utc"],
        "source_id": "manual_mt4_demo",
        "payload": {
            "pair": row["pair"], "bid": row["bid"],
            "ask": row["ask"], "quote_to_jpy": row["quote_to_jpy"],
            "source_status": "USER_SUPPLIED_UNVERIFIED",
        },
    }


def import_quote(store: Path, file: Path, *,
                 now: datetime | None = None) -> dict:
    if file.stat().st_size > MAX_BYTES:
        raise InputError("excessive MT4 quote snapshot")
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    sample = parse_quote_csv(file.read_text(encoding="utf-8-sig"),
                             now=current)
    with tempfile.TemporaryDirectory() as root:
        staged = Path(root) / "quote.json"
        staged.write_text(json.dumps(sample), encoding="utf-8")
        result = obs.ingest(store, staged, now=current)
    return {**result, "account_type_verified": False,
            "mt4_connected": False,
            "demo_order_execution_enabled": False}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description="Offline manually exported MT4 demo quote, NO_GO")
    p.add_argument("--store", required=True, type=Path)
    p.add_argument("--csv", required=True, type=Path)
    args = p.parse_args(argv)
    try:
        result = import_quote(args.store, args.csv)
        print(json.dumps(result))
        return 0
    except (InputError, OSError, UnicodeError, ValueError, TypeError,
            csv.Error, ArithmeticError):
        print(json.dumps({
            "status": "FAIL_CLOSED",
            "reason": "MT4_QUOTE_EXPORT_INVALID_OR_UNVERIFIED",
            "runtime_go_no_go": "NO_GO",
            "safety_hold_latched": True,
            "real_orders_permitted": False,
        }))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
