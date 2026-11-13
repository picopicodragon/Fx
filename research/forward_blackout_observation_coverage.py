"""FWD-701..720: offline *research-only* event blackout observation coverage.

Builds ±15-minute time windows from verified saved BLS ICS and strictly
validated user-provided USD/EUR/JPY macro observations. Compares those
windows to the timestamps in copied MT4 quote-session metadata. No live
timer, quote polling, MT4/broker access, approval, order routing, or
inference that overlapping quotes demonstrate a successful trading pause.
"""
from __future__ import annotations

import json
from datetime import timedelta, timezone
from pathlib import Path

from research import forward_bls_saved_html_audit as bls_audit
from research import forward_bls_snapshot_diff as integrity
from research import forward_bls_dual_snapshot as bls_snapshot
from research import forward_global_macro_evidence as macro
from research.offline_backtest import InputError

SCHEMA = "fx_fwd_blackout_observation_coverage_v1"
WINDOW_MINUTES = 15
MAX_WINDOWS = 400
MAX_SESSIONS = 24
MAX_PREVIEW = 16
PAIR_SCOPE = ("USD/JPY", "EUR/JPY", "EUR/USD")


def _text(moment) -> str:
    return moment.astimezone(timezone.utc).isoformat(
        timespec="seconds").replace("+00:00", "Z")


