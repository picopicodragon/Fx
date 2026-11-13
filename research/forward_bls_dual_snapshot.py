"""FWD-325..344: one-shot bounded BLS dual-format research evidence bundle.

Explicit opt-in only; fixed official HTTPS hosts and no redirects or retry.
All file output is under one fresh directory; snapshot.json is written last.
No scheduler, paid API, EA, broker access or order permission. A bundle is
an *observation*, never proof of point-in-time publisher truth.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from research import forward_bls_calendar as calendar
from research.offline_backtest import InputError, timestamp

SCHEMA = "fx_fwd_bls_dual_format_snapshot_v1"
HTML_URL = "https://www.bls.gov/schedule/2026/11_sched_list.htm"
HTML_MAX_BYTES = 500_000
ICS_NAME = "bls.ics"
HTML_NAME = "bls_schedule.html"
CAL_NAME = "calendar.json"
MANIFEST_NAME = "snapshot.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(
        timespec="seconds").replace("+00:00", "Z")


def _read_file(path: Path, cap: int) -> bytes:
    if (not path.is_file() or path.is_symlink()
            or not 0 < path.stat().st_size <= cap):
        raise InputError("source file invalid or exceeds size limit")
    data = path.read_bytes()
    if not 0 < len(data) <= cap:
        raise InputError("source size changed during read")
    return data


def _download_html(*, opener=None) -> bytes:
    opener = opener or urllib.request.build_opener(calendar.NoRedirect())
    request = urllib.request.Request(
        HTML_URL, headers={
            "User-Agent": "FxResearchCalendarObserver/0.1",
            "Accept": "text/html"})
    with opener.open(request, timeout=12) as response:
        if response.status != 200:
            raise InputError("BLS HTML response not successful")
        data = response.read(HTML_MAX_BYTES + 1)
        if len(data) > HTML_MAX_BYTES:
            raise InputError("BLS HTML response too large")
        return data


def _validate_html(raw: bytes) -> None:
    if not isinstance(raw, bytes) or not 0 < len(raw) <= HTML_MAX_BYTES:
        raise InputError("HTML size invalid")
    if b"\x00" in raw:
        raise InputError("HTML binary content invalid")
    lower = raw[:1200].lstrip(b"\xef\xbb\xbf \r\n\t").lower()
    if not (lower.startswith(b"<!doctype html")
            or lower.startswith(b"<html")):
        raise InputError("HTML document header invalid")
    if (b"schedule of selected releases" not in raw.lower()
            or b"november 2026" not in raw.lower()):
        raise InputError("expected BLS HTML month not established")


def prepare(*, ics: bytes, html: bytes, observed_ics_utc: str,
            observed_html_utc: str, mode: str,
            days_forward: int = 14) -> tuple[dict, dict]:
    if mode not in ("NETWORK_EXPLICIT_OPT_IN", "LOCAL_COPY"):
        raise InputError("unknown observation mode")
    if type(days_forward) is not int or not 1 <= days_forward <= 31:
        raise InputError("invalid calendar horizon")
    start = timestamp(observed_ics_utc)
    end = timestamp(observed_html_utc)
    if start.utcoffset() != timezone.utc.utcoffset(None) or (
            end.utcoffset() != timezone.utc.utcoffset(None)):
        raise InputError("observation clock not UTC")
    if start > end or (end - start).total_seconds() > 120:
        raise InputError("observation clocks out of bounds")
    if type(ics) is not bytes or not 0 < len(ics) <= calendar.MAX_ICS_BYTES:
        raise InputError("ICS missing or too large")
    _validate_html(html)
    report = calendar.parse_calendar(
        ics, asof_utc=observed_ics_utc, days_forward=days_forward)
    ics_sha = hashlib.sha256(ics).hexdigest()
    html_sha = hashlib.sha256(html).hexdigest()
    manifest = {
        "schema": SCHEMA,
        "status": "BLS_DUAL_FORMAT_SNAPSHOT_RESEARCH_HOLD_NO_GO",
        "collection_mode": mode,
        "ics_source_url": calendar.URL,
        "html_source_url": HTML_URL,
        "ics_observed_at_utc_local_clock_unattested": observed_ics_utc,
        "html_observed_at_utc_local_clock_unattested": observed_html_utc,
        "two_sources_not_atomic_and_not_independently_authenticated": True,
        "publisher_of_both_sources": "BLS",
        "source_authenticity_independently_verified": False,
        "http_delivery_time_independently_attested": False,
        "calendar_all_fx_events_covered": False,
        "html_selected_releases_only": True,
        "historical_publication_time_proven": False,
        "original_source_capture_time_proven": False,
        "ics_file": ICS_NAME,
        "ics_sha256": ics_sha,
        "ics_bytes": len(ics),
        "html_file": HTML_NAME,
        "html_sha256": html_sha,
        "html_bytes": len(html),
        "calendar_report_file": CAL_NAME,
        "calendar_sha256_self_reported": report["calendar_sha256"],
        "calendar_event_count": report["event_count"],
        "calendar_horizon_days": days_forward,
        "complete_snapshot_marker_written_last": True,
        "network_calls_expected": 2 if mode == "NETWORK_EXPLICIT_OPT_IN" else 0,
        "automatic_poll_or_retry_enabled": False,
        "API_calls_this_run": 0,
        "actual_orders_sent": 0,
        "demo_orders_permitted": False,
        "real_orders_permitted": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
    }
    if report["calendar_sha256"] != ics_sha:
        raise InputError("ICS report hash mismatch")
    return manifest, report


def write_bundle(*, out_dir: Path, ics: bytes, html: bytes,
                 manifest: dict, report: dict) -> None:
    if (not isinstance(out_dir, Path) or out_dir.exists()
            or out_dir.is_symlink() or not out_dir.parent.is_dir()
            or out_dir.parent.is_symlink()):
        raise InputError("new output folder required")
    # Exclusive mkdir: a partial directory has no complete manifest, hence
    # must not be accepted as evidence by the independent bundle verifier.
    out_dir.mkdir(exist_ok=False)
    with (out_dir / ICS_NAME).open("xb") as dest:
        dest.write(ics)
    with (out_dir / HTML_NAME).open("xb") as dest:
        dest.write(html)
    with (out_dir / CAL_NAME).open("x", encoding="utf-8") as dest:
        json.dump(report, dest, ensure_ascii=False, indent=2, allow_nan=False)
    with (out_dir / MANIFEST_NAME).open("x", encoding="utf-8") as dest:
        json.dump(manifest, dest, ensure_ascii=False, indent=2, allow_nan=False)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="BLS one-shot research snapshot")
    parser.add_argument("--out-dir", required=True, type=Path)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--allow-network", action="store_true")
    group.add_argument("--ics-file", type=Path)
    parser.add_argument("--html-file", type=Path)
    parser.add_argument("--days-forward", type=int, default=14)
    args = parser.parse_args(argv)
    stage = "INPUT"
    try:
        if (args.out_dir.exists() or args.out_dir.is_symlink()
                or not args.out_dir.parent.is_dir()
                or args.out_dir.parent.is_symlink()):
            raise InputError("new output directory required")
        if args.allow_network:
            if args.html_file is not None:
                raise InputError("offline source with network flag forbidden")
            stage = "FETCH"
            ics = calendar.download()
            observed_ics = _now()
            html = _download_html()
            observed_html = _now()
            mode = "NETWORK_EXPLICIT_OPT_IN"
        else:
            if args.html_file is None:
                raise InputError("both offline source files required")
            stage = "READ_LOCAL"
            ics = _read_file(args.ics_file, calendar.MAX_ICS_BYTES)
            observed_ics = _now()
            html = _read_file(args.html_file, HTML_MAX_BYTES)
            observed_html = _now()
            mode = "LOCAL_COPY"
        stage = "VALIDATE"
        manifest, report = prepare(
            ics=ics, html=html, observed_ics_utc=observed_ics,
            observed_html_utc=observed_html, mode=mode,
            days_forward=args.days_forward)
        stage = "WRITE"
        write_bundle(
            out_dir=args.out_dir, ics=ics, html=html,
            manifest=manifest, report=report)
        print(json.dumps({
            "status": manifest["status"],
            "collection_mode": mode,
            "calendar_event_count": report["event_count"],
            "ics_sha256": manifest["ics_sha256"],
            "html_sha256": manifest["html_sha256"],
            "snapshot_dir_created": True,
            "publisher_time_and_source_truth_verified": False,
            "runtime_go_no_go": "NO_GO",
            "safety_hold_latched": True,
            "real_orders_permitted": False,
        }))
        return 0
    except (InputError, OSError, ValueError, UnicodeError,
            TypeError, KeyError, ArithmeticError,
            urllib.error.URLError):
        print(json.dumps({
            "status": "BLS_DUAL_FORMAT_SNAPSHOT_FAIL_CLOSED_NO_GO",
            "stage": stage,
            "reason_code": "INVALID_OR_UNAVAILABLE_SNAPSHOT_EVIDENCE",
            "possible_partial_directory_without_manifest": stage == "WRITE",
            "automatic_retry_enabled": False,
            "API_calls_this_run": 0,
            "actual_orders_sent": 0,
            "demo_orders_permitted": False,
            "real_orders_permitted": False,
            "runtime_go_no_go": "NO_GO",
            "safety_hold_latched": True,
        }))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
