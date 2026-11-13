"""FWD-409..440: offline multi-currency macro event/consensus evidence fastlane.

This is a point-in-time *claim* and source-integrity research contract.
No crawling, inference, aliasing, released values, financial instructions,
MT4 connections, approval of demo/live orders, or modification of source data.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlsplit

from research import forward_bls_macro_source_gate as bls_gate
from research.forward_macro_consensus_surprise import _number
from research.forward_macro_pre_release_capture import ALLOWED_UNITS, _url
from research.offline_backtest import InputError, timestamp

SCHEMA = "fx_fwd_external_macro_observation_v1"
REPORT = "fx_fwd_multi_region_macro_evidence_readiness_v1"
ROOT_FIELDS = frozenset(("schema", "observed_at_utc", "horizon_days", "events"))
EVENT_FIELDS = frozenset((
    "event_id", "currency", "event_type", "title",
    "scheduled_at_utc", "calendar_source", "consensus"))
SOURCE_FIELDS = frozenset((
    "source_url", "source_text", "source_sha256",
    "published_at_utc", "captured_at_utc"))
CONSENSUS_FIELDS = frozenset(("value", "unit", "source"))
CURRENCIES = ("USD", "EUR", "JPY")
CATEGORIES = frozenset((
    "MONETARY_POLICY", "INFLATION", "EMPLOYMENT", "GROWTH", "OTHER"))
PAIRS = {
    "USD": ("USD/JPY", "EUR/USD"),
    "EUR": ("EUR/JPY", "EUR/USD"),
    "JPY": ("USD/JPY", "EUR/JPY"),
}
UTC_SECONDS = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
IDENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,79}$")
DIGEST = re.compile(r"^[0-9a-f]{64}$")
MAX_INPUT_BYTES = 180_000
MAX_EVENTS = 64
MAX_OUTPUT_EVENTS = 20


def _utc(value):
    if type(value) is not str or not UTC_SECONDS.fullmatch(value):
        raise InputError("UTC timestamp must use exact seconds and Z")
    moment = timestamp(value)
    if moment.utcoffset() != timedelta(0):
        raise InputError("UTC offset invalid")
    return moment


def _source(data: object, *, event_time, observed, is_consensus: bool) -> dict:
    if type(data) is not dict or set(data) != SOURCE_FIELDS:
        raise InputError("invalid macro source fields")
    excerpt = data["source_text"]
    digest = data["source_sha256"]
    if (type(excerpt) is not str or not 1 <= len(excerpt) <= 2000
            or "\x00" in excerpt or
            type(digest) is not str or not DIGEST.fullmatch(digest)
            or hashlib.sha256(excerpt.encode("utf-8")).hexdigest() != digest):
        raise InputError("invalid macro source excerpt/hash")
    url = _url(data["source_url"])
    published = _utc(data["published_at_utc"])
    captured = _utc(data["captured_at_utc"])
    if not published <= captured <= observed < event_time:
        raise InputError("macro source time order invalid")
    if is_consensus and not captured < event_time - timedelta(minutes=15):
        raise InputError("consensus not obtained before blackout")
    return {
        "source_host_unverified": urlsplit(url).hostname.lower(),
        "source_sha256": digest,
        "published_at_utc_self_reported": data["published_at_utc"],
        "captured_at_utc_self_reported": data["captured_at_utc"],
        "publisher_and_clock_authenticated": False,
    }


def inspect_observations(payload: object, *, asof_utc: str) -> dict:
    now = _utc(asof_utc)
    if (type(payload) is not dict or set(payload) != ROOT_FIELDS
            or payload["schema"] != SCHEMA
            or type(payload["horizon_days"]) is not int
            or not 1 <= payload["horizon_days"] <= 31
            or type(payload["events"]) is not list
            or not 0 <= len(payload["events"]) <= MAX_EVENTS):
        raise InputError("external observation envelope invalid")
    observed = _utc(payload["observed_at_utc"])
    if observed > now:
        raise InputError("future external observation")
    counts = Counter()
    scheduled = []
    source_domains = set()
    seen = set()
    for entry in payload["events"]:
        if (type(entry) is not dict or set(entry) != EVENT_FIELDS
                or type(entry["event_id"]) is not str
                or not IDENT.fullmatch(entry["event_id"])
                or entry["currency"] not in CURRENCIES
                or entry["event_type"] not in CATEGORIES
                or type(entry["title"]) is not str
                or not 1 <= len(entry["title"]) <= 250
                or not entry["title"].strip()):
            raise InputError("invalid external macro event")
        at = _utc(entry["scheduled_at_utc"])
        if not observed < at <= observed + timedelta(
                days=payload["horizon_days"]):
            raise InputError("event outside captured future horizon")
        key = (entry["currency"], entry["title"], entry["scheduled_at_utc"])
        if entry["event_id"] in seen or key in seen:
            raise InputError("duplicate event identity")
        seen.add(entry["event_id"])
        seen.add(key)
        cal_src = _source(entry["calendar_source"], event_time=at,
                          observed=observed, is_consensus=False)
        source_domains.add(cal_src["source_host_unverified"])
        forecast = entry["consensus"]
        if forecast is not None:
            if (type(forecast) is not dict or
                    set(forecast) != CONSENSUS_FIELDS or
                    forecast["unit"] not in ALLOWED_UNITS):
                raise InputError("invalid external consensus record")
            _number(forecast["value"])
            fore_src = _source(forecast["source"], event_time=at,
                               observed=observed, is_consensus=True)
            source_domains.add(fore_src["source_host_unverified"])
            counts["with_consensus"] += 1
        else:
            counts["without_consensus"] += 1
        counts[entry["currency"]] += 1
        scheduled.append({
            "event_id": entry["event_id"],
            "currency": entry["currency"],
            "event_type": entry["event_type"],
            "scheduled_at_utc_unattested": entry["scheduled_at_utc"],
            "calendar_source_host_unverified":
                cal_src["source_host_unverified"],
            "consensus_excerpt_supplied": forecast is not None,
            "pair_scope_advisory_only": list(PAIRS[entry["currency"]]),
            "blackout_or_order_runtime_connected": False,
        })
    holds = {
        "GLOBAL_MACRO_EVENT_CALENDAR_COVERAGE_UNATTESTED",
        "EXTERNAL_SOURCE_PUBLICATION_TIME_AND_CLOCK_UNATTESTED",
        "CONSENSUS_VALUE_NOT_INDEPENDENTLY_VERIFIED_AGAINST_EXCERPT",
    }
    tasks = []
    for cur in CURRENCIES:
        if not counts[cur]:
            holds.add("NO_" + cur + "_EVENT_OBSERVATION")
            tasks.append("OBTAIN_POINT_IN_TIME_" + cur + "_EVENT_SOURCE")
    if counts["without_consensus"]:
        holds.add("EXTERNAL_EVENT_PRE_RELEASE_CONSENSUS_MISSING")
        tasks.append("CAPTURE_MISSING_PRE_RELEASE_CONSENSUS")
    if not payload["events"]:
        holds.add("NO_EXTERNAL_MACRO_EVENT_OBSERVATIONS")
    old = now - observed > timedelta(hours=24)
    if old:
        holds.add("EXTERNAL_MACRO_OBSERVATION_OLDER_THAN_24H")
        tasks.append("REVIEW_NEW_EXPLICIT_OFFLINE_MACRO_EVIDENCE")
    return {
        "schema": REPORT,
        "external_event_observations_supplied": len(scheduled),
        "external_observed_at_utc_local_clock_unattested":
            payload["observed_at_utc"],
        "external_observation_older_than_24h": old,
        "external_by_currency": {cur: counts[cur] for cur in CURRENCIES},
        "external_with_consensus_count": counts["with_consensus"],
        "external_missing_consensus_count": counts["without_consensus"],
        "unverified_source_hosts": sorted(source_domains),
        "event_evidence_preview": scheduled[:MAX_OUTPUT_EVENTS],
        "event_evidence_preview_omitted_count":
            max(0, len(scheduled) - MAX_OUTPUT_EVENTS),
        "unresolved_holds": sorted(holds),
        "next_research_actions": tasks,
        "external_evidence_values_and_times_independently_authenticated":
            False,
        "independent_event_calendar_coverage_proven": False,
        "no_orders_can_be_derived_from_this_observation": True,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
        "demo_orders_permitted": False,
        "real_orders_permitted": False,
    }


def inspect(*, asof_utc: str, bls_snapshot_dir: Path | None = None,
            external_observations: dict | None = None) -> dict:
    _utc(asof_utc)
    base = (inspect_observations(external_observations, asof_utc=asof_utc)
            if external_observations is not None else None)
    bls = (bls_gate.inspect(bls_snapshot_dir, asof_utc=asof_utc)
           if bls_snapshot_dir is not None else None)
    warnings = set(base["unresolved_holds"]) if base else {
        "NO_EXTERNAL_MACRO_EVENT_OBSERVATIONS",
        "GLOBAL_MACRO_EVENT_CALENDAR_COVERAGE_UNATTESTED",
        "NO_USD_EVENT_OBSERVATION",
        "NO_EUR_EVENT_OBSERVATION",
        "NO_JPY_EVENT_OBSERVATION",
        "EXTERNAL_EVENT_PRE_RELEASE_CONSENSUS_MISSING",
    }
    tasks = list(base["next_research_actions"]) if base else [
        "OBTAIN_POINT_IN_TIME_USD_EUR_JPY_EVENT_SOURCES",
        "CAPTURE_PRE_RELEASE_CONSENSUS_WITH_TIME_EVIDENCE",
    ]
    if bls is None:
        warnings.add("NO_VERIFIED_BLS_DUAL_FORMAT_SOURCE_BUNDLE")
        tasks.append("VERIFY_BLS_ICS_HTML_ORIGINAL_SOURCE_BUNDLE")
    else:
        warnings.update(bls["unresolved_holds"])
        tasks.extend(bls["next_research_actions"])
    warnings.update({
        "USD_EUR_JPY_MACRO_COVERAGE_NOT_CERTIFIED",
        "BROKER_BLACKOUT_AND_ORDER_SAFETY_NOT_VALIDATED",
    })
    return {
        "schema": REPORT,
        "status": "GLOBAL_MACRO_FORWARD_EVIDENCE_HOLD_NO_GO",
        "asof_utc": asof_utc,
        "bls_snapshot_supplied_and_integrity_checked": bls is not None,
        "bls_html_ics_disagreement": (
            bls["html_ics_slot_count_disagreement"] if bls else None),
        "bls_html_only_missing_slot_instances": (
            bls["missing_html_slot_instances"] if bls else None),
        "external_event_observations_supplied": (
            base["external_event_observations_supplied"] if base else 0),
        "external_by_currency": (
            base["external_by_currency"] if base else
            {cur: 0 for cur in CURRENCIES}),
        "external_missing_consensus_count": (
            base["external_missing_consensus_count"] if base else 0),
        "external_with_consensus_count": (
            base["external_with_consensus_count"] if base else 0),
        "source_and_forecast_authenticity_independently_verified": False,
        "all_material_macro_events_covered": False,
        "blackout_and_recovery_broker_controls_verified": False,
        "unresolved_holds": sorted(warnings),
        "next_research_actions": list(dict.fromkeys(tasks)),
        "files_written_this_run": 0,
        "network_calls_this_run": 0,
        "API_calls_this_run": 0,
        "actual_orders_sent": 0,
        "demo_orders_permitted": False,
        "real_orders_permitted": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
    }


def _load(path: Path) -> dict:
    if (not path.is_file() or path.is_symlink()
            or not 0 < path.stat().st_size <= MAX_INPUT_BYTES):
        raise InputError("external macro source file absent or invalid")
    doc = json.loads(path.read_text(encoding="utf-8-sig"))
    if type(doc) is not dict:
        raise InputError("macro document root must be object")
    return doc


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description="Single offline multi-region macro evidence audit (NO_GO)")
    p.add_argument("--asof-utc", required=True)
    p.add_argument("--bls-snapshot-dir", type=Path)
    p.add_argument("--external-macro-file", type=Path)
    args = p.parse_args(argv)
    try:
        observations = (
            _load(args.external_macro_file)
            if args.external_macro_file is not None else None)
        outcome = inspect(
            asof_utc=args.asof_utc,
            bls_snapshot_dir=args.bls_snapshot_dir,
            external_observations=observations)
        print(json.dumps(outcome, ensure_ascii=False))
        return 0
    except (InputError, OSError, UnicodeError, ValueError, TypeError,
            KeyError, ArithmeticError, OverflowError):
        print(json.dumps({
            "schema": REPORT,
            "status": "GLOBAL_MACRO_EVIDENCE_FAIL_CLOSED_NO_GO",
            "reason_code": "UNSAFE_OR_INCOMPLETE_MACRO_EVIDENCE",
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
