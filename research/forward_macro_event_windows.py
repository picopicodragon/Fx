"""FWD-205..212: advisory BLS release time windows, strictly offline.

A local ICS-derived report is self-reported evidence, NOT an authoritative,
complete FX event calendar. The 15-minute intervals describe research-only
blackouts; they cannot enable trading or authorize resumption.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import timedelta
from pathlib import Path

from research.forward_bls_calendar import URL
from research.offline_backtest import InputError, timestamp

SCHEMA = "fx_fwd_macro_event_windows_v1"
PAIRS = ("USD/JPY", "EUR/JPY", "EUR/USD")
FINGERPRINT = re.compile(r"^[0-9a-f]{64}$")
EVENT_KEYS = frozenset(("title", "scheduled_at_utc",
                        "source_url", "source_status"))
MAX_INPUT = 160_000


def inspect(calendar: dict, *, asof_utc: str) -> dict:
    now = timestamp(asof_utc)
    if (type(calendar) is not dict
            or calendar.get("status") != "BLS_CALENDAR_RESEARCH_ONLY_NO_GO"
            or calendar.get("runtime_go_no_go") != "NO_GO"
            or calendar.get("safety_hold_latched") is not True
            or calendar.get("real_orders_permitted") is not False
            or calendar.get("source_url") != URL
            or calendar.get("source_authenticity_verified") is not False
            or calendar.get("calendar_covers_all_fx_events") is not False
            or type(calendar.get("calendar_sha256")) is not str
            or not FINGERPRINT.fullmatch(calendar["calendar_sha256"])
            or type(calendar.get("events")) is not list
            or type(calendar.get("event_count")) is not int
            or len(calendar["events"]) != calendar["event_count"]
            or len(calendar["events"]) > 500):
        raise InputError("calendar report lacks safe research provenance")
    sampled = timestamp(calendar["asof_utc"])
    if now < sampled:
        raise InputError("future calendar snapshot")
    if (type(calendar.get("horizon_days")) is not int
            or not 1 <= calendar["horizon_days"] <= 31):
        raise InputError("invalid calendar coverage window")
    stale = now - sampled > timedelta(hours=24)
    holds = {
        "CALENDAR_SOURCE_NOT_INDEPENDENTLY_ATTESTED",
        "BLS_CALENDAR_NOT_COMPLETE_FX_EVENT_COVERAGE",
        "EVENT_BLACKOUT_NOT_BROKER_TRADING_PERMISSION",
        "CLOCK_AND_MARKET_SAFETY_NOT_ATTESTED",
    }
    if stale:
        holds.add("CALENDAR_SNAPSHOT_OLDER_THAN_24H")
    if not calendar["events"]:
        holds.add("NO_EVENTS_IN_THIS_BLS_CALENDAR_SNAPSHOT")
    windows = []
    seen = set()
    for entry in calendar["events"]:
        if (type(entry) is not dict or set(entry) != EVENT_KEYS
                or type(entry["title"]) is not str
                or not 1 <= len(entry["title"]) <= 250
                or not entry["title"].strip()
                or entry["source_url"] != URL
                or entry["source_status"] != "PUBLISHED_SCHEDULE_UNVERIFIED"):
            raise InputError("invalid calendar event record")
        starts = timestamp(entry["scheduled_at_utc"])
        # A parsed official-calendar snapshot cannot be enlarged arbitrarily
        # by inserting claimed events outside its window.
        if (starts < sampled - timedelta(minutes=15)
                or starts > sampled + timedelta(days=calendar["horizon_days"])):
            raise InputError("event outside calendar snapshot horizon")
        unique = (entry["title"], entry["scheduled_at_utc"])
        if unique in seen:
            raise InputError("duplicate event time/title")
        seen.add(unique)
        before = starts - timedelta(minutes=15)
        after = starts + timedelta(minutes=15)
        state = ("BEFORE_RESEARCH_BLACKOUT" if now < before
                 else "WITHIN_RESEARCH_BLACKOUT" if now < after
                 else "AFTER_EVENT_REQUIRES_INDEPENDENT_REASSESSMENT")
        if now >= before and now < after:
            holds.add("SCHEDULED_BLS_RELEASE_RESEARCH_BLACKOUT_ACTIVE")
        windows.append({
            "title_unverified": entry["title"],
            "scheduled_at_utc_unverified": entry["scheduled_at_utc"],
            "blackout_start_utc": before.isoformat().replace("+00:00", "Z"),
            "blackout_end_utc": after.isoformat().replace("+00:00", "Z"),
            "research_state": state,
            # Conservative coverage only; this is not Q23/Q24 live logic.
            "all_three_pairs_research_advisory_only": list(PAIRS),
            "new_orders_permitted": False,
            "automatic_resume_authorized": False,
        })
    return {
        "schema": SCHEMA,
        "status": "BLS_MACRO_WINDOWS_RESEARCH_HOLD_NO_GO",
        "asof_utc": asof_utc,
        "calendar_sha256_self_reported": calendar["calendar_sha256"],
        "snapshot_asof_utc": calendar["asof_utc"],
        "calendar_stale": stale,
        "windows": windows,
        "active_research_blackout_count": sum(
            e["research_state"] == "WITHIN_RESEARCH_BLACKOUT"
            for e in windows),
        "data_holds": sorted(holds),
        "calendar_completeness_proven": False,
        "market_event_stop_operational": False,
        "source_clock_attested": False,
        "broker_orders_sent": 0,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
        "real_orders_permitted": False,
        "demo_orders_permitted": False,
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Offline advisory macro windows")
    p.add_argument("--calendar-report", type=Path, required=True)
    p.add_argument("--asof-utc", required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args(argv)
    try:
        if (not a.calendar_report.is_file()
                or a.calendar_report.is_symlink()
                or a.calendar_report.stat().st_size > MAX_INPUT
                or a.out.exists() or a.out.is_symlink()
                or not a.out.parent.is_dir()):
            raise InputError("unsafe macro calendar input/output")
        data = json.loads(a.calendar_report.read_text("utf-8-sig"))
        report = inspect(data, asof_utc=a.asof_utc)
        with a.out.open("x", encoding="utf-8") as output:
            json.dump(report, output, ensure_ascii=False, indent=2)
        print(json.dumps({
            "status": report["status"],
            "event_count": len(report["windows"]),
            "active_research_blackout_count":
                report["active_research_blackout_count"],
            "calendar_stale": report["calendar_stale"],
            "runtime_go_no_go": "NO_GO", "real_orders_permitted": False,
        }))
        return 0
    except (InputError, OSError, ValueError, TypeError,
            KeyError, UnicodeError, ArithmeticError, OverflowError):
        print(json.dumps({
            "status": "FAIL_CLOSED",
            "reason": "MACRO_EVENT_SCHEDULE_UNVERIFIED",
            "runtime_go_no_go": "NO_GO",
            "safety_hold_latched": True,
            "real_orders_permitted": False,
        }))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
