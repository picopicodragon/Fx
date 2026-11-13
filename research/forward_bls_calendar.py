"""FX-FWD-002B: bounded read-only BLS public release calendar snapshot.

Public ICS helps identify *some* scheduled events in advance, not all FX
events. No independent source attestation, trading permission, or guarantee
of a timely release. Network is opt-in, fixed HTTPS URL only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from research.offline_backtest import InputError, timestamp

URL = "https://www.bls.gov/schedule/news_release/bls.ics"
MAX_ICS_BYTES = 350_000
MAX_EVENTS = 500
TZ = ZoneInfo("America/New_York")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise InputError("BLS schedule redirect not allowlisted")


def download(*, opener=None) -> bytes:
    request = urllib.request.Request(
        URL, headers={
            "User-Agent": "FxResearchCalendarObserver/0.1",
            "Accept": "text/calendar"})
    opener = opener or urllib.request.build_opener(NoRedirect())
    with opener.open(request, timeout=12) as response:
        if response.status != 200:
            raise InputError("BLS calendar response not successful")
        content = response.read(MAX_ICS_BYTES + 1)
        if len(content) > MAX_ICS_BYTES:
            raise InputError("BLS calendar response too large")
        return content


def _unfold(raw: bytes) -> list[str]:
    if not isinstance(raw, bytes) or len(raw) > MAX_ICS_BYTES:
        raise InputError("calendar size exceeded")
    text = raw.decode("utf-8-sig")
    if "\x00" in text:
        raise InputError("invalid ICS binary")
    lines = text.replace("\r\n", "\n").split("\n")
    unfolded = []
    for line in lines:
        if len(line) > 2500:
            raise InputError("overlong ICS line")
        if line.startswith((" ", "\t")):
            if not unfolded:
                raise InputError("orphan ICS folded line")
            unfolded[-1] += line[1:]
        else:
            unfolded.append(line)
    return unfolded


def _utc(value: str, property_name: str) -> str:
    tzid = None
    for part in property_name.split(";")[1:]:
        if part.startswith("TZID="):
            tzid = part.partition("=")[2]
    if value.endswith("Z"):
        if tzid:
            raise InputError("contradictory ICS timezone")
        try:
            start = datetime.strptime(value, "%Y%m%dT%H%M%SZ")
        except ValueError as exc:
            raise InputError("invalid UTC calendar datetime") from exc
        start = start.replace(tzinfo=timezone.utc)
    else:
        # BLS publishes its release timetable in US Eastern Time. Its
        # public ICS uses the legacy iCalendar TZID "US-Eastern" (hyphen).
        # Treat exactly that spelling as an observational BLS-only alias
        # of America/New_York; do NOT generalize arbitrary TZIDs.
        # This is not independent event-time authentication or GO permission.
        if tzid not in ("America/New_York", "US/Eastern", "US-Eastern"):
            raise InputError("unsupported or missing BLS calendar timezone")
        try:
            local = datetime.strptime(value, "%Y%m%dT%H%M%S")
        except ValueError as exc:
            raise InputError("invalid NY calendar datetime") from exc
        start = local.replace(tzinfo=TZ)
        # DST gap and ambiguity require additional review; no guessing.
        roundtrip = start.astimezone(timezone.utc).astimezone(TZ)
        if roundtrip.replace(tzinfo=None) != local:
            raise InputError("nonexistent calendar DST local time")
        alternative = local.replace(tzinfo=TZ, fold=1)
        if alternative.utcoffset() != start.utcoffset():
            raise InputError("ambiguous calendar DST local time")
    return start.astimezone(timezone.utc).isoformat(
        timespec="seconds").replace("+00:00", "Z")


def parse_calendar(raw: bytes, *, asof_utc: str,
                   days_forward: int = 14) -> dict:
    now = timestamp(asof_utc)
    if type(days_forward) is not int or not 1 <= days_forward <= 31:
        raise InputError("bounded calendar horizon required")
    lines = _unfold(raw)
    if not lines or lines[0] != "BEGIN:VCALENDAR" or (
            "END:VCALENDAR" not in lines):
        raise InputError("unexpected calendar format")
    inside = False
    properties = {}
    events = []
    for line in lines:
        if line == "BEGIN:VEVENT":
            if inside:
                raise InputError("nested ICS event")
            inside, properties = True, {}
        elif line == "END:VEVENT":
            if not inside:
                raise InputError("orphan ICS event end")
            inside = False
            dt = [(key, value) for key, value in properties.items()
                  if key == "DTSTART" or key.startswith("DTSTART;")]
            if len(dt) != 1 or "SUMMARY" not in properties:
                raise InputError("ICS event missing date or title")
            event_at = _utc(dt[0][1], dt[0][0])
            summary = properties["SUMMARY"]
            if len(summary) > 250 or not summary.strip():
                raise InputError("invalid calendar event title")
            t = timestamp(event_at)
            if now - timedelta(minutes=15) <= t <= (
                    now + timedelta(days=days_forward)):
                events.append({
                    "title": summary,
                    "scheduled_at_utc": event_at,
                    "source_url": URL,
                    "source_status": "PUBLISHED_SCHEDULE_UNVERIFIED",
                })
        elif inside:
            if ":" not in line:
                raise InputError("invalid ICS property line")
            key, value = line.split(":", 1)
            if key.startswith(("DTSTART", "SUMMARY")):
                if key in properties:
                    raise InputError("repeated ICS event property")
                properties[key] = value
        if len(events) > MAX_EVENTS:
            raise InputError("excessive BLS events")
    if inside:
        raise InputError("unterminated calendar event")
    events.sort(key=lambda e: e["scheduled_at_utc"])
    imminent = [e for e in events if abs((
        timestamp(e["scheduled_at_utc"]) - now).total_seconds()) <= 900]
    return {
        "status": "BLS_CALENDAR_RESEARCH_ONLY_NO_GO",
        "asof_utc": asof_utc, "horizon_days": days_forward,
        "calendar_sha256": hashlib.sha256(raw).hexdigest(),
        "source_url": URL, "event_count": len(events),
        "imminent_event_count": len(imminent),
        "imminent_research_event_halt_suggested": bool(imminent),
        "events": events,
        "source_authenticity_verified": False,
        "calendar_covers_all_fx_events": False,
        "release_content_or_consensus_verified": False,
        # Provisional until independently cross-checked with release pages.
        "calendar_timezone_alias_us_eastern_assumed": any(
            line.startswith("DTSTART;TZID=US-Eastern:") for line in lines),
        "release_time_independently_verified": False,
        "real_orders_permitted": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description="BLS public release calendar snapshot; research only")
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--ics-file", type=Path)
    p.add_argument("--allow-network", action="store_true")
    p.add_argument("--asof-utc")
    p.add_argument("--days-forward", type=int, default=14)
    args = p.parse_args(argv)
    try:
        if args.out.exists() or not args.out.parent.is_dir() or (
                bool(args.ics_file) == bool(args.allow_network)):
            raise InputError("explicit one-source mode and absent output")
        if args.ics_file:
            if args.ics_file.stat().st_size > MAX_ICS_BYTES:
                raise InputError("local ICS file too large")
            raw = args.ics_file.read_bytes()
        else:
            raw = download()
        now = args.asof_utc or datetime.now(
            timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        report = parse_calendar(raw, asof_utc=now,
                                days_forward=args.days_forward)
        with args.out.open("x", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(json.dumps({
            "status": report["status"],
            "event_count": report["event_count"],
            "imminent_event_count": report["imminent_event_count"],
            "runtime_go_no_go": "NO_GO",
            "real_orders_permitted": False}))
        return 0
    except (InputError, OSError, ValueError, TypeError,
            UnicodeError, ArithmeticError, urllib.error.URLError):
        print(json.dumps({
            "status": "FAIL_CLOSED",
            "reason": "BLS_CALENDAR_INVALID_OR_UNAVAILABLE",
            "runtime_go_no_go": "NO_GO",
            "safety_hold_latched": True,
            "real_orders_permitted": False,
        }))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
