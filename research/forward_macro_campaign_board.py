"""FWD-171..182: single-command, all-offline FX macro research readiness board.

Unifies already-audited MT4 sessions, observation macro journal, AI request
ledger and post-review snapshot marks. It NEVER calls provider APIs, enables
orders, computes live signals, retries pending paid requests or authenticates
broker provenance. A 'next_action' is a research task, NOT authorization.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from research.forward_macro_evidence_readiness import inspect as macro_evidence
from research.forward_macro_reviewed_outcomes import inspect as outcomes
from research.forward_shadow_quote_quality import inspect as quote_quality
from research.forward_shadow_time_regimes import inspect as time_regimes
from research.forward_mt4_multisession_reliability import _parse_labeled_entries
from research.offline_backtest import InputError, timestamp

SCHEMA = "fx_fwd_macro_research_campaign_board_v1"


def inspect(sessions: list[tuple[str, Path]], *, asof_utc: str,
            store: Path | None = None,
            ai_ledgers: list[Path] | None = None) -> dict:
    timestamp(asof_utc)
    # Source files are re-audited by each independent consumer. No claim of
    # atomic full-system snapshot or broker-authenticated feed is made.
    quality = quote_quality(sessions, asof_utc=asof_utc)
    coverage = time_regimes(sessions, asof_utc=asof_utc)
    macro = macro_evidence(sessions, asof_utc=asof_utc,
                           store=store, ai_ledgers=ai_ledgers)
    score = outcomes(sessions, asof_utc=asof_utc, store=store)
    if (quality["files"] != coverage["csv_file_count"]
            or quality["files"] != macro["quote_csv_count"]
            or score["price_csv_count"] != quality["files"]
            or score["complete_cycle_count"] != quality["cycle_count"]):
        raise InputError("inconsistent multi-component evidence size")
    # Deterministic status, not a claim that any stage passed independent
    # authentication. Context is deliberately limited to counts and SHA-256.
    snapshot = {
        "asof_utc": asof_utc,
        "price_csv_count": quality["files"],
        "complete_cycles": quality["cycle_count"],
        "macro_events": macro["macro_event_count"],
        "macro_reviews": macro["macro_review_count"],
        "outcome_marks": score["two_snapshot_descriptive_mark_count"],
    }
    manifest_sha = hashlib.sha256(json.dumps(
        snapshot, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    actions = []
    if store is None:
        actions.append("ESTABLISH_LOCAL_HASH_CHAIN_MACRO_JOURNAL")
    if macro["macro_event_count"] == 0:
        actions.append("CAPTURE_REAL_POINT_IN_TIME_MACRO_EVENTS")
    if macro["macro_event_missing_consensus_count"] or not macro["macro_event_count"]:
        actions.append("OBTAIN_PRE_RELEASE_CONSENSUS_WITH_TIME_EVIDENCE")
    if macro["macro_event_count"] and macro["macro_review_count"] == 0:
        actions.append("RUN_BOUNDED_EXPLICIT_TWO_MODEL_RESEARCH_WHEN_FUNDED")
    if macro["ledger_count"] and any(
            ledger["pending_request"] is not None
            for ledger in macro["ledger_evidence"]):
        actions.append("MANUALLY_RECONCILE_AMBIGUOUS_PAID_API_CALL_FIRST")
    if (macro["research_only_candidate_count"] > 0
            and score["two_snapshot_descriptive_mark_count"] == 0):
        actions.append("GATHER_POST_REVIEW_QUOTES_IN_SAME_DEMO_SESSION")
    if "INSUFFICIENT_TIME_OF_DAY_COVERAGE" in (
            coverage["coverage_and_safety_holds"]):
        actions.append("EXTEND_DISTINCT_OBSERVATION_TIME_BUCKETS")
    actions.append("INDEPENDENTLY_REVIEW_MT4_ACCOUNT_CLOCK_AND_CAP_LOG")
    warnings = sorted(set(
        quality["data_quality_alerts_and_safety_holds"] +
        coverage["coverage_and_safety_holds"] +
        macro["source_holds_and_warnings"] +
        score["holds_and_limitations"]))
    # Requests are PLAN only. Existing forward_ai_shadow.run mandates
    # opt-in and max_api_calls <= 2 per event, and its ledger is authoritative
    # for possible previous billing. No implicit retry or provider selection.
    possible_new_event_count = max(
        0, macro["macro_event_count"] - macro["ledger_count"])
    estimated_calls = 2 * possible_new_event_count
    return {
        "schema": SCHEMA,
        "status": "MACRO_FORWARD_RESEARCH_CAMPAIGN_HOLD_NO_GO",
        "asof_utc": asof_utc,
        "session_count": quality["session_count"],
        "price_csv_count": quality["files"],
        "complete_cycle_count": quality["cycle_count"],
        "pair_quote_statistics_research_only": quality["pair_statistics"],
        "time_of_day_hour_bucket_counts": {
            pair: len(buckets) for pair, buckets
            in coverage["per_pair_utc_hour"].items()},
        "observed_macro_event_count": macro["macro_event_count"],
        "missing_consensus_event_count":
            macro["macro_event_missing_consensus_count"],
        "macro_hypothesis_count": macro["macro_hypothesis_count"],
        "review_count": macro["macro_review_count"],
        "completed_or_pending_AI_ledger_count": macro["ledger_count"],
        "independent_model_review_unattested": True,
        "reviewed_long_short_candidate_count":
            macro["research_only_candidate_count"],
        "descriptive_two_snapshot_mark_count":
            score["two_snapshot_descriptive_mark_count"],
        "two_snapshot_pair_summary": score["descriptive_pair_summary"],
        "possible_new_AI_event_count_research_only": possible_new_event_count,
        "maximum_two_model_api_calls_if_all_new_events_chosen":
            estimated_calls,
        "API_call_cost_estimate_jpy": None,
        "API_calls_this_run": 0,
        "external_network_access_this_run": False,
        "replay_or_order_executed_this_run": False,
        "source_checksum_of_summary_only": manifest_sha,
        "checksum_is_not_provenance_authentication": True,
        "next_research_actions": actions,
        "unresolved_warnings_and_safety_holds": warnings,
        "real_strategy_out_of_sample_profitability_proven": False,
        "broker_time_and_account_authenticated": False,
        "real_orders_permitted": False,
        "demo_orders_permitted": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="One-command NO_GO macro research board")
    p.add_argument("--session", action="append", required=True)
    p.add_argument("--store", type=Path)
    p.add_argument("--ai-ledger", type=Path, action="append", default=[])
    p.add_argument("--asof-utc", required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args(argv)
    try:
        sessions = list(_parse_labeled_entries(
            a.session, "--session").items())
        source_dirs = [directory.resolve() for _, directory in sessions]
        if a.store is not None:
            source_dirs.append(a.store.resolve())
        if (a.out.exists() or a.out.is_symlink()
                or not a.out.parent.is_dir()
                or any(folder in a.out.resolve().parents
                       for folder in source_dirs)):
            raise InputError("unsafe report destination")
        report = inspect(sessions, store=a.store, ai_ledgers=a.ai_ledger,
                         asof_utc=a.asof_utc)
        with a.out.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2)
        print(json.dumps({
            "status": report["status"],
            "files": report["price_csv_count"],
            "complete_cycles": report["complete_cycle_count"],
            "macro_events": report["observed_macro_event_count"],
            "reviewed_candidates": report["reviewed_long_short_candidate_count"],
            "descriptive_marks": report["descriptive_two_snapshot_mark_count"],
            "next_research_actions": report["next_research_actions"],
            "API_calls_this_run": 0,
            "runtime_go_no_go": "NO_GO",
            "real_orders_permitted": False,
        }))
        return 0
    except (InputError, OSError, ValueError, TypeError, KeyError,
            UnicodeError, ArithmeticError, OverflowError):
        print(json.dumps({
            "status": "FAIL_CLOSED",
            "reason": "MACRO_RESEARCH_CAMPAIGN_EVIDENCE_INVALID",
            "runtime_go_no_go": "NO_GO",
            "safety_hold_latched": True,
            "real_orders_permitted": False,
        }))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
