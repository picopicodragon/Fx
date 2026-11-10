"""FWD-019: offline per-pair bid/ask continuity from verified local journal.

Data are locally supplied and unverified; no live feed or broker credentials.
This tool does not attempt to connect to any price provider.
"""
from __future__ import annotations

import argparse
import json
from datetime import timedelta
from pathlib import Path
from research.forward_quality import records
from research.offline_backtest import InputError, PAIRS, decimal, timestamp

SCHEMA = "fx_forward_quote_continuity_v1"


def inspect(store: Path, *, asof_utc: str, max_gap_seconds: int = 300) -> dict:
    now = timestamp(asof_utc)
    if type(max_gap_seconds) is not int or not 1 <= max_gap_seconds <= 86400:
        raise InputError("invalid gap threshold")
    latest = {}
    previous = {}
    counts = {p: 0 for p in PAIRS}
    issues = {p: set() for p in PAIRS}
    gaps = {p: 0 for p in PAIRS}
    quote_hashes = {p: [] for p in PAIRS}
    for record in records(store):
        if timestamp(record["captured_at_utc"]) > now:
            raise InputError("journal contains future records")
        s = record["snapshot"]
        if s["kind"] != "PRICE_QUOTE":
            continue
        payload = s["payload"]
        pair = payload["pair"]
        if pair not in PAIRS or payload["source_status"] != "USER_SUPPLIED_UNVERIFIED":
            raise InputError("unauthorized quote identity")
        at = timestamp(s["observed_at_utc"])
        arrival = timestamp(record["captured_at_utc"])
        if arrival < at or arrival-at > timedelta(seconds=90):
            issues[pair].add("QUOTE_CAPTURE_DELAY")
        if at > now:
            raise InputError("future quote")
        bid = decimal(payload["bid"], "bid", positive=True)
        ask = decimal(payload["ask"], "ask", positive=True)
        if bid >= ask:
            raise InputError("crossed quote")
        counts[pair] += 1
        if pair in previous:
            old_at, old_bid, old_ask = previous[pair]
            if at <= old_at:
                issues[pair].add("DUPLICATE_OR_REVERSED_TICK_TIME")
            if (at-old_at).total_seconds() > max_gap_seconds:
                gaps[pair] += 1
                issues[pair].add("TICK_GAP_EXCEEDED")
            if bid == old_bid and ask == old_ask:
                issues[pair].add("REPEATED_BID_ASK_NOT_PROOF_OF_LIVE_FEED")
        previous[pair] = (at, bid, ask)
        latest[pair] = at
        quote_hashes[pair].append(record["record_sha256"])
    per_pair = {}
    for pair in PAIRS:
        age = (now-latest[pair]).total_seconds() if pair in latest else None
        if age is None or age > 90:
            issues[pair].add("MISSING_OR_STALE_LATEST_QUOTE")
        per_pair[pair] = {
            "quote_count": counts[pair],
            "gap_count": gaps[pair],
            "latest_quote_age_seconds": age,
            "blocking_reasons": sorted(issues[pair]),
            "latest_record_sha256": quote_hashes[pair][-1] if quote_hashes[pair] else None,
            "source_authenticated": False,
            "eligible_for_demo_or_live_execution": False,
        }
    return {
        "schema": SCHEMA, "status": "QUOTE_CONTINUITY_RESEARCH_NO_GO",
        "asof_utc": asof_utc,
        "by_pair": per_pair,
        "all_pairs_have_fresh_quotes": all(
            d["latest_quote_age_seconds"] is not None and
            d["latest_quote_age_seconds"] <= 90
            for d in per_pair.values()),
        "live_feed_connected": False,
        "provider_license_verified": False,
        "tick_server_time_verified": False,
        "demo_order_execution_enabled": False,
        "runtime_go_no_go": "NO_GO", "safety_hold_latched": True,
        "real_orders_permitted": False,
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Offline quote continuity; never orders")
    p.add_argument("--store", required=True, type=Path)
    p.add_argument("--asof-utc", required=True)
    p.add_argument("--max-gap-seconds", type=int, default=300)
    p.add_argument("--out", required=True, type=Path)
    a = p.parse_args(argv)
    try:
        if a.out.exists() or not a.out.parent.is_dir():
            raise InputError("existing output")
        result = inspect(a.store, asof_utc=a.asof_utc,
                         max_gap_seconds=a.max_gap_seconds)
        with a.out.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, indent=2, ensure_ascii=False)
        print(json.dumps({"status": result["status"],
                          "runtime_go_no_go": "NO_GO",
                          "real_orders_permitted": False}))
        return 0
    except (InputError, ValueError, TypeError, OSError, UnicodeError, ArithmeticError):
        print(json.dumps({"status": "FAIL_CLOSED",
                          "reason": "INVALID_QUOTE_CONTINUITY_DATA",
                          "runtime_go_no_go": "NO_GO",
                          "safety_hold_latched": True,
                          "real_orders_permitted": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
