"""FWD-489..520: bounded read-only batch audit of write-once forecasts.

Each archive is verified using the existing strict record+SHA/time checks.
An archive can be matched only to the exact stored BLS ICS title/time/hash.
Absence or matching is never pre-release source authentication or GO.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from research import forward_bls_snapshot_diff as bls_integrity
from research import forward_bls_dual_snapshot as bls_snapshot
from research.forward_macro_pre_release_capture import verify_archive
from research.offline_backtest import InputError, timestamp

SCHEMA = "fx_fwd_consensus_archive_batch_audit_v1"
MAX_FORECASTS = 64
MAX_ARCHIVE_BYTES = 8000


def _read(path: Path) -> dict:
    if (not isinstance(path, Path) or not path.is_file() or path.is_symlink()
            or not 0 < path.stat().st_size <= MAX_ARCHIVE_BYTES):
        raise InputError("forecast file invalid, unsafe or oversized")
    record = json.loads(path.read_text(encoding="utf-8-sig"))
    if type(record) is not dict:
        raise InputError("forecast archive must be JSON object")
    return record


def inspect(archives: list[Path], *, asof_utc: str,
            bls_snapshot_dir: Path | None = None) -> dict:
    timestamp(asof_utc)
    if (type(archives) is not list or len(archives) > MAX_FORECASTS
            or any(not isinstance(p, Path) for p in archives)):
        raise InputError("invalid forecast archive list")
    if archives and bls_snapshot_dir is None:
        raise InputError("forecasts require same-capture BLS source bundle")
    calendar = None
    digest = None
    if bls_snapshot_dir is not None:
        m = bls_integrity.verify(bls_snapshot_dir)
        calendar = json.loads(bls_integrity._bytes(
            bls_snapshot_dir, bls_snapshot.CAL_NAME,
            bls_integrity.MAX_CALENDAR))
        if type(calendar) is not dict or type(calendar.get("events")) is not list:
            raise InputError("invalid verified BLS report")
        digest = m["ics_sha256"]
        if calendar.get("calendar_sha256") != digest:
            raise InputError("calendar digest disagrees with BLS raw source")
    events = {(e["title"], e["scheduled_at_utc"])
              for e in calendar["events"]} if calendar else set()
    if calendar and len(events) != len(calendar["events"]):
        raise InputError("duplicate BLS event title/time")
    archive_paths = set()
    used = set()
    accepted_events = set()
    unmatched = []
    for p in archives:
        resolved = p.resolve(strict=True)
        if resolved in archive_paths:
            raise InputError("forecast archive path repeated")
        archive_paths.add(resolved)
        # The archive fields and timing are independently checked by
        # verify_archive, but source publication is NOT third-party attested.
        e = verify_archive(_read(p), asof_utc=asof_utc)
        ident = (e["event_title_unverified"],
                 e["scheduled_at_utc_unverified"])
        pair = e["pair"]
        if (ident, pair) in used:
            raise InputError("duplicate forecast event/pair record")
        used.add((ident, pair))
        if (e["calendar_report_sha256_self_reported"] == digest
                and ident in events):
            accepted_events.add(ident)
        else:
            unmatched.append({
                "event_title_sha256": __import__("hashlib").sha256(
                    ident[0].encode("utf-8")).hexdigest(),
                "scheduled_at_utc_unverified": ident[1],
                "pair": pair,
                "calendar_identity_mismatch": True,
            })
    holds = {
        "FORECAST_PUBLISHER_AND_CAPTURE_CLOCK_NOT_INDEPENDENTLY_ATTESTED",
        "FORECAST_EXCERPT_AND_CONSENSUS_VALUE_SEMANTIC_MATCH_UNVERIFIED",
        "FULL_FX_MACRO_CONSENSUS_COVERAGE_NOT_ATTESTED",
    }
    actions = []
    if bls_snapshot_dir is None:
        holds.add("NO_BLS_ORIGINAL_CALENDAR_FOR_CONSENSUS_AUDIT")
        actions.append("OBTAIN_AND_VERIFY_BLS_DUAL_SOURCE_SNAPSHOT")
    elif not archives:
        holds.add("NO_POINT_IN_TIME_FORECAST_ARCHIVES_PROVIDED")
        actions.append("CAPTURE_PRE_RELEASE_CONSENSUS_BEFORE_BLACKOUT")
    if unmatched:
        holds.add("FORECAST_ARCHIVE_BLS_CALENDAR_IDENTITY_MISMATCH")
        actions.append("RECONCILE_FORECAST_EVIDENCE_WITH_CURRENT_BLS_SNAPSHOT")
    if events - accepted_events:
        holds.add("BLS_EVENT_WITHOUT_MATCHED_FORECAST_ARCHIVE")
        actions.append("CAPTURE_REMAINING_BLS_PRE_RELEASE_CONSENSUS")
    return {
        "schema": SCHEMA,
        "status": "CONSENSUS_ARCHIVE_BATCH_RESEARCH_HOLD_NO_GO",
        "asof_utc": asof_utc,
        "bls_bundle_integrity_verified": calendar is not None,
        "bls_calendar_sha256": digest,
        "bls_unique_calendar_event_count": len(events),
        "archive_count": len(archives),
        "matched_unique_bls_event_count": len(accepted_events),
        "unmatched_archive_count": len(unmatched),
        "unmatched_archive_evidence": unmatched[:16],
        "unmatched_archive_evidence_omitted_count": max(0, len(unmatched)-16),
        "bls_events_without_archive_count": len(events - accepted_events),
        "all_pairwise_consensus_proven": False,
        "consensus_publisher_authenticated": False,
        "unresolved_holds": sorted(holds),
        "next_research_actions": actions,
        "files_written_this_run": 0,
        "network_calls_this_run": 0,
        "API_calls_this_run": 0,
        "orders_sent_this_run": 0,
        "demo_orders_permitted": False,
        "real_orders_permitted": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description="Audit many pre-release consensus archives (NO_GO)")
    p.add_argument("--bls-snapshot-dir", type=Path)
    p.add_argument("--forecast-archive", action="append",
                   type=Path, default=[])
    p.add_argument("--asof-utc", required=True)
    args = p.parse_args(argv)
    try:
        result = inspect(args.forecast_archive,
                         asof_utc=args.asof_utc,
                         bls_snapshot_dir=args.bls_snapshot_dir)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (InputError, OSError, ValueError, KeyError, TypeError,
            UnicodeError, ArithmeticError, OverflowError):
        print(json.dumps({
            "schema": SCHEMA,
            "status": "CONSENSUS_ARCHIVE_BATCH_FAIL_CLOSED_NO_GO",
            "reason_code": "INVALID_ARCHIVE_OR_SNAPSHOT",
            "files_written_this_run": 0, "network_calls_this_run": 0,
            "API_calls_this_run": 0, "orders_sent_this_run": 0,
            "demo_orders_permitted": False, "real_orders_permitted": False,
            "runtime_go_no_go": "NO_GO", "safety_hold_latched": True,
        }))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
