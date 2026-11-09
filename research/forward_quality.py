"""FX-FWD-002/003: deterministic, offline quality and timing checks.

The source of truth is an already-recorded forward_observation journal.
Does NOT download quotes, query calendars, run MT4, call paid APIs, or trade.
"""
from __future__ import annotations

import argparse
import json
from datetime import timedelta
from pathlib import Path

from research import forward_observation as observation
from research.offline_backtest import InputError, PAIRS, timestamp

MAX_QUOTE_AGE_SECONDS = 90
MAX_REPORTING_DELAY_SECONDS = 300
EVENT_BLACKOUT_SECONDS = 900


def records(store: Path) -> list[dict]:
    """Read only after verifying the entire chain and referential integrity."""
    result = observation.audit(store)
    if result["runtime_go_no_go"] != "NO_GO":
        raise InputError("unsafe record audit")
    return [json.loads(
        (store / f"{i:08d}.json").read_text(encoding="utf-8"))
        for i in range(1, result["record_count"] + 1)]


def quality_report(store: Path, *, asof_utc: str) -> dict:
    now = timestamp(asof_utc)
    entries = records(store)
    last_quotes = {}
    events = []
    age_issues = []
    out_of_order_sources = []
    last_observed = {}
    latest_captured = None
    verified_clock = False  # No independent NTP attestation.
    for row in entries:
        s = row["snapshot"]
        pair = s["payload"]["pair"]
        observed = timestamp(s["observed_at_utc"])
        captured = timestamp(row["captured_at_utc"])
        if captured > now + timedelta(seconds=5):
            raise InputError("analysis time before completed evidence")
        if observed > captured + timedelta(seconds=5):
            raise InputError("future observation")
        source_key = (s["source_id"], pair, s["kind"])
        if source_key in last_observed and observed < last_observed[source_key]:
            out_of_order_sources.append(row["sequence"])
        last_observed[source_key] = observed
        delay = (captured - observed).total_seconds()
        if delay > MAX_REPORTING_DELAY_SECONDS:
            age_issues.append(row["sequence"])
        latest_captured = captured
        if s["kind"] == "PRICE_QUOTE":
            previous = last_quotes.get(pair)
            if previous is None or observed >= previous[0]:
                last_quotes[pair] = (observed, row)
        elif s["kind"] == "MACRO_EVENT":
            events.append({
                "record_sha256": row["record_sha256"],
                "pair": pair,
                "observed_at_utc": s["observed_at_utc"],
                "published_at_utc": s["payload"]["published_at_utc"],
                "consensus_missing": not bool(s["payload"]["consensus"].strip()),
                "source_provenance": "UNVERIFIED",
            })
    per_pair = {}
    for pair in PAIRS:
        quote = last_quotes.get(pair)
        age = (now - quote[0]).total_seconds() if quote else None
        fresh = age is not None and 0 <= age <= MAX_QUOTE_AGE_SECONDS
        # Past event blackout only: no future economic calendar connection
        # exists. Thus future event blackout cannot be guaranteed.
        near_event = any(
            event["pair"] == pair and
            abs((now - timestamp(event["published_at_utc"]))
                .total_seconds()) <= EVENT_BLACKOUT_SECONDS
            for event in events)
        per_pair[pair] = {
            "latest_quote_sequence": quote[1]["sequence"] if quote else None,
            "quote_age_seconds": age,
            "quote_fresh": fresh,
            "event_blackout_observed": near_event,
            "future_calendar_coverage_verified": False,
            "operational_feed_quality_verified": False,
            "eligible_for_live_or_demo_order": False,
        }
    return {
        "status": "FORWARD_QUALITY_RESEARCH_ONLY_NO_GO",
        "schema": "fx_forward_quality_v1",
        "runtime_go_no_go": "NO_GO", "safety_hold_latched": True,
        "real_orders_permitted": False,
        "mt4_order_execution_enabled": False,
        "asof_utc": asof_utc,
        "record_count": len(entries),
        "observed_macro_event_count": len(events),
        "macro_events_missing_consensus": sum(
            e["consensus_missing"] for e in events),
        "macro_events": events,
        "late_capture_sequences": age_issues,
        "out_of_order_source_sequences": out_of_order_sources,
        "capture_clock_independently_verified": verified_clock,
        "current_asof_quote_freshness": per_pair,
        "source_authenticity_verified": False,
        "data_license_verified": False,
        "full_economic_calendar_coverage_verified": False,
        "ai_reviewer_quality_verified": False,
        "simulation_eligibility": (
            "LOCAL_HYPOTHETICAL_ONLY"
            if not age_issues and not out_of_order_sources
            else "INPUT_QUALITY_HOLD"),
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Offline FX forward quality report")
    p.add_argument("--store", required=True, type=Path)
    p.add_argument("--asof-utc", required=True)
    p.add_argument("--out", required=True, type=Path)
    args = p.parse_args(argv)
    try:
        timestamp(args.asof_utc)
        if args.out.exists() or not args.out.parent.is_dir():
            raise InputError("existing output or invalid parent")
        result = quality_report(args.store, asof_utc=args.asof_utc)
        with args.out.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, indent=2, ensure_ascii=False)
        print(json.dumps({
            "status": result["status"],
            "record_count": result["record_count"],
            "macro_events_missing_consensus":
                result["macro_events_missing_consensus"],
            "runtime_go_no_go": "NO_GO",
            "real_orders_permitted": False}))
        return 0
    except (InputError, OSError, TypeError, ValueError,
            UnicodeError, ArithmeticError):
        print(json.dumps({
            "status": "FAIL_CLOSED",
            "reason": "FORWARD_QUALITY_INVALID_OR_UNVERIFIED",
            "runtime_go_no_go": "NO_GO",
            "safety_hold_latched": True,
            "real_orders_permitted": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
