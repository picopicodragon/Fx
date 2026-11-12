"""FWD-253..264: fixed-code, read-only BLS iCalendar failure diagnosis.

The official ICS download and strict parser are reused unchanged. No
redirects, UA bypass, error details, raw page content, network retries,
broker calls or trading permission. Network requires explicit opt-in.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

from research import forward_bls_calendar as cal
from research.offline_backtest import InputError, timestamp

SCHEMA = "fx_fwd_bls_calendar_diagnostic_v1"
ERRORS = {
    "BLS schedule redirect not allowlisted": "HTTP_REDIRECT_BLOCKED",
    "BLS calendar response not successful": "HTTP_NON_200",
    "BLS calendar response too large": "ICS_RESPONSE_SIZE_LIMIT",
    "calendar size exceeded": "ICS_RESPONSE_SIZE_LIMIT",
    "invalid ICS binary": "INVALID_ICS_BINARY",
    "overlong ICS line": "ICS_LINE_TOO_LONG",
    "orphan ICS folded line": "ICS_FOLDING_INVALID",
    "unexpected calendar format": "UNEXPECTED_CALENDAR_ROOT",
    "nested ICS event": "NESTED_ICS_EVENT",
    "orphan ICS event end": "UNMATCHED_ICS_EVENT_END",
    "ICS event missing date or title": "ICS_EVENT_DATE_OR_TITLE_MISSING",
    "invalid UTC calendar datetime": "ICS_UTC_TIME_INVALID",
    "unsupported or missing BLS calendar timezone": "ICS_TIMEZONE_UNSUPPORTED",
    "contradictory ICS timezone": "ICS_TIMEZONE_CONTRADICTORY",
    "invalid NY calendar datetime": "ICS_LOCAL_TIME_INVALID",
    "nonexistent calendar DST local time": "ICS_DST_GAP",
    "ambiguous calendar DST local time": "ICS_DST_AMBIGUOUS",
    "invalid calendar event title": "ICS_EVENT_TITLE_INVALID",
    "invalid ICS property line": "ICS_PROPERTY_INVALID",
    "repeated ICS event property": "ICS_PROPERTY_REPEATED",
    "excessive BLS events": "ICS_EVENT_COUNT_LIMIT",
    "unterminated calendar event": "ICS_EVENT_NOT_TERMINATED",
    "bounded calendar horizon required": "INVALID_HORIZON",
    "output path already exists": "OUTPUT_PATH_ALREADY_EXISTS",
    "output parent directory missing": "OUTPUT_PARENT_NOT_DIRECTORY",
}
MAX_BYTES = cal.MAX_ICS_BYTES


def _code(exc: BaseException) -> str:
    # Never expose network exception strings or raw HTTP response data.
    if isinstance(exc, urllib.error.HTTPError):
        if exc.code in (400, 401, 403, 404, 408, 410, 429):
            return "HTTP_" + str(exc.code)
        if 500 <= exc.code <= 599:
            return "HTTP_5XX"
        return "HTTP_OTHER"
    if isinstance(exc, InputError):
        return ERRORS.get(str(exc), "INPUT_VALIDATION_OTHER")
    if isinstance(exc, urllib.error.URLError):
        return "NETWORK_DNS_TLS_OR_TIMEOUT"
    if isinstance(exc, (TimeoutError, ConnectionError)):
        return "NETWORK_DNS_TLS_OR_TIMEOUT"
    if isinstance(exc, UnicodeError):
        return "ICS_CHARACTER_ENCODING_INVALID"
    return "LOCAL_IO_OR_UNCLASSIFIED_ERROR"


def _format_hint(data: bytes) -> str:
    # This is a bounded classification of the beginning of the response,
    # *not* a copy of content. Never store the response in this report.
    lead = data[:180].lstrip().lower().lstrip(b"\xef\xbb\xbf")
    if lead.startswith(b"begin:vcalendar"):
        return "VCALENDAR_TEXT"
    if lead.startswith(b"<!doctype html") or lead.startswith(b"<html"):
        return "HTML_NOT_CALENDAR"
    if lead.startswith(b"<?xml") or lead.startswith(b"<!doctype"):
        return "XML_OR_OTHER_DOCUMENT"
    if not data:
        return "EMPTY_RESPONSE"
    return "OTHER_OR_WRAPPED_CONTENT"


def _base(*, network: bool) -> dict:
    return {
        "schema": SCHEMA,
        "status": "BLS_CALENDAR_DIAGNOSTIC_HOLD_NO_GO",
        "stage": "INPUT",
        "reason_code": None,
        "network_opted_in": network,
        "calendar_source_url": cal.URL,
        "source_url_independently_authenticated": False,
        "calendar_covers_all_fx_events": False,
        "report_or_original_journal_modified": False,
        "automatic_retry_enabled": False,
        "API_calls_this_run": 0,
        "actual_orders_sent": 0,
        "demo_orders_permitted": False,
        "real_orders_permitted": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
    }


def diagnose(*, raw: bytes | None = None,
             allow_network: bool = False,
             asof_utc: str, days_forward: int = 14,
             planned_out: Path | None = None) -> dict:
    result = _base(network=allow_network)
    try:
        timestamp(asof_utc)
        if (allow_network != (raw is None)
                or type(days_forward) is not int
                or not 1 <= days_forward <= 31):
            raise InputError("bounded calendar horizon required")
        if planned_out is not None:
            result["stage"] = "OUTPUT_PRECHECK"
            if type(planned_out) is not Path:
                raise InputError("output parent directory missing")
            if planned_out.exists() or planned_out.is_symlink():
                raise InputError("output path already exists")
            if not planned_out.parent.is_dir():
                raise InputError("output parent directory missing")
            result["planned_output_status"] = "NEW_PATH_AVAILABLE_NOT_WRITTEN"
        if raw is None:
            result["stage"] = "FETCH"
            raw = cal.download()
        result["stage"] = "CONTENT_CLASSIFICATION"
        if not isinstance(raw, bytes) or len(raw) > MAX_BYTES:
            raise InputError("calendar size exceeded")
        result["body_bytes"] = len(raw)
        result["body_sha256_for_local_comparison"] = hashlib.sha256(
            raw).hexdigest()
        result["document_class"] = _format_hint(raw)
        result["stage"] = "STRICT_PARSE"
        parsed = cal.parse_calendar(
            raw, asof_utc=asof_utc, days_forward=days_forward)
        result.update({
            "status": "BLS_CALENDAR_DIAGNOSTIC_PREFLIGHT_OK_NO_GO",
            "stage": "PREFLIGHT",
            "calendar_research_event_count": parsed["event_count"],
            "imminent_research_event_count":
                parsed["imminent_event_count"],
            "calendar_horizon_days": days_forward,
        })
    except (InputError, OSError, ValueError, UnicodeError,
            TypeError, KeyError, ArithmeticError, OverflowError) as exc:
        result["status"] = "BLS_CALENDAR_DIAGNOSTIC_FAIL_CLOSED_NO_GO"
        result["reason_code"] = _code(exc)
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Read-only BLS iCalendar failure classification (NO_GO)")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--allow-network", action="store_true")
    group.add_argument("--ics-file", type=Path)
    parser.add_argument("--days-forward", type=int, default=14)
    parser.add_argument("--planned-out", type=Path)
    args = parser.parse_args(argv)
    try:
        raw = None
        if args.ics_file is not None:
            p = args.ics_file
            if (not p.is_file() or p.is_symlink()
                    or not 0 < p.stat().st_size <= MAX_BYTES):
                raise InputError("invalid local calendar fixture")
            raw = p.read_bytes()
        current = datetime.now(timezone.utc).isoformat(
            timespec="seconds").replace("+00:00", "Z")
        report = diagnose(
            raw=raw, allow_network=args.allow_network,
            asof_utc=current, days_forward=args.days_forward,
            planned_out=args.planned_out)
    except (InputError, OSError, ValueError, UnicodeError,
            TypeError, KeyError):
        report = _base(network=args.allow_network)
        report["status"] = "BLS_CALENDAR_DIAGNOSTIC_FAIL_CLOSED_NO_GO"
        report["reason_code"] = "LOCAL_CALENDAR_FILE_INVALID"
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["status"] == (
        "BLS_CALENDAR_DIAGNOSTIC_PREFLIGHT_OK_NO_GO") else 2


if __name__ == "__main__":
    raise SystemExit(main())
