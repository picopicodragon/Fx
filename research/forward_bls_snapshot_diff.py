"""FWD-333..344: offline verification/comparison of two BLS snapshot bundles.

No network, writes, new event insertion or trading actions. Timestamps are
local-wall-clock self-reported, and SHA256 only detects accidental/malicious
changes when a trusted reference digest is separately retained.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from research import forward_bls_dual_snapshot as snap
from research import forward_bls_calendar as cal
from research.offline_backtest import InputError, timestamp

MAX_MANIFEST = 12_000
MAX_CALENDAR = 160_000


def _bytes(folder: Path, name: str, cap: int) -> bytes:
    path = folder / name
    if (not path.is_file() or path.is_symlink()
            or not 0 < path.stat().st_size <= cap):
        raise InputError("unsafe snapshot evidence file")
    data = path.read_bytes()
    if not 0 < len(data) <= cap:
        raise InputError("snapshot input changed size")
    return data


def verify(folder: Path) -> dict:
    if not isinstance(folder, Path) or not folder.is_dir() or folder.is_symlink():
        raise InputError("invalid snapshot directory")
    manifest = json.loads(_bytes(folder, snap.MANIFEST_NAME, MAX_MANIFEST))
    if type(manifest) is not dict or any((
            manifest.get("schema") != snap.SCHEMA,
            manifest.get("status") != "BLS_DUAL_FORMAT_SNAPSHOT_RESEARCH_HOLD_NO_GO",
            manifest.get("runtime_go_no_go") != "NO_GO",
            manifest.get("safety_hold_latched") is not True,
            manifest.get("real_orders_permitted") is not False,
            manifest.get("demo_orders_permitted") is not False,
            manifest.get("complete_snapshot_marker_written_last") is not True,
            manifest.get("source_authenticity_independently_verified") is not False,
            manifest.get("ics_source_url") != cal.URL,
            manifest.get("html_source_url") != snap.HTML_URL,
            manifest.get("ics_file") != snap.ICS_NAME,
            manifest.get("html_file") != snap.HTML_NAME,
            manifest.get("calendar_report_file") != snap.CAL_NAME,
            manifest.get("collection_mode") not in (
                "NETWORK_EXPLICIT_OPT_IN", "LOCAL_COPY"),
        )):
        raise InputError("snapshot manifest provenance invalid")
    ics = _bytes(folder, snap.ICS_NAME, cal.MAX_ICS_BYTES)
    html = _bytes(folder, snap.HTML_NAME, snap.HTML_MAX_BYTES)
    snap._validate_html(html)
    for name, raw in (("ics", ics), ("html", html)):
        if (type(manifest.get(name + "_bytes")) is not int
                or manifest[name + "_bytes"] != len(raw)
                or manifest.get(name + "_sha256")
                != hashlib.sha256(raw).hexdigest()):
            raise InputError("snapshot source checksum mismatch")
    raw_report = _bytes(folder, snap.CAL_NAME, MAX_CALENDAR)
    report = json.loads(raw_report)
    if type(report) is not dict:
        raise InputError("calendar report root invalid")
    ics_at = manifest.get("ics_observed_at_utc_local_clock_unattested")
    html_at = manifest.get("html_observed_at_utc_local_clock_unattested")
    if (type(ics_at) is not str or type(html_at) is not str
            or timestamp(ics_at) > timestamp(html_at)):
        raise InputError("snapshot timestamp order invalid")
    recomputed, derived = snap.prepare(
        ics=ics, html=html, observed_ics_utc=ics_at,
        observed_html_utc=html_at,
        mode=manifest["collection_mode"],
        days_forward=manifest.get("calendar_horizon_days"))
    if recomputed != manifest or derived != report:
        raise InputError("snapshot manifest/calendar payload mismatch")
    return manifest


def compare(before: Path, after: Path) -> dict:
    earlier, later = verify(before), verify(after)
    btime = timestamp(earlier["html_observed_at_utc_local_clock_unattested"])
    atime = timestamp(later["ics_observed_at_utc_local_clock_unattested"])
    if btime > atime:
        raise InputError("snapshot order overlaps or runs backwards")
    ics_changed = earlier["ics_sha256"] != later["ics_sha256"]
    html_changed = earlier["html_sha256"] != later["html_sha256"]
    if ics_changed and html_changed:
        change = "BOTH_SOURCE_BYTES_CHANGED"
    elif ics_changed:
        change = "ICS_SOURCE_BYTES_CHANGED"
    elif html_changed:
        change = "HTML_SOURCE_BYTES_CHANGED"
    else:
        change = "BOTH_SOURCE_BYTES_UNCHANGED"
    return {
        "schema": "fx_fwd_bls_dual_snapshot_diff_v1",
        "status": "BLS_SNAPSHOT_BYTE_DIFF_RESEARCH_HOLD_NO_GO",
        "raw_body_change_classification": change,
        "before_ics_sha256": earlier["ics_sha256"],
        "after_ics_sha256": later["ics_sha256"],
        "before_html_sha256": earlier["html_sha256"],
        "after_html_sha256": later["html_sha256"],
        "ics_reported_event_count_before": earlier["calendar_event_count"],
        "ics_reported_event_count_after": later["calendar_event_count"],
        "two_bls_sources_not_independent": True,
        "source_capture_clock_independently_attested": False,
        "publication_or_revision_time_verified": False,
        "changed_bytes_not_equivalent_to_schedule_change": True,
        "unchanged_bytes_not_equivalent_to_complete_coverage": True,
        "event_title_and_datetime_identity_verified": False,
        "pre_release_consensus_available": False,
        "missing_events_auto_backfilled": False,
        "network_calls_this_run": 0,
        "files_written_this_run": 0,
        "API_calls_this_run": 0,
        "actual_orders_sent": 0,
        "demo_orders_permitted": False,
        "real_orders_permitted": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Offline BLS snapshot integrity and source-byte diff")
    parser.add_argument("--before-dir", required=True, type=Path)
    parser.add_argument("--after-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.before_dir.resolve() == args.after_dir.resolve():
            raise InputError("distinct snapshots required")
        result = compare(args.before_dir, args.after_dir)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (InputError, OSError, ValueError, TypeError,
            KeyError, UnicodeError, ArithmeticError, OverflowError):
        print(json.dumps({
            "schema": "fx_fwd_bls_dual_snapshot_diff_v1",
            "status": "BLS_SNAPSHOT_DIFF_FAIL_CLOSED_NO_GO",
            "reason_code": "INVALID_OR_INCOMPLETE_BUNDLE",
            "files_written_this_run": 0,
            "network_calls_this_run": 0,
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
