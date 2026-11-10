"""FWD-018/019/020: offline forward health and scheduled-event coverage.

Consumes verified LOCAL research reports and bounded externally prepared
snapshots. No HTTP, MT4, paid AI, orders or schedule registration.
A healthy-looking report can NEVER authorize broker or demo execution.
"""
from __future__ import annotations

import argparse
import json
from datetime import timedelta
from pathlib import Path

from research.offline_backtest import InputError, PAIRS, timestamp

SCHEMA = "fx_forward_observability_v1"
MAX_BYTES = 800_000
MAX_GAP = 300
MAX_QUOTE_AGE = 90
SCHEDULE_AGE = 86400
BLACKOUT = 900
EVENT_LIMIT = 500
PAIRS_SET = frozenset(PAIRS)


def _require_research(obj: dict, status: str) -> None:
    if (type(obj) is not dict or obj.get("status") != status or
            obj.get("runtime_go_no_go") != "NO_GO" or
            obj.get("safety_hold_latched") is not True or
            obj.get("real_orders_permitted") is not False):
        raise InputError("untrusted research report")


def observe(multicycle: dict, *, asof_utc: str,
            schedules: list[dict] | None = None) -> dict:
    """Only report problems; never infer execution eligibility."""
    now = timestamp(asof_utc)
    _require_research(multicycle, "FORWARD_MULTICYCLE_RESEARCH_HOLD_NO_GO")
    cycles = multicycle.get("cycles")
    if type(cycles) is not list or not cycles or len(cycles) > 5000:
        raise InputError("missing cycle series")
    reasons = set()
    prev = None
    previous_count = None
    stale_cycles = []
    for index, cycle in enumerate(cycles):
        if type(cycle) is not dict or set(cycle) != {
                "cycle_id", "asof_utc", "observation_count",
                "quality_sha256", "paper_sha256",
                "hypothetical_pnl_jpy", "hypothetical_equity_jpy"}:
            raise InputError("invalid cycle evidence")
        t = timestamp(cycle["asof_utc"])
        count = cycle["observation_count"]
        if type(count) is not int or count < 0:
            raise InputError("invalid observation count")
        if prev is not None and t <= prev:
            raise InputError("reversed cycle timestamp")
        if previous_count is not None and count < previous_count:
            raise InputError("observation rollback")
        if prev is not None and (t-prev).total_seconds() > MAX_GAP:
            stale_cycles.append(index+1)
        prev, previous_count = t, count
    latest_age = (now-prev).total_seconds()
    if latest_age < 0:
        raise InputError("future cycle")
    if latest_age > MAX_GAP:
        reasons.add("SHADOW_CYCLE_NOT_RECENT")
    if stale_cycles:
        reasons.add("SHADOW_CYCLE_GAPS")
    if multicycle.get("cycle_count") != len(cycles):
        raise InputError("cycle count mismatch")
    risk = multicycle.get("risk_timeline")
    if (type(risk) is not dict or
            risk.get("status") != "HYPOTHETICAL_RISK_MONITOR_NO_GO" or
            risk.get("real_orders_permitted") is not False or
            risk.get("safety_hold_latched") is not True):
        raise InputError("invalid risk report")
    if any(risk.get(key) is True for key in (
            "hypothetical_dd_level3_latched",
            "hypothetical_dd_hard_stop_latched",
            "hypothetical_daily_loss_latched",
            "hypothetical_concurrent_risk_violated")):
        reasons.add("SHADOW_RISK_LATCH")
    if type(multicycle.get("blocking_reasons")) is not list:
        raise InputError("missing prior blockers")
    if multicycle["blocking_reasons"]:
        reasons.add("PRIOR_RESEARCH_BLOCKERS")
    schedule_reports = schedules if schedules is not None else []
    if type(schedule_reports) is not list or len(schedule_reports) > 10:
        raise InputError("invalid schedule collection")
    coverage = {"US_BLS": False, "US_FED": False,
                "EU_ECB": False, "JP_BOJ": False}
    imminent = []
    if not schedule_reports:
        reasons.add("NO_FUTURE_SCHEDULE_SNAPSHOT")
    seen = set()
    for snapshot in schedule_reports:
        if type(snapshot) is not dict:
            raise InputError("invalid schedule snapshot")
        source = snapshot.get("source_key")
        if source not in coverage or source in seen:
            raise InputError("unknown or repeated calendar source")
        seen.add(source)
        if (snapshot.get("schema") != "fx_forward_schedule_snapshot_v1" or
                snapshot.get("source_status") != "PUBLISHED_SCHEDULE_UNVERIFIED" or
                snapshot.get("runtime_go_no_go") != "NO_GO" or
                snapshot.get("real_orders_permitted") is not False or
                snapshot.get("source_authenticity_verified") is not False or
                type(snapshot.get("events")) is not list or
                len(snapshot["events"]) > EVENT_LIMIT):
            raise InputError("unsafe schedule snapshot")
        stamp = timestamp(snapshot.get("retrieved_at_utc"))
        age = (now-stamp).total_seconds()
        if age < 0:
            raise InputError("future schedule snapshot")
        if age > SCHEDULE_AGE:
            reasons.add("STALE_SCHEDULE_" + source)
            continue
        coverage[source] = True  # available observation, NOT verified coverage
        for event in snapshot["events"]:
            if (type(event) is not dict or
                    set(event) != {"title", "scheduled_at_utc",
                                   "source_url", "source_status"} or
                    type(event["title"]) is not str or
                    not 1 <= len(event["title"]) <= 250 or
                    type(event["source_url"]) is not str or
                    not event["source_url"].startswith("https://") or
                    event["source_status"] != "PUBLISHED_SCHEDULE_UNVERIFIED"):
                raise InputError("invalid calendar event")
            at = timestamp(event["scheduled_at_utc"])
            if abs((at-now).total_seconds()) <= BLACKOUT:
                imminent.append({"source_key": source,
                                 "scheduled_at_utc": event["scheduled_at_utc"]})
    if not all(coverage.values()):
        reasons.add("PARTIAL_ECONOMIC_CALENDAR")
    if imminent:
        reasons.add("SCHEDULED_EVENT_BLACKOUT")
    # Never use source presence, completed data or a high score as GO.
    reasons.update(("DATA_LICENSE_NOT_VERIFIED",
                    "SOURCE_AUTHENTICITY_NOT_ATTESTED",
                    "BROKER_CONNECTION_NOT_AUTHENTICATED",
                    "INDEPENDENT_CLOCK_NOT_ATTESTED"))
    return {
        "schema": SCHEMA, "status": "FORWARD_OBSERVABILITY_HOLD_NO_GO",
        "asof_utc": asof_utc, "cycle_count": len(cycles),
        "latest_cycle_age_seconds": latest_age,
        "gap_cycle_indexes": stale_cycles,
        "schedule_sources_observed_not_verified": coverage,
        "imminent_scheduled_events": imminent[:100],
        "blocking_reasons": sorted(reasons),
        "data_feed_connected": False,
        "economic_calendar_coverage_verified": False,
        "mt4_demo_authenticated": False,
        "demo_order_execution_enabled": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
        "real_orders_permitted": False,
    }


