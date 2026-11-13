"""FWD-1201..1280: bounded point-in-time multi-snapshot macro evidence ledger.

Audits user-listed, already-saved USD/EUR/JPY original-source manifests in
capture order, pins exact manifest SHA256, re-verifies EVERY raw source via
forward_regional_source_intake, detects explicit event revisions and
point-in-time forecast evidence loss. These are LOCAL claims, not publisher
authentications. Never edits originals, rewrites history, fills missing
events, contacts a broker, or authorizes orders.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import timedelta
from pathlib import Path

from research import forward_global_macro_evidence as macro
from research import forward_regional_source_intake as originals
from research.offline_backtest import InputError

SCHEMA = "fx_fwd_regional_evidence_history_manifest_v1"
REPORT = "fx_fwd_regional_evidence_history_readiness_v1"
MAX_HISTORY_BYTES = 20_000
MAX_MANIFESTS = 32
MAX_REVISION_PREVIEW = 24
MAX_EVENTS_PER_SNAPSHOT = macro.MAX_EVENTS
HISTORY_FIELDS = frozenset({"schema", "entries"})
ENTRY_FIELDS = frozenset({"manifest_path", "manifest_sha256"})
SHA256 = re.compile(r"^[0-9a-f]{64}$")
PAIRS = ("USD/JPY", "EUR/JPY", "EUR/USD")
CURRENCIES = ("USD", "EUR", "JPY")


def _verified_file(path: Path, max_bytes: int) -> bytes:
    if (not isinstance(path, Path) or path.is_symlink()
            or any(parent.is_symlink() for parent in path.parents)
            or not path.is_file()
            or not 0 < path.stat().st_size <= max_bytes):
        raise InputError("missing, symlinked, or oversized evidence file")
    data = path.read_bytes()
    if not 0 < len(data) <= max_bytes:
        raise InputError("evidence file changed while reading")
    return data


def _entry_path(history_file: Path, name: object) -> Path:
    if (type(name) is not str or not 1 <= len(name) <= 1024
            or name.strip() != name
            or any(char in name for char in ("\x00", "\n", "\r", "*", "?"))):
        raise InputError("invalid explicit history source path")
    path = Path(name)
    if not path.is_absolute():
        path = history_file.parent / path
    return path.absolute()


def _material(entry: dict) -> tuple:
    cal = entry["calendar_source"]
    consensus = entry["consensus"]
    return (
        entry["event_type"], entry["title"], entry["scheduled_at_utc"],
        cal["source_url"], cal["source_sha256"],
        None if consensus is None else (
            str(consensus["value"]), consensus["unit"],
            consensus["source"]["source_url"],
            consensus["source"]["source_sha256"],
        ),
    )


def _changes(old: dict, new: dict) -> list[str]:
    changes = []
    if old["event_type"] != new["event_type"]:
        changes.append("EVENT_CATEGORY_CHANGED")
    if old["title"] != new["title"]:
        changes.append("EVENT_TITLE_CHANGED")
    if old["scheduled_at_utc"] != new["scheduled_at_utc"]:
        changes.append("PUBLISHED_RELEASE_CLOCK_CLAIM_CHANGED")
    before, after = old["calendar_source"], new["calendar_source"]
    if (before["source_url"], before["source_sha256"]) != (
            after["source_url"], after["source_sha256"]):
        changes.append("SCHEDULE_SOURCE_EXCERPT_OR_URL_CHANGED")
    before, after = old["consensus"], new["consensus"]
    if before is None and after is not None:
        changes.append("CONSENSUS_ADDED_WITH_SELF_REPORTED_TIME")
    elif before is not None and after is None:
        changes.append("CONSENSUS_NO_LONGER_PRESENT_IN_NEW_SNAPSHOT")
    elif before is not None and after is not None and (
            before["value"], before["unit"],
            before["source"]["source_url"],
            before["source"]["source_sha256"]) != (
            after["value"], after["unit"],
            after["source"]["source_url"],
            after["source"]["source_sha256"]):
        changes.append("CONSENSUS_VALUE_OR_SOURCE_CLAIM_CHANGED")
    return changes


def inspect(history_file: Path, *, asof_utc: str) -> dict:
    asof = macro._utc(asof_utc)
    raw = _verified_file(history_file, MAX_HISTORY_BYTES)
    manifest = json.loads(raw.decode("utf-8-sig"))
    if (type(manifest) is not dict or set(manifest) != HISTORY_FIELDS
            or manifest["schema"] != SCHEMA
            or type(manifest["entries"]) is not list
            or len(manifest["entries"]) > MAX_MANIFESTS):
        raise InputError("invalid saved source history manifest")
    visited_paths = set()
    previous_capture = None
    snapshots = []
    latest = {}
    revisions = []
    seen_slot_ids = {}
    latest_per_currency = {}
    for idx, item in enumerate(manifest["entries"], start=1):
        if (type(item) is not dict or set(item) != ENTRY_FIELDS
                or type(item["manifest_sha256"]) is not str
                or SHA256.fullmatch(item["manifest_sha256"]) is None):
            raise InputError("invalid history entry")
        path = _entry_path(history_file, item["manifest_path"])
        if path.resolve() == history_file.resolve():
            raise InputError("history file cannot contain itself")
        resolved = path.resolve(strict=True)
        if resolved in visited_paths:
            raise InputError("duplicate physical evidence manifest")
        visited_paths.add(resolved)
        source_bytes = _verified_file(path, originals.MAX_MANIFEST)
        if hashlib.sha256(source_bytes).hexdigest() != item["manifest_sha256"]:
            raise InputError("saved manifest content differs from pinned digest")
        observed, summary = originals.load(path, asof_utc=asof_utc)
        if (summary["status"] != "REGIONAL_ORIGINAL_SOURCE_INTAKE_HOLD_NO_GO"
                or summary["runtime_go_no_go"] != "NO_GO"
                or summary["safety_hold_latched"] is not True
                or summary["demo_orders_permitted"] is not False
                or summary["real_orders_permitted"] is not False):
            raise InputError("raw-source validator safety flags compromised")
        captured = macro._utc(observed["observed_at_utc"])
        if previous_capture is not None and captured < previous_capture:
            raise InputError("history entries are not time-ordered")
        previous_capture = captured
        snapshot_currencies = set()
        for event in observed["events"]:
            currency = event["currency"]
            identity = (currency, event["event_id"])
            slot = (currency, event["title"], event["scheduled_at_utc"])
            other_id = seen_slot_ids.get(slot)
            if other_id is not None and other_id != identity:
                raise InputError("same release title/time has conflicting event ID")
            seen_slot_ids[slot] = identity
            snapshot_currencies.add(currency)
            if identity in latest:
                old_at, old_entry = latest[identity]
                changes = _changes(old_entry, event)
                if old_at == captured and changes:
                    raise InputError("contradictory same-clock event claims")
                if changes:
                    revisions.append({
                        "currency": currency,
                        "event_id_unverified": event["event_id"],
                        "previous_observed_at_utc_clock_unattested":
                            macro._utc_str(old_at),
                        "new_observed_at_utc_clock_unattested":
                            observed["observed_at_utc"],
                        "change_types": changes,
                        "automatic_revision_acceptance": False,
                    })
            latest[identity] = (captured, event)
        for currency in snapshot_currencies:
            latest_per_currency[currency] = captured
        snapshots.append({
            "observation_index": idx,
            "observed_at_utc_clock_unattested":
                observed["observed_at_utc"],
            "manifest_sha256_local_pin": item["manifest_sha256"],
            "event_claim_count": len(observed["events"]),
            "with_consensus_claim_count": summary["pre_release_consensus_count"],
            "currencies_present_in_snapshot": sorted(snapshot_currencies),
        })
    current = {currency: 0 for currency in CURRENCIES}
    with_consensus = {currency: 0 for currency in CURRENCIES}
    affected_pairs = {pair: 0 for pair in PAIRS}
    future_count = 0
    first_future = None
    for observed_at, event in latest.values():
        event_at = macro._utc(event["scheduled_at_utc"])
        if event_at <= asof:
            continue
        future_count += 1
        currency = event["currency"]
        current[currency] += 1
        if event["consensus"] is not None:
            with_consensus[currency] += 1
        for pair in macro.PAIRS[currency]:
            affected_pairs[pair] += 1
        if first_future is None or event_at < first_future:
            first_future = event_at
    stale = {
        currency: (
            latest_per_currency.get(currency) is None
            or asof - latest_per_currency[currency] > timedelta(hours=24))
        for currency in CURRENCIES
    }
    holds = {
        "PUBLISHER_AND_LOCAL_CLOCK_NOT_INDEPENDENTLY_AUTHENTICATED",
        "FULL_FX_MACRO_EVENT_AND_CONSENSUS_COVERAGE_NOT_ATTESTED",
        "SAVED_ARCHIVES_ARE_NOT_BROKER_BLACKOUT_OR_ORDER_PERMISSION",
    }
    next_actions = []
    if not snapshots:
        holds.add("NO_SAVED_REGIONAL_EVIDENCE_HISTORY")
        next_actions.append("REGISTER_REAL_SAVED_REGIONAL_ORIGINAL_MANIFESTS")
    for currency in CURRENCIES:
        if not current[currency]:
            holds.add("NO_UPCOMING_" + currency + "_EVENT_IN_SAVED_HISTORY")
            next_actions.append("CAPTURE_FUTURE_" + currency + "_SCHEDULE_ORIGINAL")
        if current[currency] > with_consensus[currency]:
            holds.add("MISSING_" + currency + "_POINT_IN_TIME_CONSENSUS")
            next_actions.append("CAPTURE_PRE_BLACKOUT_" + currency + "_CONSENSUS_ORIGINAL")
        if stale[currency]:
            holds.add("STALE_OR_MISSING_" + currency + "_CAPTURE_WITHIN_24H")
            next_actions.append("CAPTURE_FRESH_" + currency + "_ORIGINAL_IF_AVAILABLE")
    if revisions:
        holds.add("SAVED_RELEASE_OR_CONSENSUS_REVISIONS_REQUIRE_REVIEW")
        next_actions.append("INDEPENDENTLY_RECONCILE_CHANGED_EVENT_CLAIMS")
    return {
        "schema": REPORT,
        "status": "REGIONAL_EVIDENCE_HISTORY_RESEARCH_HOLD_NO_GO",
        "asof_utc_clock_unattested": asof_utc,
        "history_file_sha256_local_integrity_only":
            hashlib.sha256(raw).hexdigest(),
        "registered_snapshot_count": len(snapshots),
        "registered_manifest_source_count": len(visited_paths),
        "total_raw_event_claim_instances": sum(
            x["event_claim_count"] for x in snapshots),
        "distinct_event_ids_across_history": len(latest),
        "recorded_revision_occurrence_count": len(revisions),
        "revision_preview": revisions[:MAX_REVISION_PREVIEW],
        "revision_preview_omitted_count":
            max(0, len(revisions) - MAX_REVISION_PREVIEW),
        "latest_manifest_observation_by_currency_unattested": {
            c: (macro._utc_str(latest_per_currency[c])
                if c in latest_per_currency else None)
            for c in CURRENCIES
        },
        "capture_missing_or_older_than_24h_by_currency": stale,
        "upcoming_event_count_by_currency_unattested": current,
        "upcoming_event_with_consensus_count_by_currency_unattested":
            with_consensus,
        "upcoming_unverified_event_count": future_count,
        "potentially_affected_pair_event_counts_research_only":
            affected_pairs,
        "earliest_upcoming_release_utc_unattested": (
            macro._utc_str(first_future) if first_future is not None else None),
        "saved_snapshots_preview": snapshots[:MAX_REVISION_PREVIEW],
        "saved_snapshots_preview_omitted_count":
            max(0, len(snapshots) - MAX_REVISION_PREVIEW),
        "unresolved_holds": sorted(holds),
        "next_research_actions": next_actions,
        "title_or_schedule_revisions_automatically_applied_to_trading": False,
        "future_event_coverage_claimed_complete": False,
        "independent_publisher_or_clock_authentication": False,
        "point_in_time_forecast_meaning_independently_verified": False,
        "real_time_release_blackout_executed": False,
        "broker_mt4_connection_attempted": False,
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
        description="Offline regional saved-source revision/freshness campaign")
    parser.add_argument("--history-file", type=Path, required=True)
    parser.add_argument("--asof-utc")
    a = parser.parse_args(argv)
    try:
        if a.asof_utc is None:
            from datetime import datetime, timezone
            asof = datetime.now(timezone.utc).isoformat(
                timespec="seconds").replace("+00:00", "Z")
        else:
            asof = a.asof_utc
        report = inspect(a.history_file, asof_utc=asof)
        print(json.dumps(report, ensure_ascii=False, allow_nan=False))
        return 0
    except (InputError, OSError, TypeError, ValueError, KeyError,
            UnicodeError, ArithmeticError, OverflowError):
        print(json.dumps({
            "schema": REPORT,
            "status": "REGIONAL_EVIDENCE_HISTORY_FAIL_CLOSED_NO_GO",
            "reason_code": "INVALID_OR_UNATTESTED_EVIDENCE_HISTORY",
            "network_calls_this_run": 0, "API_calls_this_run": 0,
            "orders_sent_this_run": 0, "demo_orders_permitted": False,
            "real_orders_permitted": False,
            "runtime_go_no_go": "NO_GO", "safety_hold_latched": True,
        }))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
