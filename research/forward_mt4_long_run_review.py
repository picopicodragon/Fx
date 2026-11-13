"""FWD-521..552: bounded offline multi-session MT4 observer readiness.

Consumes copied CSV/log evidence through the existing strict MT4 audit.
Can summarize evidence across observation days; cannot attest that MT4
was truly connected, a demo account was used, or any order was disabled.
Does not open MT4 or other processes.
"""
from __future__ import annotations

import argparse
import json
from datetime import timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from research import forward_mt4_multisession_reliability as reliability
from research.offline_backtest import InputError, timestamp

SCHEMA = "fx_fwd_mt4_observer_long_run_readiness_v1"
NEW_YORK = ZoneInfo("America/New_York")


def _ny17_bucket(utc_str: str) -> str:
    local = timestamp(utc_str).astimezone(NEW_YORK)
    date = local.date()
    if local.hour >= 17:
        date += timedelta(days=1)
    return date.isoformat()


def inspect(sessions: list[tuple[str, Path]], *, asof_utc: str,
            experts: dict[str, Path] | None = None,
            compiles: dict[str, Path] | None = None) -> dict:
    timestamp(asof_utc)
    if (type(sessions) is not list
            or len(sessions) > reliability.MAX_SESSIONS):
        raise InputError("invalid number of copied MT4 sessions")
    holds = set()
    actions = []
    source = None
    if sessions:
        source = reliability.inspect(
            sessions, asof_utc=asof_utc,
            experts=experts, compiles=compiles)
        if (source.get("status") != "MT4_MULTISESSION_RESEARCH_HOLD_NO_GO"
                or source["runtime_go_no_go"] != "NO_GO"
                or source["safety_hold_latched"] is not True
                or source["real_orders_permitted"] is not False
                or source["demo_orders_permitted"] is not False):
            raise InputError("MT4 observer source escapes research-only scope")
        holds.update(source["issues_and_safety_holds"])
    elif experts or compiles:
        raise InputError("logs cannot be provided without copied MT4 sessions")
    else:
        holds.add("NO_COPIED_MT4_OBSERVER_CSV_SESSIONS")
        actions.append("COLLECT_OFFLINE_MT4_DEMO_READONLY_CSV_SESSIONS")
    summaries = source["sessions"] if source else []
    if len(summaries) < 2:
        holds.add("INSUFFICIENT_DISTINCT_MT4_OBSERVATION_SESSIONS")
        actions.append("COLLECT_DISTINCT_NOORDER_MT4_OBSERVATION_SESSIONS")
    buckets = sorted({
        _ny17_bucket(row["first_observation_utc"]) for row in summaries
    })
    if len(buckets) < 2:
        holds.add("MT4_OBSERVATIONS_NOT_YET_SPANNING_TWO_NY17_BUCKETS")
        actions.append("EXTEND_INDEPENDENT_OBSERVATION_TIME_BUCKETS")
    missing_logs = [
        row["label"] for row in summaries
        if not row["expert_log_supplied"] or not row["compile_log_supplied"]
    ]
    if missing_logs:
        holds.add("MT4_OBSERVER_LOGS_OR_COMPILE_EVIDENCE_INCOMPLETE")
        actions.append("ARCHIVE_OBSERVER_EXPERT_AND_COMPILE_LOGS")
    all_30 = bool(summaries) and all(
        row["complete_cycles"] == 30
        and row["incomplete_cycles"] == 0
        and row["stop_evidence_assessment"]
        == "SELF_REPORTED_CAP_MARKER_AND_30_CSV_CYCLES"
        for row in summaries)
    if not all_30:
        holds.add("THIRTY_CYCLE_CAP_STOP_NOT_DOCUMENTED_FOR_ALL_SESSIONS")
        actions.append("VERIFY_30_CYCLE_STOP_MARKERS_WITH_COPIED_LOGS")
    holds.update({
        "BROKER_DEMO_ACCOUNT_IDENTITY_AND_SERVER_CLOCK_UNATTESTED",
        "MT4_AUTOTRADING_OFF_AND_ORDER_PATH_NOT_INDEPENDENTLY_VERIFIED",
        "OBSERVATION_EVIDENCE_DOES_NOT_AUTHORIZE_DEMO_ORDERS",
    })
    return {
        "schema": SCHEMA,
        "status": "MT4_MULTIDAY_NOORDER_OBSERVATION_HOLD_NO_GO",
        "asof_utc": asof_utc,
        "verified_format_copied_session_count": len(summaries),
        "csv_file_count": source["csv_file_count"] if source else 0,
        "complete_observation_cycle_count":
            source["complete_cycle_count"] if source else 0,
        "incomplete_observation_cycle_count":
            source["incomplete_cycle_count"] if source else 0,
        "distinct_ny17_bucket_count": len(buckets),
        "ny17_bucket_dates_observed_unattested": buckets,
        "all_sessions_have_self_reported_30cycle_stop_markers": all_30,
        "session_labels_with_missing_logs": missing_logs[:24],
        "source_observation_issues": (
            source["issues_and_safety_holds"] if source else []),
        "copied_observation_intervals_unattested": [
            {
                "label": row["label"],
                "first_observation_utc": row["first_observation_utc"],
                "last_observation_utc": row["last_observation_utc"],
            }
            for row in summaries
        ],
        "unresolved_holds": sorted(holds),
        "next_research_actions": list(dict.fromkeys(actions)),
        "source_broker_or_demo_identity_independently_attested": False,
        "extended_live_mt4_connection_verified": False,
        "broker_clock_independently_verified": False,
        "orders_and_auto_trading_independently_proven_disabled": False,
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
        description="Offline MT4 long-run CSV + log evidence NO_GO audit")
    p.add_argument("--session", action="append", default=[])
    p.add_argument("--experts", action="append", default=[])
    p.add_argument("--compile", action="append", default=[])
    p.add_argument("--asof-utc", required=True)
    args = p.parse_args(argv)
    try:
        session_map = reliability._parse_labeled_entries(
            args.session, "--session")
        experts = reliability._parse_labeled_entries(args.experts, "--experts")
        compiles = reliability._parse_labeled_entries(args.compile, "--compile")
        result = inspect(
            list(session_map.items()), asof_utc=args.asof_utc,
            experts=experts, compiles=compiles)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (InputError, OSError, ValueError, TypeError, KeyError,
            UnicodeError, ArithmeticError, OverflowError):
        print(json.dumps({
            "schema": SCHEMA,
            "status": "MT4_MULTIDAY_OBSERVATION_FAIL_CLOSED_NO_GO",
            "reason_code": "UNSAFE_OR_CONFLICTING_COPIED_MT4_EVIDENCE",
            "files_written_this_run": 0, "network_calls_this_run": 0,
            "API_calls_this_run": 0, "orders_sent_this_run": 0,
            "demo_orders_permitted": False, "real_orders_permitted": False,
            "runtime_go_no_go": "NO_GO", "safety_hold_latched": True,
        }))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