def _bounded(path: Path) -> dict:
    if not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise InputError("missing or oversized report")
    result = json.loads(path.read_text(encoding="utf-8-sig"))
    if type(result) is not dict:
        raise InputError("invalid report")
    return result


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Read-only FWD-018/020 health report, NO_GO")
    p.add_argument("--multicycle", required=True, type=Path)
    p.add_argument("--asof-utc", required=True)
    p.add_argument("--schedule", action="append", type=Path, default=[])
    p.add_argument("--out", required=True, type=Path)
    args = p.parse_args(argv)
    try:
        if args.out.exists() or not args.out.parent.is_dir():
            raise InputError("output already exists")
        result = observe(_bounded(args.multicycle),
                         asof_utc=args.asof_utc,
                         schedules=[_bounded(p) for p in args.schedule])
        with args.out.open("x", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(json.dumps({"status": result["status"],
                          "blocking_reasons": result["blocking_reasons"],
                          "runtime_go_no_go": "NO_GO",
                          "real_orders_permitted": False}))
        return 0
    except (InputError, ValueError, OSError, TypeError, KeyError, UnicodeError):
        print(json.dumps({"status": "FAIL_CLOSED",
                          "reason": "INVALID_FORWARD_OBSERVABILITY_INPUT",
                          "runtime_go_no_go": "NO_GO",
                          "safety_hold_latched": True,
                          "real_orders_permitted": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
