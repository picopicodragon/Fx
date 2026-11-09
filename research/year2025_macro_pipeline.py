"""2025 full-calendar-year OFFLINE/opt-in FX macro research.

The corpus can be inspected without market data or API. Replay requires the
user's full-year six bid/ask H1 CSV files. No broker, MT4, or orders.
"""
from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from dataclasses import replace
from datetime import datetime, timezone, timedelta
from pathlib import Path

from research import historical_replay as hist
from research import macro_ai_backtest as replay
from research import macro_ai_generate as ai
from research.offline_backtest import InputError, PAIRS, simulate, timestamp

EVIDENCE = Path(__file__).parent / "datasets" / "official_2025_macro_evidence.json"
DATE_TAG = "2025-01-01-2026-01-01"
TRAIN_END = datetime(2025, 10, 1, tzinfo=timezone.utc)
END = datetime(2026, 1, 1, tzinfo=timezone.utc)
MAX_YEAR_DECISIONS = 120
MAX_YEAR_CALLS = MAX_YEAR_DECISIONS * 2
DEFAULT_DECISIONS = 3  # low-cost smoke test; NOT a full-year result
START = datetime(2025, 1, 1, tzinfo=timezone.utc)


def year_prices(folder: Path) -> dict:
    return {
        symbol: (folder / f"{symbol}-h1-bid-{DATE_TAG}.csv",
                 folder / f"{symbol}-h1-ask-{DATE_TAG}.csv")
        for symbol in hist.SYMBOLS
    }


def check_corpus(path: Path) -> tuple[dict, dict]:
    events, metadata = replay.evidence_file(path)
    months = set()
    by_type = Counter()
    missing_forecasts = 0
    for item in events.values():
        when = timestamp(item["available_at_utc"])
        if not START <= when < END:
            raise InputError("event outside 2025")
        months.add(when.month)
        by_type[item["source_type"]] += 1
        missing_forecasts += not bool(item["market_expectation"])
        if not item["source_url"].startswith((
                "https://www.bls.gov/",
                "https://www.federalreserve.gov/",
                "https://www.boj.or.jp/",
                "https://www.ecb.europa.eu/")):
            raise InputError("unapproved source domain")
    if months != set(range(1, 13)):
        raise InputError("missing calendar month in macro evidence")
    if any(len(item["text"]) == 0 for item in events.values()):
        raise InputError("missing source summary")
    return events, {
        "scope": "2025_full_year_official_source_snapshot",
        "evidence_sha256": metadata["evidence_manifest_sha256"],
        "source_events": metadata["evidence_event_count"],
        "months_with_evidence": sorted(months),
        "source_types": dict(sorted(by_type.items())),
        "market_expectations_missing": missing_forecasts,
        "market_consensus_point_in_time_authenticated": False,
        "source_publication_times_independently_authenticated": False,
        "currency_pairs": list(PAIRS),
    }


def check_year_prices(folder: Path) -> dict:
    bars, pricing = hist.prepare(year_prices(folder))
    months = {bar.time.month for bar in bars if bar.time.year == 2025}
    if (months != set(range(1, 13))
            or bars[0].time >= START + timedelta(days=7)
            or bars[-1].time < datetime(2025, 12, 20, tzinfo=timezone.utc)
            or bars[-1].time >= END + timedelta(days=2)
            or any(bar.time < START or bar.time >= END for bar in bars)):
        raise InputError("price year incomplete or timestamps out of window")
    unique_times = sorted({bar.time for bar in bars})
    if any(b - a > timedelta(days=7)
           for a, b in zip(unique_times, unique_times[1:])):
        raise InputError("long gap in price coverage")
    return {
        "verified_months": sorted(months),
        "first_bar_utc": unique_times[0].isoformat(),
        "last_bar_utc": unique_times[-1].isoformat(),
        "aligned_bars_per_pair": pricing["aligned_bars_per_pair"],
        "input_price_checksums": pricing["input_checksums"],
        "price_provenance_independently_verified": False,
        "broker_contract_specifications_verified": False,
    }


