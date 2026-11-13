"""FWD-285..298: offline, conservative BLS ICS vs selected HTML schedule audit.

Two representations from the *same publisher*, not independent source
authentication. No network, write, AI request, broker/EA access or permission.
Calendar and independently-transcribed HTML list are both unverified evidence.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
from zoneinfo import ZoneInfo

from research import forward_bls_calendar as cal
from research.offline_backtest import InputError, timestamp

SCHEMA = "fx_fwd_bls_secondary_schedule_slot_audit_v1"
REFERENCE_SCHEMA = "fx_bls_selected_html_schedule_reference_v1"
REFERENCE_URL = "https://www.bls.gov/schedule/2026/11_sched_list.htm"
TZ = ZoneInfo("America/New_York")
MAX_CALENDAR_BYTES = 160_000
MAX_REFERENCE_BYTES = 32_000
UTC_TEXT = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z")
ET_TEXT = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\Z")
DIGEST = re.compile(r"[a-f0-9]{64}\Z")


def _utc(text: str) -> datetime:
    if type(text) is not str or not UTC_TEXT.fullmatch(text):
        raise InputError("UTC timestamp format invalid")
    result = timestamp(text)
    if result.tzinfo is None or result.utcoffset() != timedelta(0):
        raise InputError("UTC timestamp invalid")
    return result


def _local_et_to_utc(text: str) -> datetime:
    if type(text) is not str or not ET_TEXT.fullmatch(text):
        raise InputError("local schedule timestamp format invalid")
    local = datetime.strptime(text, "%Y-%m-%dT%H:%M:%S")
    aware = local.replace(tzinfo=TZ)
    if aware.astimezone(timezone.utc).astimezone(TZ).replace(tzinfo=None) != local:
        raise InputError("nonexistent ET schedule time")
    if local.replace(tzinfo=TZ, fold=1).utcoffset() != aware.utcoffset():
        raise InputError("ambiguous ET schedule time")
    return aware.astimezone(timezone.utc)


def _read_json(path: Path, limit: int) -> dict:
    if (not path.is_file() or path.is_symlink()
            or not 0 < path.stat().st_size <= limit):
        raise InputError("missing, linked or oversized evidence file")
    obj = json.loads(path.read_text(encoding="utf-8-sig"))
    if type(obj) is not dict:
        raise InputError("evidence root invalid")
    return obj


def _validate_calendar(obj: dict) -> tuple[datetime, datetime, Counter[str]]:
    if type(obj) is not dict or any((
            obj.get("status") != "BLS_CALENDAR_RESEARCH_ONLY_NO_GO",
            obj.get("source_url") != cal.URL,
            obj.get("runtime_go_no_go") != "NO_GO",
            obj.get("safety_hold_latched") is not True,
            obj.get("real_orders_permitted") is not False,
            obj.get("release_time_independently_verified") is not False,
            obj.get("source_authenticity_verified") is not False,
            obj.get("calendar_covers_all_fx_events") is not False,
            obj.get("calendar_timezone_alias_us_eastern_assumed") is not True,
        )):
        raise InputError("calendar research safety or provenance invalid")
    sha = obj.get("calendar_sha256")
    if type(sha) is not str or not DIGEST.fullmatch(sha):
        raise InputError("ICS digest provenance invalid")
    horizon = obj.get("horizon_days")
    if type(horizon) is not int or not 1 <= horizon <= 31:
        raise InputError("calendar horizon invalid")
    start = _utc(obj.get("asof_utc"))
    end = start + timedelta(days=horizon)
    lower = start - timedelta(minutes=15)
    events = obj.get("events")
    if (type(events) is not list or len(events) > cal.MAX_EVENTS
            or type(obj.get("event_count")) is not int
            or obj["event_count"] != len(events)):
        raise InputError("calendar event count invalid")
    slots: Counter[str] = Counter()
    for event in events:
        if (type(event) is not dict
                or type(event.get("title")) is not str
                or not 0 < len(event["title"]) <= 250
                or event.get("source_url") != cal.URL
                or event.get("source_status") != "PUBLISHED_SCHEDULE_UNVERIFIED"):
            raise InputError("calendar event item invalid")
        dt = _utc(event.get("scheduled_at_utc"))
        if not lower <= dt <= end:
            raise InputError("calendar event outside claimed horizon")
        slots[event["scheduled_at_utc"]] += 1
    return lower, end, slots


def _validate_reference(obj: dict) -> tuple[str, Counter[str]]:
    if (type(obj) is not dict
            or obj.get("schema") != REFERENCE_SCHEMA
            or obj.get("source_url") != REFERENCE_URL
            or obj.get("reference_month") != "2026-11"
            or obj.get("source_page_last_modified") != "2026-11-03"
            or obj.get("transcription_method")
               != "MANUALLY_TRANSCRIBED_PUBLIC_BLS_HTML_LIST"
            or obj.get("source_authenticity_independently_attested") is not False
            or obj.get("source_snapshot_immutable_proof_available") is not False
            or obj.get("selected_release_schedule_not_exhaustive") is not True):
        raise InputError("HTML reference scope or provenance invalid")
    events = obj.get("events")
    if type(events) is not list or not 1 <= len(events) <= 100:
        raise InputError("HTML reference events invalid")
    slots: Counter[str] = Counter()
    for event in events:
        if (type(event) is not dict
                or type(event.get("title")) is not str
                or not 0 < len(event["title"]) <= 250
                or type(event.get("local_time_et")) is not str
                or not event["local_time_et"].startswith("2026-11-")):
            raise InputError("HTML reference event invalid")
        when = _local_et_to_utc(event["local_time_et"])
        slots[when.strftime("%Y-%m-%dT%H:%M:%SZ")] += 1
    return obj["reference_month"], slots


def inspect(calendar: dict, reference: dict) -> dict:
    start, end, observed = _validate_calendar(calendar)
    month, selected = _validate_reference(reference)
    # The selected BLS HTML list is a MONTHLY source. Refuse a
    # partial-month crosscheck if the ICS window spills into another month.
    covered = (
        start.astimezone(TZ).strftime("%Y-%m") == month
        and end.astimezone(TZ).strftime("%Y-%m") == month)
    if not covered:
        raise InputError("reference does not cover entire calendar horizon")
    selected = Counter({
        dt: n for dt, n in selected.items()
        if start <= _utc(dt) <= end
    })
    missing = selected - observed
    extra = observed - selected
    matched = selected & observed

    # A match of timestamp multiplicities cannot authenticate titles,
    # source publication, or completeness of macro calendars.
    agreement = not missing and not extra
    return {
        "schema": SCHEMA,
        "status": "BLS_SECOND_SOURCE_SLOT_AUDIT_HOLD_NO_GO",
        "slot_count_result": (
            "SELECTED_HTML_SLOT_COUNTS_MATCH_UNVERIFIED"
            if agreement else "SELECTED_HTML_SLOT_COUNTS_DISAGREE"),
        "reference_month": month,
        "calendar_asof_utc": calendar["asof_utc"],
        "calendar_horizon_days": calendar["horizon_days"],
        "calendar_sha256_self_reported": calendar["calendar_sha256"],
        "reference_source_url": REFERENCE_URL,
        "reference_page_last_modified": reference["source_page_last_modified"],
        "reference_format": "STATIC_MANUALLY_TRANSCRIBED_HTML_LIST",
        "reference_covers_entire_requested_window": covered,
        "calendar_event_count": sum(observed.values()),
        "selected_html_event_count_within_window": sum(selected.values()),
        "matching_slot_instance_count": sum(matched.values()),
        "missing_selected_html_slot_instances": sum(missing.values()),
        "unexpected_ics_slot_instances": sum(extra.values()),
        "missing_selected_html_slots": [
            {"scheduled_at_utc": key, "count": missing[key]}
            for key in sorted(missing)],
        "unexpected_ics_slots": [
            {"scheduled_at_utc": key, "count": extra[key]}
            for key in sorted(extra)],
        "date_time_slots_only_not_titles": True,
        "selected_html_does_not_cover_all_bls_releases": True,
        "all_fx_macro_events_covered": False,
        "title_or_release_identity_verified": False,
        "release_time_independently_verified": False,
        "source_authenticity_independently_verified": False,
        "official_html_snapshot_time_authenticated": False,
        "freshness_of_static_reference_guaranteed": False,
        "calendar_schedule_revision_possible": True,
        "new_evidence_files_written": False,
        "network_calls_this_run": 0,
        "API_calls_this_run": 0,
        "demo_orders_permitted": False,
        "real_orders_permitted": False,
        "actual_orders_sent": 0,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description="BLS ICS vs selected HTML slot count, offline NO_GO")
    p.add_argument("--calendar-report", required=True, type=Path)
    p.add_argument("--reference-file", required=True, type=Path)
    args = p.parse_args(argv)
    try:
        result = inspect(
            _read_json(args.calendar_report, MAX_CALENDAR_BYTES),
            _read_json(args.reference_file, MAX_REFERENCE_BYTES))
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (InputError, OSError, ValueError, TypeError, KeyError,
            UnicodeError, OverflowError):
        print(json.dumps({
            "schema": SCHEMA,
            "status": "BLS_SECOND_SOURCE_SLOT_AUDIT_FAIL_CLOSED_NO_GO",
            "reason_code": "INVALID_OR_OUT_OF_SCOPE_EVIDENCE",
            "source_authenticity_independently_verified": False,
            "release_time_independently_verified": False,
            "new_evidence_files_written": False,
            "network_calls_this_run": 0,
            "API_calls_this_run": 0,
            "demo_orders_permitted": False,
            "real_orders_permitted": False,
            "actual_orders_sent": 0,
            "runtime_go_no_go": "NO_GO",
            "safety_hold_latched": True,
        }))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
