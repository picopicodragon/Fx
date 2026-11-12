"""FWD-161..170: review-linked, strictly subsequent bid/ask shadow scorecard.

There is no position sizing, fill, commission, broker call or permission gate.
A spread-adjusted per-unit mark from two observed snapshots is descriptive,
NOT a simulated executable return or evidence of strategy profitability.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from research.forward_macro_evidence_readiness import inspect as readiness
from research.forward_mt4_multisession_reliability import _parse_labeled_entries
from research.forward_shadow_causal_replay import _load_session_quotes
from research.forward_shadow_quote_quality import PIP
from research.offline_backtest import InputError, timestamp

SCHEMA = "fx_fwd_macro_two_snapshot_outcome_v1"
MAX_ENTRY_DELAY = timedelta(seconds=120)
MAX_NEXT_SNAPSHOT_GAP = timedelta(seconds=75)
MAX_SPREAD_PIPS = Decimal("5")
MAX_RECORDS = 2000
STRUCTURAL_VETO = {
    "CSV_REPLAY_ACROSS_SESSIONS",
    "OVERLAPPING_SESSION_OBSERVATION_WINDOWS",
    "INCOMPLETE_THREE_PAIR_CYCLE",
    "PARTIAL_THREE_PAIR_CYCLES",
    "CAPTURE_INTERVAL_NOT_60S",
    "TIMER_INTERVAL_OUT_OF_TOLERANCE",
    "MORE_THAN_30_CYCLES_IN_FOLDER",
    "SESSION_EXCEEDS_30_CAPTURE_CYCLES",
    "EURUSD_USDJPY_CONVERSION_INCONSISTENT",
    "REVIEWER_AND_BUILDER_MODEL_ID_MATCH",
    "MULTIPLE_RESEARCH_REVIEWS_FOR_ONE_HYPOTHESIS",
}


def inspect(sessions: list[tuple[str, Path]], *, store: Path | None,
            asof_utc: str) -> dict:
    cutoff = timestamp(asof_utc)
    base = readiness(sessions, asof_utc=asof_utc, store=store)
    alerts = set(base["source_holds_and_warnings"])
    candidates = base["candidate_records"]
    if len(candidates) > MAX_RECORDS:
        raise InputError("too many review candidates")
    structural_veto = bool(alerts & STRUCTURAL_VETO)
    if structural_veto:
        alerts.add("SOURCE_INTEGRITY_VETO_PREVENTS_OUTCOME_MARKS")
    else:
        alerts.add("UNVERIFIED_EVENT_CALENDAR_BLACKOUT_COVERAGE")
    quotes = {}
    if not structural_veto:
        for label, directory in sessions:
            quotes[label] = _load_session_quotes(directory)
    marks = []
    skipped = []
    for candidate in candidates:
        pair = candidate["pair"]
        direction = candidate["direction"]
        review_t = timestamp(candidate["review_captured_at_utc"])
        release_t = timestamp(candidate["event_published_at_utc"])
        event_received = timestamp(candidate["event_captured_at_utc"])
        if not candidate["model_ids_differ"]:
            skipped.append({"review_sha256":candidate["review_record_sha256"],
                            "reason":"REVIEW_MODEL_IDS_NOT_DISTINCT"})
            continue
        if structural_veto:
            skipped.append({"review_sha256":candidate["review_record_sha256"],
                            "reason":"SOURCE_INTEGRITY_VETO"})
            continue
        if review_t < event_received or review_t > cutoff:
            raise InputError("invalid macro event/review capture sequence")
        # Publication time is NOT independently verified as release time.
        # Nevertheless decline to score within the 15-minute window of a
        # self-reported event publication, and never treat this as a full
        # macro-economic calendar blackout gate.
        eligible = []
        for label, records in quotes.items():
            for i, (entry_time, group) in enumerate(records[:-1]):
                if not (review_t < entry_time <= review_t + MAX_ENTRY_DELAY):
                    continue
                if (release_t - timedelta(minutes=15)
                        <= entry_time < release_t + timedelta(minutes=15)):
                    continue
                exit_time, exit_group = records[i+1]
                if (exit_time > cutoff
                        or exit_time - entry_time > MAX_NEXT_SNAPSHOT_GAP):
                    continue
                eligible.append((
                    entry_time, exit_time, label, group, exit_group
                ))
        if not eligible:
            skipped.append({
                "review_sha256": candidate["review_record_sha256"],
                "reason": "NO_POST_REVIEW_PAIR_OF_SNAPSHOTS_OUTSIDE_KNOWN_BLACKOUT",
            })
            continue
        # Exactly one earliest eligible observed pair, with no session jump.
        eligible.sort(key=lambda r: (r[0], r[2]))
        entry_time, exit_time, label, g0, g1 = eligible[0]
        entry = g0[pair]
        end = g1[pair]
        b0 = Decimal(entry["bid"])
        a0 = Decimal(entry["ask"])
        b1 = Decimal(end["bid"])
        a1 = Decimal(end["ask"])
        spread = (a0-b0)/PIP[pair]
        if spread > MAX_SPREAD_PIPS:
            skipped.append({"review_sha256":candidate["review_record_sha256"],
                            "reason":"ENTRY_SPREAD_OVER_RESEARCH_LIMIT"})
            continue
        if direction == "LONG":
            entry_side, exit_side = a0, b1
            delta = (exit_side-entry_side)/PIP[pair]
        else:
            entry_side, exit_side = b0, a1
            delta = (entry_side-exit_side)/PIP[pair]
        marks.append({
            "research_review_sha256": candidate["review_record_sha256"],
            "research_hypothesis_sha256":
                candidate["hypothesis_record_sha256"],
            "pair": pair, "direction": direction,
            "session_label": label,
            "entry_observation_utc":
                entry_time.isoformat().replace("+00:00", "Z"),
            "exit_observation_utc":
                exit_time.isoformat().replace("+00:00", "Z"),
            "entry_quote_side": str(entry_side),
            "exit_quote_side": str(exit_side),
            "entry_spread_pips": str(spread),
            "two_snapshot_spread_adjusted_change_pips_per_unit":
                str(delta),
            "actual_fill_executed": False,
            "underlying_event_and_review_authenticated": False,
        })
    if not candidates:
        alerts.add("NO_MACRO_APPROVED_NON_HOLD_CANDIDATES")
    if not marks:
        alerts.add("NO_CAUSALLY_EVALUABLE_SHADOW_MARKS")
    by_pair = {}
    for pair in PIP:
        values = [
            Decimal(m["two_snapshot_spread_adjusted_change_pips_per_unit"])
            for m in marks if m["pair"] == pair
        ]
        by_pair[pair] = {
            "descriptive_mark_count": len(values),
            "positive_marks": sum(x > 0 for x in values),
            "negative_marks": sum(x < 0 for x in values),
            "zero_marks": sum(x == 0 for x in values),
            "total_two_snapshot_pips_per_unit": (
                str(sum(values, Decimal("0"))) if values else None),
            "representative_return_or_proven_edge": False,
        }
    return {
        "schema": SCHEMA,
        "status": "FORWARD_MACRO_REVIEW_LINKED_RESEARCH_HOLD_NO_GO",
        "asof_utc": asof_utc,
        "price_csv_count": base["quote_csv_count"],
        "complete_cycle_count": base["quote_complete_cycles"],
        "macro_event_count": base["macro_event_count"],
        "macro_review_count": base["macro_review_count"],
        "structural_veto": structural_veto,
        "research_only_candidate_count": len(candidates),
        "two_snapshot_descriptive_mark_count": len(marks),
        "skipped_candidates": skipped,
        "spread_adjusted_marks": marks,
        "descriptive_pair_summary": by_pair,
        "holds_and_limitations": sorted(alerts),
        "risk_sized_positions_created": 0,
        "simulated_order_fills_created": 0,
        "actual_broker_order_calls": 0,
        "AI_inference_calls": 0,
        "historical_lookahead_excluded_by_supplied_timestamps_only": True,
        "economic_calendar_all_events_excluded": False,
        "proven_out_of_sample_strategy_edge": False,
        "trading_permission": "NO_GO",
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
        "real_orders_permitted": False,
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description="Offline reviewed macro two-snapshot scorecard, NO_GO")
    p.add_argument("--session", action="append", required=True)
    p.add_argument("--store", type=Path)
    p.add_argument("--asof-utc", required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args(argv)
    try:
        sessions = list(_parse_labeled_entries(
            a.session, "--session").items())
        sources = [directory.resolve() for _, directory in sessions]
        if a.store is not None:
            sources.append(a.store.resolve())
        if (a.out.exists() or a.out.is_symlink()
                or not a.out.parent.is_dir()
                or any(source in a.out.resolve().parents
                       for source in sources)):
            raise InputError("unsafe research report output")
        report = inspect(sessions, store=a.store, asof_utc=a.asof_utc)
        with a.out.open("x", encoding="utf-8") as file:
            json.dump(report, file, indent=2, ensure_ascii=False)
        print(json.dumps({
            "status": report["status"],
            "price_csv_count": report["price_csv_count"],
            "macro_events": report["macro_event_count"],
            "descriptive_marks": report["two_snapshot_descriptive_mark_count"],
            "holds_and_limitations": report["holds_and_limitations"],
            "runtime_go_no_go": "NO_GO", "real_orders_permitted": False,
        }))
        return 0
    except (InputError, OSError, ValueError, TypeError, KeyError,
            UnicodeError, ArithmeticError, OverflowError):
        print(json.dumps({
            "status": "FAIL_CLOSED",
            "reason": "MACRO_OUTCOME_RESEARCH_EVIDENCE_INVALID",
            "runtime_go_no_go": "NO_GO",
            "safety_hold_latched": True,
            "real_orders_permitted": False,
        }))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
