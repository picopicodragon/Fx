"""FWD-054/055: strict local v2 CSV intake for three specified FX pairs.

The broker's server-local clock offset is UNKNOWN: the server-relative
last-tick age is useful for rejecting obvious staleness, but NOT a proof of
market freshness, synchronised UTC, provenance, conversion, or execution.
No MT4 access, order API, network or paid inference calls.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from research.offline_backtest import InputError, decimal, timestamp

SCHEMA = "fx_forward_mt4_v2_manual_quote_v1"
PAIRS_V2 = ("USD/JPY", "EUR/JPY", "EUR/USD")
COLUMNS = ("observed_at_utc", "pair", "bid", "ask", "quote_to_jpy",
           "server_tick_time", "server_now_time", "tick_age_seconds",
           "account_type", "origin")
ORIGIN = "MANUAL_MT4_DEMO_V2_UNVERIFIED"
MAX_BYTES = 1200
SERVER_TIME_PATTERN = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}$")


def server_time(value: str) -> datetime:
    if type(value) is not str or not SERVER_TIME_PATTERN.fullmatch(value):
        raise InputError("server-local timestamp has invalid shape")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S")
    except ValueError as exc:
        raise InputError("server-local timestamp invalid") from exc


def parse(raw: bytes, *, asof_utc: str) -> dict:
    now = timestamp(asof_utc)
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_BYTES:
        raise InputError("missing/oversized v2 CSV")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeError as exc:
        raise InputError("unsupported v2 encoding") from exc
    try:
        reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
        if tuple(reader.fieldnames or ()) != COLUMNS:
            raise InputError("unexpected v2 CSV columns")
        rows = list(reader)
        if len(rows) != 1 or None in rows[0] or any(
                type(val) is not str for val in rows[0].values()):
            raise InputError("expected exactly one complete CSV record")
        row = rows[0]
    except csv.Error as exc:
        raise InputError("malformed CSV") from exc
    if (row["pair"] not in PAIRS_V2 or
            row["account_type"] != "DEMO" or
            row["origin"] != ORIGIN):
        raise InputError("untrusted v2 account/origin/pair")
    observed = timestamp(row["observed_at_utc"])
    age = (now - observed).total_seconds()
    if age < 0 or age > 90:
        raise InputError("PC clock observation stale/future")
    bid = decimal(row["bid"], "bid", positive=True)
    ask = decimal(row["ask"], "ask", positive=True)
    conversion = decimal(row["quote_to_jpy"], "quote_to_jpy", positive=True)
    if ask <= bid:
        raise InputError("crossed sides")
    if row["pair"].endswith("/JPY") and conversion != 1:
        raise InputError("JPY-quoted pairs require unit conversion")
    tick = server_time(row["server_tick_time"])
    current = server_time(row["server_now_time"])
    # Both broker server clock values are naive wall times; subtraction is
    # meaningful only insofar as the broker provided consistent values.
    delta = (current - tick).total_seconds()
    if (not re.fullmatch(r"0|[1-9][0-9]{0,2}",
                         row["tick_age_seconds"]) or
            int(row["tick_age_seconds"]) > 90 or
            delta != int(row["tick_age_seconds"])):
        raise InputError("incoherent or stale broker-relative tick")
    return {
        "schema": SCHEMA,
        "status": "MT4_V2_MANUAL_QUOTE_RESEARCH_NO_GO",
        "pair": row["pair"],
        "observed_at_utc": row["observed_at_utc"],
        "asof_utc": asof_utc,
        "server_tick_time_unverified": row["server_tick_time"],
        "server_now_time_unverified": row["server_now_time"],
        "server_relative_tick_age_seconds": int(row["tick_age_seconds"]),
        "csv_sha256": hashlib.sha256(raw).hexdigest(),
        "bid": str(bid), "ask": str(ask),
        "quote_to_jpy_research_only": str(conversion),
        "account_demo_self_reported": True,
        "server_timezone_offset_verified": False,
        "server_timestamp_authenticated": False,
        "independent_utc_clock_attested": False,
        "usd_conversion_feed_authenticated": False,
        "broker_quote_authenticity_verified": False,
        "demo_order_execution_enabled": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
        "real_orders_permitted": False,
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Offline three-pair MT4 v2 snapshot check")
    p.add_argument("--csv", required=True, type=Path)
    p.add_argument("--asof-utc", required=True)
    p.add_argument("--out", required=True, type=Path)
    a = p.parse_args(argv)
    try:
        if (a.out.exists() or not a.out.parent.is_dir() or
                not a.csv.is_file() or a.csv.is_symlink() or
                a.csv.stat().st_size > MAX_BYTES):
            raise InputError("unsafe input/output")
        result = parse(a.csv.read_bytes(), asof_utc=a.asof_utc)
        with a.out.open("x", encoding="utf-8") as file:
            json.dump(result, file, ensure_ascii=False, indent=2)
        print(json.dumps({
            "status": result["status"], "pair": result["pair"],
            "runtime_go_no_go": "NO_GO", "real_orders_permitted": False}))
        return 0
    except (InputError, OSError, UnicodeError, ValueError, TypeError, KeyError):
        print(json.dumps({
            "status": "FAIL_CLOSED",
            "reason": "MT4_V2_MANUAL_QUOTE_UNTRUSTED",
            "runtime_go_no_go": "NO_GO",
            "safety_hold_latched": True,
            "real_orders_permitted": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