def inspect(*, asof_utc: str, bls_snapshot_dir: Path | None = None,
            external_observations: dict | None = None,
            copied_sessions: list[dict] | None = None) -> dict:
    asof = macro._utc(asof_utc)
    if copied_sessions is None:
        copied_sessions = []
    if type(copied_sessions) is not list or len(copied_sessions) > MAX_SESSIONS:
        raise InputError("invalid copied MT4 session count")
    intervals = []
    seen_labels = set()
    for row in copied_sessions:
        if (type(row) is not dict
                or set(row) != {"label", "first_observation_utc",
                               "last_observation_utc"}
                or type(row["label"]) is not str
                or not 1 <= len(row["label"]) <= 40
                or row["label"] in seen_labels):
            raise InputError("unsafe copied-session interval")
        seen_labels.add(row["label"])
        start = macro._utc(row["first_observation_utc"])
        end = macro._utc(row["last_observation_utc"])
        if end < start or end > asof:
            raise InputError("invalid copied-session timeline")
        intervals.append((start, end, row["label"]))
    events: list[tuple[object, str, str]] = []
    bls_slot_disagreement = None
    if bls_snapshot_dir is not None:
        audit = bls_audit.inspect(bls_snapshot_dir)
        if audit["status"] != "BLS_SAVED_HTML_ICS_AUDIT_HOLD_NO_GO":
            raise InputError("BLS audit status is unsafe")
        bls_slot_disagreement = audit["comparison"] == (
            "SAVED_HTML_ICS_SLOT_COUNTS_DISAGREE")
        manifest = integrity.verify(bls_snapshot_dir)
        if macro._utc(manifest[
                "html_observed_at_utc_local_clock_unattested"]) > asof:
            raise InputError("saved BLS source observed after review time")
        calendar = json.loads(integrity._bytes(
            bls_snapshot_dir, bls_snapshot.CAL_NAME,
            integrity.MAX_CALENDAR))
        if type(calendar) is not dict or type(calendar.get("events")) is not list:
            raise InputError("invalid saved BLS calendar")
        for event in calendar["events"]:
            at = macro._utc(event["scheduled_at_utc"])
            events.append((at, "USD/JPY", "BLS_ICS"))
            events.append((at, "EUR/USD", "BLS_ICS"))
    if external_observations is not None:
        validated = macro.inspect_observations(
            external_observations, asof_utc=asof_utc)
        for event in validated["event_evidence_preview"]:
            # The validator emits only the first MAX_OUTPUT_EVENTS. The full
            # plan below must use all validated input events, not this preview.
            if event["blackout_or_order_runtime_connected"] is not False:
                raise InputError("external macro source cannot authorize orders")
        for record in external_observations["events"]:
            at = macro._utc(record["scheduled_at_utc"])
            for pair in macro.PAIRS[record["currency"]]:
                events.append((at, pair, "EXTERNAL_SOURCE_UNATTESTED"))
    dedup = {}
    for at, pair, source in events:
        if pair not in PAIR_SCOPE:
            raise InputError("unapproved research pair")
        key = (_text(at), pair)
        dedup.setdefault(key, set()).add(source)
    if len(dedup) > MAX_WINDOWS:
        raise InputError("too many research blackout windows")
    covered = 0
    previews = []
    crossing_pair_counts = {pair: 0 for pair in PAIR_SCOPE}
    for (iso, pair), sources in sorted(dedup.items()):
        at = macro._utc(iso)
        start = at - timedelta(minutes=WINDOW_MINUTES)
        end = at + timedelta(minutes=WINDOW_MINUTES)
        intersect = [
            label for a, b, label in intervals
            if a <= end and b >= start
        ]
        if intersect:
            covered += 1
            crossing_pair_counts[pair] += 1
        if len(previews) < MAX_PREVIEW:
            previews.append({
                "event_at_utc_unattested": iso,
                "pair": pair,
                "blackout_start_utc_research_only": _text(start),
                "blackout_end_utc_research_only": _text(end),
                "source_families_unattested": sorted(sources),
                "copied_observer_session_labels_overlapping": intersect,
                "real_order_stop_evidence": False,
            })
    holds = {
        "RESEARCH_WINDOWS_ARE_NOT_ACTIVE_BROKER_BLACKOUTS",
        "COPIED_MT4_QUOTES_NEVER_ATTEST_DEMO_ORDER_SUPPRESSION",
        "BLACKOUT_RECOVERY_AND_EVENT_PRIORITY_NOT_INDEPENDENTLY_VALIDATED",
    }
    actions = []
    if not dedup:
        holds.add("NO_RESEARCH_BLACKOUT_EVENT_WINDOWS_FROM_VERIFIED_SOURCE")
        actions.append("OBTAIN_VERIFIABLE_FUTURE_EVENT_CALENDAR_EVIDENCE")
    if not intervals:
        holds.add("NO_COPIED_MT4_SESSION_INTERVALS_FOR_EVENT_COVERAGE")
        actions.append("COLLECT_COPIED_MT4_READONLY_OBSERVATION_TIMELINES")
    if bls_slot_disagreement:
        holds.add("BLS_HTML_ONLY_EVENTS_NOT_IN_REHEARSED_ICS_WINDOWS")
        actions.append("RECONCILE_BLS_ICS_HTML_COUNT_DISAGREEMENT")
    if len(dedup) > covered:
        holds.add("SOME_RESEARCH_WINDOWS_LACK_OVERLAPPING_COPIED_QUOTES")
    return {
        "schema": SCHEMA,
        "status": "OFFLINE_BLACKOUT_OBSERVATION_COVERAGE_HOLD_NO_GO",
        "asof_utc": asof_utc,
        "research_window_minutes_each_side": WINDOW_MINUTES,
        "bls_saved_ics_source_supplied": bls_snapshot_dir is not None,
        "bls_html_ics_disagreement_unresolved": bls_slot_disagreement,
        "external_event_observations_supplied":
            len(external_observations["events"])
            if external_observations is not None else 0,
        "copied_mt4_session_interval_count": len(intervals),
        "unique_pair_blackout_research_window_count": len(dedup),
        "windows_with_intersecting_copied_quotes": covered,
        "windows_without_intersecting_copied_quotes": len(dedup)-covered,
        "pair_windows_with_copied_quote_overlap_unattested":
            crossing_pair_counts,
        "research_window_previews_unattested": previews,
        "preview_omitted_count": max(0, len(dedup)-MAX_PREVIEW),
        "rehearsal_is_live_blackout_or_release_control": False,
        "demonstrated_order_suppression": False,
        "verified_order_recovery": False,
        "unresolved_holds": sorted(holds),
        "next_research_actions": actions,
        "files_written_this_run": 0, "network_calls_this_run": 0,
        "API_calls_this_run": 0, "orders_sent_this_run": 0,
        "demo_orders_permitted": False,
        "real_orders_permitted": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
    }
