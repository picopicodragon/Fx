"""FWD-1121..1160: conservative saved BLS vs raw-US-page reconciliation.

Exact UTC/time + title equality is only a local byte-claim match. BLS ICS
has historically omitted an HTML-only release. Never add, infer, or approve
events based on name similarity. Never clear macro blackout / trading holds.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

from research import forward_regional_source_intake as original
from research import forward_bls_saved_html_audit as bls_audit
from research import forward_bls_dual_snapshot as bls_snapshot
from research import forward_bls_snapshot_diff as bls_integrity
from research import forward_global_macro_evidence as macro
from research.offline_backtest import InputError

SCHEMA = "fx_fwd_saved_cross_publisher_schedule_reconciliation_v1"
MAX_PREVIEW = 16


def inspect(*, asof_utc: str,
            bls_bundle: Path | None = None,
            regional_source_manifest: Path | None = None) -> dict:
    now = macro._utc(asof_utc)
    issues = {
        "BLS_ICS_HTML_BOTH_FROM_SAME_PUBLISHER_UNAUTHENTICATED",
        "CROSS_SOURCE_NAME_TIME_MATCH_IS_NOT_EVENT_AUTHENTICATION",
        "NO_AUTOMATIC_EVENT_INSERTION_OR_TRADING_AUTHORIZATION",
    }
    ics_events = []
    regional_events = []
    bls_disagree = None
    if bls_bundle is not None:
        audited = bls_audit.inspect(bls_bundle)
        if (audited.get("status") != "BLS_SAVED_HTML_ICS_AUDIT_HOLD_NO_GO"
                or audited.get("runtime_go_no_go") != "NO_GO"
                or audited.get("real_orders_permitted") is not False
                or audited.get("demo_orders_permitted") is not False
                or audited.get("safety_hold_latched") is not True):
            raise InputError("unsafe BLS source auditor")
        manifest = bls_integrity.verify(bls_bundle)
        if (macro._utc(manifest[
                "html_observed_at_utc_local_clock_unattested"]) > now):
            raise InputError("BLS bundle captured in the future")
        calendar = json.loads(bls_integrity._bytes(
            bls_bundle, bls_snapshot.CAL_NAME, bls_integrity.MAX_CALENDAR))
        if type(calendar) is not dict or type(calendar.get("events")) is not list:
            raise InputError("invalid verified BLS event source")
        for item in calendar["events"]:
            ics_events.append((item["scheduled_at_utc"], item["title"]))
        bls_disagree = audited["comparison"] == "SAVED_HTML_ICS_SLOT_COUNTS_DISAGREE"
        if bls_disagree:
            issues.add("BLS_ICS_HTML_SLOT_COUNTS_DISAGREE")
    else:
        issues.add("BLS_SAVED_SNAPSHOT_MISSING")
    if regional_source_manifest is not None:
        doc, regional = original.load(
            regional_source_manifest, asof_utc=asof_utc)
        if (regional["status"] != "REGIONAL_ORIGINAL_SOURCE_INTAKE_HOLD_NO_GO"
                or regional["runtime_go_no_go"] != "NO_GO"
                or regional["demo_orders_permitted"] is not False
                or regional["real_orders_permitted"] is not False
                or regional["safety_hold_latched"] is not True):
            raise InputError("unsafe saved regional originals")
        for item in doc["events"]:
            if (item["currency"] == "USD"
                    and urlsplit(item["calendar_source"]["source_url"]).hostname
                    == "www.bls.gov"):
                regional_events.append((
                    item["scheduled_at_utc"], item["title"]))
    else:
        issues.add("REGIONAL_ORIGINAL_SOURCE_MANIFEST_MISSING")
    if not regional_events:
        issues.add("NO_SAVED_BLS_PUBLISHER_REGIONAL_EVENTS")
    ics_counts = Counter(ics_events)
    regional_counts = Counter(regional_events)
    matches = ics_counts & regional_counts
    only_ics = ics_counts - regional_counts
    only_regional = regional_counts - ics_counts
    same_title_changed_time = sorted(set(
        title for _, title in only_ics for _, other in only_regional
        if title == other))
    same_time_different_title = sorted(set(
        at for at, _ in only_ics for other_at, _ in only_regional
        if at == other_at))
    if same_title_changed_time:
        issues.add("SAVED_BLS_SAME_TITLE_DIFFERENT_RELEASE_TIME_CLAIMS")
    if same_time_different_title:
        issues.add("SAVED_BLS_SAME_TIME_DIFFERENT_EVENT_NAME_CLAIMS")
    if only_ics or only_regional:
        issues.add("SAVED_BLS_REGIONAL_EVENT_SETS_NOT_EXACTLY_EQUAL")
    return {
        "schema": SCHEMA,
        "status": "SAVED_MACRO_SOURCE_CONFLICT_RESEARCH_HOLD_NO_GO",
        "bls_ics_source_supplied": bls_bundle is not None,
        "saved_regional_source_supplied": regional_source_manifest is not None,
        "bls_ics_html_slot_disagreement_unresolved": bls_disagree,
        "ics_saved_event_count": sum(ics_counts.values()),
        "regional_saved_bls_event_count": sum(regional_counts.values()),
        "exact_same_utc_and_title_count_local_only": sum(matches.values()),
        "ics_only_title_time_claim_count": sum(only_ics.values()),
        "regional_only_title_time_claim_count": sum(only_regional.values()),
        "same_title_different_time_unverified_count":
            len(same_title_changed_time),
        "same_time_different_title_unverified_count":
            len(same_time_different_title),
        "same_title_different_time_preview": [
            {"event_title_unverified": title}
            for title in same_title_changed_time[:MAX_PREVIEW]],
        "same_time_different_title_preview": [
            {"scheduled_at_utc_unverified": when}
            for when in same_time_different_title[:MAX_PREVIEW]],
        "unresolved_holds": sorted(issues),
        "event_identity_independently_authenticated": False,
        "bls_html_only_events_automatically_inserted": False,
        "all_fx_calendar_coverage_proven": False,
        "bls_and_saved_page_claims_are_independent_publishers": False,
        "generated_or_authorized_trading_orders": False,
        "network_calls_this_run": 0,
        "API_calls_this_run": 0,
        "orders_sent_this_run": 0,
        "demo_orders_permitted": False,
        "real_orders_permitted": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Reconcile saved BLS ICS against saved regional original claims")
    parser.add_argument("--bls-snapshot-dir", type=Path)
    parser.add_argument("--regional-source-manifest", type=Path)
    parser.add_argument("--asof-utc", required=True)
    a = parser.parse_args(argv)
    try:
        result = inspect(
            asof_utc=a.asof_utc, bls_bundle=a.bls_snapshot_dir,
            regional_source_manifest=a.regional_source_manifest)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (InputError, OSError, TypeError, ValueError, KeyError,
            UnicodeError, ArithmeticError, OverflowError):
        print(json.dumps({
            "schema": SCHEMA,
            "status": "SAVED_MACRO_SOURCE_CONFLICT_FAIL_CLOSED_NO_GO",
            "network_calls_this_run": 0, "API_calls_this_run": 0,
            "orders_sent_this_run": 0,
            "demo_orders_permitted": False,
            "real_orders_permitted": False,
            "runtime_go_no_go": "NO_GO", "safety_hold_latched": True,
        }))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