def expected_decisions(events: dict) -> int:
    """3 pair decisions per distinct H1 as-of with at least one source."""
    cutoffs = {
        timestamp(e["available_at_utc"]).replace(
            minute=0, second=0, microsecond=0) +
        (timedelta(hours=1) if timestamp(e["available_at_utc"]).minute or
         timestamp(e["available_at_utc"]).second or
         timestamp(e["available_at_utc"]).microsecond else timedelta())
        for e in events.values()
    }
    return len(cutoffs) * len(PAIRS)


def evaluate_periods(source_path: Path, journal_path: Path,
                     price_dir: Path) -> dict:
    """Same price source, same simulator for all, train, Q4 held-out replay.

    Q4 is time-separated but NOT a prospectively tested true OOS experiment:
    model weights and the curated source list are known after 2025.
    """
    sources, _ = check_corpus(source_path)
    actions, audit = replay.decision_file(journal_path, sources)
    bars, price_meta = hist.prepare(year_prices(price_dir))
    closes = {(bar.time + timedelta(hours=1), bar.pair) for bar in bars}
    if any(key not in closes for key in actions):
        raise InputError("as-of key outside supplied H1 history")
    # Keep SMA signal data for separate control only, never pass it to AI replay.
    ai_bars = [
        replace(bar, signal=actions.get(
            (bar.time + timedelta(hours=1), bar.pair), "HOLD"))
        for bar in bars
    ]
    slices = {
        "full_year": ai_bars,
        "development_jan_sep": [b for b in ai_bars if b.time < TRAIN_END],
        "held_out_oct_dec": [b for b in ai_bars if b.time >= TRAIN_END],
    }
    # The simulator starts each window with its own 100000 JPY cash; any open
    # position is forcibly closed at a period edge, not carried between windows.
    if any(not chunk for chunk in slices.values()):
        raise InputError("empty period")
    reports = {}
    for name, chunk in slices.items():
        result = simulate(chunk)
        reports[name] = {
            "trade_count": result["trade_count"],
            "net_pnl_jpy": result["net_pnl_jpy"],
            "max_drawdown_observed_pct":
                result["max_drawdown_observed_pct"],
            "signals_rejected": result["signals_rejected"],
            "signals_rejected_by_reason":
                result["signals_rejected_by_reason"],
            "ending_jpy": result["ending_jpy"],
            "starting_jpy": result["starting_jpy"],
        }
    # Separate transparent SMA control, no inference / AI label.
    baseline = simulate(bars)
    return {
        "status": "2025_RESEARCH_REPLAY_COMPLETE_NO_GO",
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
        "source_events": len(sources),
        "decision_count": audit["decision_count"],
        "approved_nonhold_count": audit["approved_nonhold_count"],
        "decision_journal_sha256": audit["ai_decision_journal_sha256"],
        "input_price_checksums": price_meta["input_checksums"],
        "calendar_2025": reports,
        "sma10_30_separate_control": {
            "strategy": "SMA_CROSSOVER_ONLY_NOT_AI",
            "trade_count": baseline["trade_count"],
            "net_pnl_jpy": baseline["net_pnl_jpy"],
            "max_drawdown_observed_pct":
                baseline["max_drawdown_observed_pct"],
        },
        "held_out_window_is_prospective": False,
        "possible_pretraining_future_knowledge": True,
        "missing_contemporaneous_consensus_warning": True,
        "replay_costs_model_limitations": price_meta["known_limitations"],
        "historical_prices_independently_authenticated": False,
        "trade_orders_enabled": False,
        "human_approval_granted": False,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="2025 3-pair macro research, offline by default, NO_GO")
    parser.add_argument("--evidence", type=Path, default=EVIDENCE)
    parser.add_argument("--prices-dir", type=Path,
                        default=Path("data/raw/dukascopy_h1"))
    parser.add_argument("--evidence-only", action="store_true")
    parser.add_argument("--decisions-out", type=Path,
                        default=Path("out/macro_ai_decisions_2025.json"))
    parser.add_argument("--report-out", type=Path,
                        default=Path("out/macro_ai_backtest_2025.json"))
    parser.add_argument("--analyst-model", default="gpt-6-luna")
    parser.add_argument("--reviewer-model", default="gpt-6.1-sol")
    parser.add_argument("--max-decisions", type=int,
                        default=DEFAULT_DECISIONS)
    parser.add_argument("--max-api-requests", type=int, default=6)
    parser.add_argument("--allow-external-api", action="store_true")
    stage = "CORPUS"
    args = parser.parse_args(argv)
    try:
        events, manifest = check_corpus(args.evidence)
        total = expected_decisions(events)
        if not 1 <= total <= MAX_YEAR_DECISIONS:
            raise InputError("unsupported year decision count")
        if args.evidence_only:
            if args.allow_external_api:
                raise InputError("evidence-only conflicts with API")
            print(json.dumps({
                "status": "2025_EVIDENCE_ONLY_RESEARCH_NO_GO",
                "runtime_go_no_go": "NO_GO",
                "safety_hold_latched": True,
                "expected_full_year_decisions": total,
                **manifest
            }, ensure_ascii=False, indent=2))
            return 0
        stage = "PRICE_PREFLIGHT"
        pricing = check_year_prices(args.prices_dir)
        if not args.allow_external_api:
            print(json.dumps({
                "status": "2025_PRICE_PREFLIGHT_NO_GO",
                "runtime_go_no_go": "NO_GO",
                "safety_hold_latched": True,
                "expected_full_year_decisions": total,
                **manifest, **pricing,
                "ai_api_called": False,
            }, ensure_ascii=False, indent=2))
            return 0
        # Explicit, bounded billable API calls; no silent large run.
        if (not 1 <= args.max_decisions <= total
                or type(args.max_api_requests) is not int
                or not 2 <= args.max_api_requests <= MAX_YEAR_CALLS
                or 2 * args.max_decisions > args.max_api_requests
                or not os.environ.get("OPENAI_API_KEY")
                or args.decisions_out == args.report_out
                or args.decisions_out.exists() or args.report_out.exists()
                or not args.decisions_out.parent.is_dir()
                or not args.report_out.parent.is_dir()):
            raise InputError("unsafe or insufficient API budget/config")
        stage = "AI_GENERATION"
        journal = ai.generate(
            events, analyst_model=args.analyst_model,
            reviewer_model=args.reviewer_model,
            max_decisions=args.max_decisions,
            decision_limit=MAX_YEAR_DECISIONS,
            api_key=os.environ["OPENAI_API_KEY"])
        stage = "DECISIONS_WRITE"
        # A partial-year smoke test is saved but not misreported as a full year.
        with args.decisions_out.open("x", encoding="utf-8") as file:
            json.dump(journal, file, ensure_ascii=False, indent=2)
        stage = "REPLAY"
        result = evaluate_periods(args.evidence, args.decisions_out,
                                  args.prices_dir)
        complete = args.max_decisions == total
        result["full_year_decision_coverage_complete"] = complete
        result["expected_full_year_decisions"] = total
        result["research_scope"] = ("FULL_2025" if complete
                                    else "PARTIAL_PREFIX_SMOKE_TEST")
        if not complete:
            result["status"] = "2025_PARTIAL_RESEARCH_REPLAY_NO_GO"
            result["held_out_window_evaluated_with_complete_decisions"] = False
        stage = "REPORT_WRITE"
        with args.report_out.open("x", encoding="utf-8") as file:
            json.dump(result, file, ensure_ascii=False, indent=2)
    except (InputError, OSError, ArithmeticError, TypeError, ValueError) as exc:
        print(json.dumps({
            "status": "FAIL_CLOSED", "runtime_go_no_go": "NO_GO",
            "safety_hold_latched": True, "failure_stage": stage,
            "failure_reason": (
                exc.reason if isinstance(exc, ai.MacroAPIError)
                else "INVALID_OR_INCOMPLETE_RESEARCH_INPUT"),
            "role": exc.role if isinstance(exc, ai.MacroAPIError)
                    else "UNKNOWN",
        }))
        return 2
    print(json.dumps({
        "status": result["status"],
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
        "decisions": len(journal["decisions"]),
        "full_year_decision_coverage_complete": complete,
        "year_trades": result["calendar_2025"]["full_year"]["trade_count"],
        "year_net_pnl_jpy":
            result["calendar_2025"]["full_year"]["net_pnl_jpy"],
        "holdout_oct_dec_trades":
            result["calendar_2025"]["held_out_oct_dec"]["trade_count"],
        "holdout_oct_dec_net_pnl_jpy":
            result["calendar_2025"]["held_out_oct_dec"]["net_pnl_jpy"],
        "SMA_strategy_is_separate": True,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
