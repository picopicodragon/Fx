"""FWD-024: offline scheduled macro-calendar revision and blackout audit.

Inputs are explicitly user-supplied, UNVERIFIED snapshots for BLS, Fed,
ECB or BoJ. This does not fetch sources, assess URL authenticity or trade.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from research.offline_backtest import InputError, timestamp

SCHEMA = "fx_forward_calendar_revision_v1"
SOURCE_KEYS = ("US_BLS", "US_FED", "EU_ECB", "JP_BOJ")
MAX_BYTES = 800000
MAX_EVENTS = 500


def validated(snapshot: dict) -> tuple[str, dict[str, str]]:
    if (type(snapshot) is not dict or
            snapshot.get("schema") != "fx_forward_schedule_snapshot_v1" or
            snapshot.get("source_key") not in SOURCE_KEYS or
            snapshot.get("source_status") != "PUBLISHED_SCHEDULE_UNVERIFIED" or
            snapshot.get("runtime_go_no_go") != "NO_GO" or
            snapshot.get("real_orders_permitted") is not False or
            snapshot.get("source_authenticity_verified") is not False or
            type(snapshot.get("events")) is not list or
            len(snapshot["events"]) > MAX_EVENTS):
        raise InputError("invalid unverified calendar")
    timestamp(snapshot.get("retrieved_at_utc"))
    events = {}
    for event in snapshot["events"]:
        if (type(event) is not dict or
                set(event) != {"title", "scheduled_at_utc", "source_url",
                               "source_status"} or
                type(event["title"]) is not str or
                not 1 <= len(event["title"]) <= 250 or
                type(event["source_url"]) is not str or
                not event["source_url"].startswith("https://") or
                event["source_status"] != "PUBLISHED_SCHEDULE_UNVERIFIED"):
            raise InputError("invalid calendar item")
        timestamp(event["scheduled_at_utc"])
        # Duplicate titles are ambiguous, don't infer which event changed.
        identity = (event["title"], event["source_url"])
        if identity in events:
            raise InputError("duplicate calendar identity")
        events[identity] = event["scheduled_at_utc"]
    return snapshot["source_key"], events


def compare(old: dict, new: dict) -> dict:
    old_source, before = validated(old)
    new_source, after = validated(new)
    if old_source != new_source or (
            timestamp(new["retrieved_at_utc"]) <=
            timestamp(old["retrieved_at_utc"])):
        raise InputError("wrong source or nonincreasing retrieval time")
    changed = []
    for identity in sorted(set(before) | set(after)):
        old_at, new_at = before.get(identity), after.get(identity)
        if old_at != new_at:
            changed.append({
                "title": identity[0], "source_url": identity[1],
                "previous_scheduled_at_utc": old_at,
                "current_scheduled_at_utc": new_at,
                "change": ("NEW" if old_at is None else
                           "MISSING" if new_at is None else "RESCHEDULED"),
            })
    return {
        "schema": SCHEMA, "status": "CALENDAR_REVISION_RESEARCH_NO_GO",
        "source_key": old_source,
        "previous_retrieved_at_utc": old["retrieved_at_utc"],
        "current_retrieved_at_utc": new["retrieved_at_utc"],
        "change_count": len(changed),
        "changes": changed,
        "missing_events_are_not_confirmed_cancellations": True,
        "schedule_source_authenticated": False,
        "calendar_complete": False,
        "demo_order_execution_enabled": False,
        "runtime_go_no_go": "NO_GO", "safety_hold_latched": True,
        "real_orders_permitted": False,
    }


def _read(path: Path) -> dict:
    if not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise InputError("oversized calendar")
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if type(data) is not dict:
        raise InputError("calendar is not object")
    return data


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Offline official-schedule snapshot diff, no orders")
    p.add_argument("--previous", type=Path, required=True)
    p.add_argument("--current", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args(argv)
    try:
        if args.out.exists() or not args.out.parent.is_dir():
            raise InputError("output collision")
        report = compare(_read(args.previous), _read(args.current))
        with args.out.open("x", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(json.dumps({"status": report["status"],
                          "change_count": report["change_count"],
                          "runtime_go_no_go": "NO_GO",
                          "real_orders_permitted": False}))
        return 0
    except (InputError, TypeError, ValueError, KeyError, OSError, UnicodeError):
        print(json.dumps({"status": "FAIL_CLOSED",
                          "reason": "CALENDAR_REVISION_EVIDENCE_INVALID",
                          "runtime_go_no_go": "NO_GO",
                          "safety_hold_latched": True,
                          "real_orders_permitted": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
