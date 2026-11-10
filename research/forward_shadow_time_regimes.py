"""FWD-119..125: offline time-of-observation quality stratification.

Buckets use observer-supplied PC TimeGMT, NOT independently attested UTC.
Counts and spread percentiles are research descriptions, never tradability.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

from research.forward_mt4_multisession_reliability import (
    inspect as inspect_sessions, _parse_labeled_entries
)
from research.forward_mt4_v2_quote import parse
from research.forward_shadow_quote_quality import PIP
from research.offline_backtest import InputError, timestamp

SCHEMA = "fx_fwd_time_stratified_quote_quality_v1"
MAX_HOUR_BUCKETS = 24


def inspect(sessions: list[tuple[str, Path]], *, asof_utc: str) -> dict:
    summary = inspect_sessions(sessions, asof_utc=asof_utc)
    buckets: dict[tuple[str, str], list[tuple[Decimal, int]]] = defaultdict(list)
    per_session: dict[str, dict] = {}
    for label, directory in sessions:
        pair_hours = defaultdict(set)
        for path in sorted(directory.iterdir()):
            # inspect_sessions validates paths and CSV content before this loop.
            raw = path.read_bytes()
            try:
                table = list(csv.DictReader(
                    io.StringIO(raw.decode("utf-8-sig")), strict=True))
            except (UnicodeError, csv.Error) as exc:
                raise InputError("invalid time stratification CSV") from exc
            if len(table) != 1:
                raise InputError("unexpected stratification row count")
            when = table[0]["observed_at_utc"]
            sample = parse(raw, asof_utc=when)
            pair = sample["pair"]
            hour = timestamp(when).strftime("%H")
            spread = ((Decimal(sample["ask"]) - Decimal(sample["bid"]))
                      / PIP[pair])
            if spread <= 0:
                raise InputError("invalid quote spread")
            buckets[(pair, hour)].append((
                spread, sample["server_relative_tick_age_seconds"]))
            pair_hours[pair].add(hour)
        per_session[label] = {
            pair: sorted(pair_hours[pair]) for pair in PIP
        }

    by_pair = {}
    limitations = set(summary["issues_and_safety_holds"])
    for pair in PIP:
        hour_entries = {}
        hours = sorted(key[1] for key in buckets if key[0] == pair)
        if len(hours) < 3:
            limitations.add("INSUFFICIENT_TIME_OF_DAY_COVERAGE")
        for hour in hours:
            samples = buckets[(pair, hour)]
            spreads = sorted(record[0] for record in samples)
            n = len(spreads)
            p95 = spreads[(95*n+99)//100 - 1]
            hour_entries[hour] = {
                "samples": n,
                "spread_min_pips": str(spreads[0]),
                "spread_p95_pips": str(p95),
                "spread_max_pips": str(spreads[-1]),
                "server_relative_tick_age_max_seconds":
                    max(x[1] for x in samples),
            }
        by_pair[pair] = hour_entries
    return {
        "schema": SCHEMA,
        "status": "TIME_STRATIFIED_QUOTE_RESEARCH_HOLD_NO_GO",
        "clock_basis": "UNATTESTED_OBSERVER_PC_TIMEGMT_UTC_HOUR",
        "asof_utc": asof_utc,
        "session_count": summary["session_count"],
        "csv_file_count": summary["csv_file_count"],
        "complete_cycle_count": summary["complete_cycle_count"],
        "per_session_pair_observed_utc_hours": per_session,
        "per_pair_utc_hour": by_pair,
        "coverage_and_safety_holds": sorted(limitations),
        "cross_market_time_coverage_established": False,
        "broker_time_attested": False,
        "strategy_profitability_inferred": False,
        "demo_orders_permitted": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
        "real_orders_permitted": False,
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Stratify copied MT4 DEMO prices; NO_GO")
    p.add_argument("--session", action="append", required=True)
    p.add_argument("--asof-utc", required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args(argv)
    try:
        sessions = list(_parse_labeled_entries(
            args.session, "--session").items())
        if (args.out.exists() or args.out.is_symlink()
                or not args.out.parent.is_dir()
                or any(folder.resolve() in args.out.resolve().parents
                       for _, folder in sessions)):
            raise InputError("unsafe output")
        result = inspect(sessions, asof_utc=args.asof_utc)
        with args.out.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, indent=2, ensure_ascii=False)
        print(json.dumps({
            "status": result["status"],
            "files": result["csv_file_count"],
            "complete_cycles": result["complete_cycle_count"],
            "coverage_and_safety_holds":
                result["coverage_and_safety_holds"],
            "runtime_go_no_go": "NO_GO", "real_orders_permitted": False,
        }))
        return 0
    except (InputError, OSError, TypeError, KeyError, ValueError,
            UnicodeError, ArithmeticError, OverflowError):
        print(json.dumps({
            "status": "FAIL_CLOSED",
            "reason": "TIME_STRATIFICATION_INPUT_UNVERIFIED",
            "runtime_go_no_go": "NO_GO",
            "safety_hold_latched": True,
            "real_orders_permitted": False,
        }))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
