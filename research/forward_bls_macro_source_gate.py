"""FWD-377..392: independent offline research readiness gate for saved BLS evidence.

This gate does NOT enable paper or live trading. It surfaces missing consensus
and the concrete BLS HTML/ICS mismatch to research orchestration. Snapshot
integrity and forecast records are verified before the report is built.
No network, AI requests, file writes, broker/MT4 connections, or orders.
"""
from __future__ import annotations

import argparse
from datetime import timedelta
import json
from pathlib import Path

from research import forward_bls_calendar_crosscheck as cross
from research import forward_bls_dual_snapshot as snapshot
from research import forward_bls_saved_html_audit as bls_audit
from research import forward_bls_snapshot_diff as integrity
from research.forward_macro_pre_release_capture import (
    verify_archive as verify_forecast)
from research.offline_backtest import InputError

SCHEMA = "fx_fwd_bls_macro_source_consensus_gate_v1"
MAX_FORECAST_BYTES = 8000


def _forecast_file(path: Path) -> dict:
    if (not path.is_file() or path.is_symlink()
            or not 0 < path.stat().st_size <= MAX_FORECAST_BYTES):
        raise InputError("forecast archive absent or invalid")
    doc = json.loads(path.read_text("utf-8-sig"))
    if type(doc) is not dict:
        raise InputError("forecast archive root invalid")
    return doc


