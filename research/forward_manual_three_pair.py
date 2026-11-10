"""FWD-045/046: inspect three immutable manual quote handoffs.

Local evidence only. Never computes broker-executable risk or authorizes
orders. Operator separately selects folders for the three supported pairs.
"""
from __future__ import annotations

import argparse
import json
from datetime import timedelta
from pathlib import Path

from research.forward_manual_handoff import verify_capture
from research.offline_backtest import InputError, PAIRS, timestamp

SCHEMA = "fx_forward_manual_three_pair_audit_v1"
MAX_AGE_SECONDS = 90


def audit(folders: list[Path], *, asof_utc: str) -> dict:
    now = timestamp(asof_utc)
    if type(folders) is not list or not 1 <= len(folders) <= 3:
        raise InputError("one to three independent capture directories required")
    pair_rows = {}
    ids = set()
    for folder in folders:
        report = verify_capture(folder)
        pair = report["pair"]
        cid = report["capture_id"]
        if pair in pair_rows or cid in ids:
            raise InputError("duplicate pair or capture ID")
        ids.add(cid)
        captured = timestamp(report["asof_utc"])
        observed = timestamp(report["observed_at_utc"])
        if captured > now:
            raise InputError("future evidence capture")
        age = (now - observed).total_seconds()
        if age < 0:
            raise InputError("future quote")
        pair_rows[pair] = {
            "capture_id": cid,
            "observed_at_utc": report["observed_at_utc"],
            "capture_asof_utc": report["asof_utc"],
            "quote_age_seconds": age,
            "csv_sha256": report["csv_sha256"],
            "research_quote_fresh": age <= MAX_AGE_SECONDS,
            "independent_broker_quote_authenticated": False,
        }
    blockers = []
    for pair in PAIRS:
        if pair not in pair_rows:
            blockers.append("MISSING_" + pair.replace("/", "_"))
        elif not pair_rows[pair]["research_quote_fresh"]:
            blockers.append("STALE_" + pair.replace("/", "_"))
    blockers.extend((
        "MT4_DEMO_IDENTITY_NOT_INDEPENDENTLY_VERIFIED",
        "QUOTE_SERVER_CLOCK_NOT_ATTESTED",
        "SPREAD_AND_LIQUIDITY_NOT_CERTIFIED",
        "ECONOMIC_CALENDAR_AND_RISK_ENGINE_NOT_CERTIFIED",
    ))
    return {
        "schema": SCHEMA, "status": "MANUAL_THREE_PAIR_RESEARCH_HOLD_NO_GO",
        "asof_utc": asof_utc,
        "capture_count": len(pair_rows),
        "supported_pairs": list(PAIRS),
        "by_pair": pair_rows,
        "blocking_reasons": sorted(blockers),
        "source_system_operated_by_this_program": False,
        "mt4_connected": False,
        "automatic_collection_started": False,
        "demo_order_execution_enabled": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
        "real_orders_permitted": False,
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Audit local manually supplied MT4 quotes")
    p.add_argument("--capture-dir", action="append", type=Path, required=True)
    p.add_argument("--asof-utc", required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args(argv)
    try:
        if args.out.exists() or not args.out.parent.is_dir():
            raise InputError("out path exists")
        report = audit(args.capture_dir, asof_utc=args.asof_utc)
        with args.out.open("x", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(json.dumps({
            "status": report["status"],
            "capture_count": report["capture_count"],
            "blocking_reasons": report["blocking_reasons"],
            "runtime_go_no_go": "NO_GO",
            "real_orders_permitted": False}))
        return 0
    except (InputError, OSError, TypeError, ValueError, KeyError,
            UnicodeError, ArithmeticError):
        print(json.dumps({
            "status": "FAIL_CLOSED",
            "reason": "INVALID_MANUAL_THREE_PAIR_EVIDENCE",
            "runtime_go_no_go": "NO_GO",
            "safety_hold_latched": True,
            "real_orders_permitted": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
