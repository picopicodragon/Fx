"""FWD-025/026: aggregate offline shadow health with monotonic-outage latch.

This state is RESEARCH-ONLY, not a live watchdog. Uses snapshots supplied
locally, never starts a daemon, queries brokers, or re-enables orders.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from research.offline_backtest import InputError, timestamp

SCHEMA = "fx_forward_shadow_watch_v1"
MAX_BYTES = 1_000_000
FIRST_ALERT_SECONDS = 60
SECOND_ALERT_SECONDS = 600


def evaluate(observability: dict, quote: dict, *,
             asof_utc: str, prior: dict | None = None) -> dict:
    now = timestamp(asof_utc)
    if (type(observability) is not dict or
            observability.get("status") != "FORWARD_OBSERVABILITY_HOLD_NO_GO" or
            observability.get("runtime_go_no_go") != "NO_GO" or
            observability.get("real_orders_permitted") is not False or
            observability.get("safety_hold_latched") is not True or
            type(quote) is not dict or
            quote.get("status") != "QUOTE_CONTINUITY_RESEARCH_NO_GO" or
            quote.get("runtime_go_no_go") != "NO_GO" or
            quote.get("real_orders_permitted") is not False or
            quote.get("safety_hold_latched") is not True):
        raise InputError("unsafe observer inputs")
    for source in (observability, quote):
        t = timestamp(source.get("asof_utc"))
        if t > now:
            raise InputError("future evidence")
    prior_latched = False
    previous_time = None
    if prior is not None:
        if (type(prior) is not dict or
                prior.get("schema") != SCHEMA or
                prior.get("status") != "FORWARD_SHADOW_WATCH_HOLD_NO_GO" or
                prior.get("runtime_go_no_go") != "NO_GO" or
                prior.get("real_orders_permitted") is not False or
                prior.get("safety_hold_latched") is not True or
                type(prior.get("watchdog_latched")) is not bool):
            raise InputError("untrusted previous watchdog")
        previous_time = timestamp(prior.get("asof_utc"))
        if now <= previous_time:
            raise InputError("stale or reversed watchdog state")
        prior_latched = prior["watchdog_latched"]
    obs_gap = (now-timestamp(observability["asof_utc"])).total_seconds()
    quote_gap = (now-timestamp(quote["asof_utc"])).total_seconds()
    latest_cycle_age = observability.get("latest_cycle_age_seconds")
    if (type(latest_cycle_age) not in (int, float)
            or not math.isfinite(latest_cycle_age)
            or latest_cycle_age < 0):
        raise InputError("invalid cycle age")
    ages = [obs_gap, quote_gap, obs_gap+latest_cycle_age]
    # Individual last tick freshness may differ; account for all three pairs.
    by_pair = quote.get("by_pair")
    if type(by_pair) is not dict or set(by_pair) != {
            "USD/JPY", "EUR/JPY", "EUR/USD"}:
        raise InputError("incomplete quote matrix")
    for row in by_pair.values():
        if type(row) is not dict:
            raise InputError("invalid quote row")
        age = row.get("latest_quote_age_seconds")
        if age is None:
            ages.append(SECOND_ALERT_SECONDS)
        elif (type(age) not in (int, float)
              or not math.isfinite(age) or age < 0):
            raise InputError("invalid quote age")
        else:
            ages.append(quote_gap+age)
    max_age = max(ages)
    if max_age >= SECOND_ALERT_SECONDS:
        level = "LEVEL2"
    elif max_age >= FIRST_ALERT_SECONDS:
        level = "LEVEL1"
    else:
        level = "NONE"
    latch = prior_latched or level != "NONE" or bool(
        observability.get("blocking_reasons")) or any(
            row.get("blocking_reasons") for row in by_pair.values())
    reasons = []
    if level != "NONE":
        reasons.append("OBSERVATION_INTERRUPTED_" + level)
    if prior_latched:
        reasons.append("PREVIOUS_WATCHDOG_LATCH_NOT_CLEARED")
    if observability.get("blocking_reasons"):
        reasons.append("OBSERVABILITY_HOLDS")
    if any(row.get("blocking_reasons") for row in by_pair.values()):
        reasons.append("QUOTE_QUALITY_HOLDS")
    return {
        "schema": SCHEMA, "status": "FORWARD_SHADOW_WATCH_HOLD_NO_GO",
        "asof_utc": asof_utc,
        "interruption_seconds": max_age,
        "interruption_level": level,
        "watchdog_latched": bool(latch),
        "blocking_reasons": sorted(reasons),
        "resume_automatically_permitted": False,
        "human_approval_recorded": False,
        "independent_watchdog_running": False,
        "bidirectional_mt4_heartbeat_verified": False,
        "external_alerts_sent": False,
        "demo_order_execution_enabled": False,
        "demo_orders_permitted": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
        "real_orders_permitted": False,
    }


def _read(path: Path) -> dict:
    if not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise InputError("report not found or oversized")
    v = json.loads(path.read_text(encoding="utf-8-sig"))
    if type(v) is not dict:
        raise InputError("invalid report")
    return v


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="One-shot offline shadow watchdog simulation")
    p.add_argument("--observability", required=True, type=Path)
    p.add_argument("--quote", required=True, type=Path)
    p.add_argument("--prior", type=Path)
    p.add_argument("--asof-utc", required=True)
    p.add_argument("--out", required=True, type=Path)
    a = p.parse_args(argv)
    try:
        if a.out.exists() or not a.out.parent.is_dir():
            raise InputError("output already exists")
        report = evaluate(_read(a.observability), _read(a.quote),
                          asof_utc=a.asof_utc,
                          prior=_read(a.prior) if a.prior else None)
        with a.out.open("x", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(json.dumps({"status": report["status"],
                          "interruption_level": report["interruption_level"],
                          "runtime_go_no_go": "NO_GO",
                          "real_orders_permitted": False}))
        return 0
    except (InputError, TypeError, KeyError, ValueError, OSError, UnicodeError):
        print(json.dumps({"status": "FAIL_CLOSED",
                          "reason": "FORWARD_SHADOW_WATCH_INVALID",
                          "runtime_go_no_go": "NO_GO",
                          "safety_hold_latched": True,
                          "real_orders_permitted": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