def inspect(bundle: Path, *, asof_utc: str,
            forecast_archive: dict | None = None) -> dict:
    checked_now = cross._utc(asof_utc)
    # The saved-source audit invokes integrity.verify before parsing either
    # input and fails closed if any original source hash is inconsistent.
    audit = bls_audit.inspect(bundle)
    manifest = integrity.verify(bundle)
    capture_time = cross._utc(
        manifest["html_observed_at_utc_local_clock_unattested"])
    if checked_now < capture_time:
        raise InputError("cannot inspect future-local-clock snapshot")
    calendar = json.loads(
        integrity._bytes(bundle, snapshot.CAL_NAME, 160000))
    if type(calendar) is not dict:
        raise InputError("invalid original calendar report")
    ics_sha = manifest["ics_sha256"]
    if (audit["ics_source_sha256"] != ics_sha
            or audit["html_source_sha256"] != manifest["html_sha256"]
            or calendar.get("calendar_sha256") != ics_sha):
        raise InputError("snapshot/audit provenance disagreement")

    disagreement = audit["comparison"] == (
        "SAVED_HTML_ICS_SLOT_COUNTS_DISAGREE")
    if not disagreement and audit["comparison"] != (
            "SAVED_HTML_ICS_SLOT_COUNTS_MATCH_UNVERIFIED"):
        raise InputError("unsupported source comparison outcome")
    # Give the user a source-specific research task without converting
    # calendar mismatch into a tradable event or presumed blackout.
    holds = {
        "BLS_BOTH_FORMATS_SAME_PUBLISHER_NOT_INDEPENDENTLY_AUTHENTICATED",
        "BLS_MONTHLY_HTML_SELECTED_RELEASES_NOT_EXHAUSTIVE",
        "FULL_FX_MACRO_CALENDAR_NOT_ATTESTED",
        "BLS_SOURCE_PUBLICATION_AND_LOCAL_CLOCK_UNATTESTED",
        "DEMO_AND_LIVE_TRADING_AUTHORIZATION_NOT_ESTABLISHED",
    }
    actions = []
    if disagreement:
        holds.add("BLS_ICS_HTML_SCHEDULE_COUNT_DISAGREEMENT")
        actions.append("REVIEW_SAVED_HTML_ICS_RELEASE_DISCREPANCY")
    else:
        holds.add("BLS_MATCHING_SLOT_COUNTS_DO_NOT_VERIFY_EVENT_IDENTITIES")
    stale = checked_now - capture_time > timedelta(hours=24)
    if stale:
        holds.add("BLS_SAVED_SNAPSHOT_OLDER_THAN_24H")
        actions.append("TAKE_NEW_EXPLICIT_BLS_SNAPSHOT_IF_RESEARCH_NEEDED")
    aligned = False
    if forecast_archive is None:
        holds.add("POINT_IN_TIME_CONSENSUS_EVIDENCE_MISSING")
        actions.append("CAPTURE_PRE_RELEASE_CONSENSUS_WITH_TIMESTAMP_EVIDENCE")
    else:
        evidence = verify_forecast(forecast_archive, asof_utc=asof_utc)
        aligned = (
            evidence["calendar_report_sha256_self_reported"] == ics_sha
            and any(
                event["title"] == evidence["event_title_unverified"]
                and event["scheduled_at_utc"]
                == evidence["scheduled_at_utc_unverified"]
                for event in calendar["events"]))
        if not aligned:
            holds.add("FORECAST_ARCHIVE_NOT_LINKED_TO_THIS_ICS_SNAPSHOT")
            actions.append("RECONCILE_FORECAST_ARCHIVE_WITH_CALENDAR_ID")
        else:
            # A valid local SHA and timestamp prove neither source truth nor
            # that the publisher actually posted consensus pre-release.
            holds.add("CONSENSUS_SOURCE_AND_PUBLICATION_TIME_UNATTESTED")
            actions.append("VERIFY_PRE_RELEASE_CONSENSUS_SOURCE_AND_CLOCK")
    actions.extend([
        "ESTABLISH_INDEPENDENT_ECONOMIC_CALENDAR_COVERAGE",
        "VERIFY_MT4_ACCOUNT_CLOCK_RISK_AND_ORDER_DISABLE_CONTROLS",
    ])
    return {
        "schema": SCHEMA,
        "status": "BLS_MACRO_SOURCE_CONSENSUS_READINESS_HOLD_NO_GO",
        "asof_utc": asof_utc,
        "snapshot_html_observed_at_utc_clock_unattested":
            manifest["html_observed_at_utc_local_clock_unattested"],
        "calendar_ics_sha256": ics_sha,
        "calendar_html_sha256": manifest["html_sha256"],
        "ics_event_count": audit["ics_event_count"],
        "html_selected_event_count_within_window":
            audit["html_event_count_within_window"],
        "html_ics_slot_count_disagreement": disagreement,
        "missing_html_slot_instances":
            audit["missing_html_slot_instance_count"],
        "unexpected_ics_slot_instances":
            audit["unexpected_ics_slot_instance_count"],
        "disputed_slots_unverified": [
            item["scheduled_at_utc"]
            for item in audit["disputed_slot_title_evidence"]],
        "disputed_slots_omitted_count":
            audit["disputed_slots_omitted_count"],
        "snapshot_older_than_24h": stale,
        "forecast_archive_supplied": forecast_archive is not None,
        "forecast_archive_matches_saved_ics_title_time_and_digest": aligned,
        "pre_release_consensus_truth_authenticated": False,
        "source_publisher_and_clock_independently_authenticated": False,
        "macro_event_coverage_complete": False,
        "blackout_runtime_verified": False,
        "unresolved_holds": sorted(holds),
        "next_research_actions": list(dict.fromkeys(actions)),
        "files_written_this_run": 0,
        "network_calls_this_run": 0,
        "API_calls_this_run": 0,
        "actual_orders_sent": 0,
        "demo_orders_permitted": False,
        "real_orders_permitted": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description="BLS saved-source and pre-release consensus NO_GO gate")
    p.add_argument("--snapshot-dir", required=True, type=Path)
    p.add_argument("--asof-utc", required=True)
    p.add_argument("--forecast-archive", type=Path)
    args = p.parse_args(argv)
    try:
        archive = (_forecast_file(args.forecast_archive)
                   if args.forecast_archive else None)
        result = inspect(
            args.snapshot_dir, asof_utc=args.asof_utc,
            forecast_archive=archive)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (InputError, OSError, UnicodeError, ValueError,
            TypeError, KeyError, ArithmeticError, OverflowError):
        print(json.dumps({
            "schema": SCHEMA,
            "status": "BLS_MACRO_SOURCE_CONSENSUS_FAIL_CLOSED_NO_GO",
            "reason_code": "INVALID_BLS_BUNDLE_OR_FORECAST_PROVENANCE",
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
