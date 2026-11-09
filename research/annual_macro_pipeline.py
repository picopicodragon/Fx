"""2025 full-calendar-year offline FX macro replay, three pairs, NO_GO.

Preflight never sends user prices or evidence to an API. Annual API inference
requires BOTH explicit opt-in AND a hard maximum paid-call budget. A saved
journal can be replayed without any additional API calls. No MT4 or orders.
"""
from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from pathlib import Path

from research import historical_replay as hist
from research import macro_ai_backtest as replay
from research import macro_ai_generate as ai
from research.offline_backtest import InputError, PAIRS, timestamp

START = datetime(2025, 1, 1, tzinfo=timezone.utc)
END = datetime(2026, 1, 1, tzinfo=timezone.utc)
DATASET = Path(__file__).parent / "datasets" / "official_2025_macro_evidence_seed.json"
FILE_TAG = "2025-01-01-2026-01-01"
DEFAULT_PAIRS = ("USD/JPY", "EUR/JPY", "EUR/USD")


def prices(folder: Path) -> dict:
    return {
        sym: (folder / f"{sym}-h1-bid-{FILE_TAG}.csv",
              folder / f"{sym}-h1-ask-{FILE_TAG}.csv")
        for sym in hist.SYMBOLS
    }


def preflight(folder: Path, evidence_path: Path) -> tuple[dict, dict]:
    if tuple(PAIRS) != DEFAULT_PAIRS:
        raise InputError("formal three-pair scope mismatch")
    sources, meta = replay.evidence_file(evidence_path)
    if not all(START <= timestamp(e["available_at_utc"]) < END
               for e in sources.values()):
        raise InputError("evidence not restricted to 2025")
    bars, market = hist.prepare(prices(folder))
    if not bars:
        raise InputError("missing aligned 2025 H1 bars")
    # Do not pass off a Q1-only CSV as annual coverage.
    if bars[0].time > datetime(2025, 1, 6, tzinfo=timezone.utc) or (
            bars[-1].time < datetime(2025, 12, 29, tzinfo=timezone.utc)
            or bars[-1].time >= END or bars[0].time < START):
        raise InputError("insufficient full-year time coverage")
    available = {(b.time + timedelta(hours=1), b.pair) for b in bars}
    for e in sources.values():
        published = timestamp(e["available_at_utc"])
        asof = published.replace(minute=0, second=0, microsecond=0)
        if asof < published:
            asof += timedelta(hours=1)
        for pair in PAIRS:
            if (asof, pair) not in available:
                raise InputError("historical event has no closed H1 price")
    cutoffs = set()
    for e in sources.values():
        t = timestamp(e["available_at_utc"])
        h = t.replace(minute=0, second=0, microsecond=0)
        cutoffs.add(h if h == t else h + timedelta(hours=1))
    estimated_decisions = len(cutoffs) * len(PAIRS)
    return sources, {
        "status": "ANNUAL_PRECHECK_RESEARCH_ONLY_NO_GO",
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
        "period": "2025-01-01_to_2026-01-01_UTC",
        "formal_pairs": list(PAIRS),
        "event_count": len(sources),
        "possible_decisions": estimated_decisions,
        "estimated_full_inference_api_calls": 2 * estimated_decisions,
        "missing_consensus_event_count": sum(
            not e["market_expectation"] for e in sources.values()),
        "market_consensus_point_in_time_independently_verified": False,
        "historical_price_provenance_independently_verified": False,
        "input_price_checksums": market["input_checksums"],
        "aligned_bars_per_pair": market["aligned_bars_per_pair"],
        "price_start_utc": bars[0].time.isoformat(),
        "price_end_utc": bars[-1].time.isoformat(),
        "paid_api_calls": 0,
    }


def _quarter(t: str) -> str:
    dt = datetime.fromisoformat(t.replace("Z", "+00:00"))
    if dt.tzinfo is None or dt.utcoffset() != timedelta(0):
        raise InputError("invalid quarter timestamp")
    if not START <= dt < END:
        raise InputError("trade or decision outside 2025")
    return f"2025Q{1 + (dt.month - 1) // 3}"


def quarter_summary(report: dict, journal: dict) -> dict:
    """Descriptive quarters. PnL attributed to EXIT quarter, no fake Q DD."""
    outcome = {
        f"2025Q{n}": {
            "decision_count": 0, "approved_nonhold": 0,
            "closed_trade_count": 0, "realized_pnl_jpy": "0",
        } for n in range(1, 5)
    }
    for decision in journal["decisions"]:
        key = _quarter(decision["asof_utc"])
        row = outcome[key]
        row["decision_count"] += 1
        if (decision["reviewer"]["verdict"] == "APPROVED"
                and decision["analyst"]["action"] in ("LONG", "SHORT")):
            row["approved_nonhold"] += 1
    for trade in report["trades"]:
        key = _quarter(trade["exit_time_utc"])
        outcome[key]["closed_trade_count"] += 1
        existing = Decimal(outcome[key]["realized_pnl_jpy"])
        outcome[key]["realized_pnl_jpy"] = str(
            existing + Decimal(trade["pnl_jpy"]))
    if sum(Decimal(v["realized_pnl_jpy"]) for v in outcome.values()) != (
            Decimal(report["net_pnl_jpy"])):
        raise InputError("quarterly PnL does not reconcile")
    return outcome


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description="Three-pair 2025 annual research; offline by default; NO_GO")
    p.add_argument("--prices-dir", type=Path,
                   default=Path("data/raw/dukascopy_h1"))
    p.add_argument("--evidence", type=Path, default=DATASET)
    p.add_argument("--decisions", type=Path,
                   help="Replay an existing 2025 journal locally, no AI")
    p.add_argument("--journal-out", type=Path,
                   default=Path("out/macro_ai_decisions_2025_full.json"))
    p.add_argument("--report-out", type=Path,
                   default=Path("out/macro_ai_report_2025_full.json"))
    p.add_argument("--analyst-model", default="")
    p.add_argument("--reviewer-model", default="")
    p.add_argument("--max-decisions", type=int, default=3)
    p.add_argument("--max-api-calls", type=int, default=0)
    p.add_argument("--allow-external-api", action="store_true")
    args = p.parse_args(argv)
    stage = "PREFLIGHT"
    try:
        sources, info = preflight(args.prices_dir, args.evidence)
        if not args.allow_external_api and args.decisions is None:
            print(json.dumps(info, indent=2))
            return 0
        if args.decisions is not None and args.allow_external_api:
            raise InputError("replay and paid generation are mutually exclusive")
        if args.report_out.exists() or not args.report_out.parent.is_dir():
            raise InputError("report target unavailable")
        if args.decisions is not None:
            # Reuse an existing journal with zero API calls.
            stage = "OFFLINE_REPLAY"
            journal = replay._json(args.decisions)
            replay.decision_file(args.decisions, sources)
            decision_path = args.decisions
        else:
            stage = "BILLING_CAP"
            if (args.max_decisions < 1 or args.max_decisions > 120
                    or args.max_api_calls < args.max_decisions * 2
                    or args.max_api_calls > 240
                    or not args.analyst_model or not args.reviewer_model
                    or not os.environ.get("OPENAI_API_KEY")
                    or args.journal_out.exists()
                    or not args.journal_out.parent.is_dir()
                    or args.journal_out == args.report_out):
                raise InputError("invalid explicit billed-call budget or output")
            stage = "AI_GENERATION"
            journal = ai.generate(
                sources, analyst_model=args.analyst_model,
                reviewer_model=args.reviewer_model,
                max_decisions=args.max_decisions,
                api_key=os.environ["OPENAI_API_KEY"])
            stage = "JOURNAL_WRITE"
            with args.journal_out.open("x", encoding="utf-8") as stream:
                json.dump(journal, stream, ensure_ascii=False, indent=2)
            decision_path = args.journal_out
        stage = "REPLAY"
        result = replay.run(prices(args.prices_dir), args.evidence,
                            decision_path)
        result["annual_macro_research"] = {
            "schema": "fx_annual_macro_research_2025_v1",
            "formal_pairs": list(PAIRS),
            "coverage_is_sparse_seed_not_all_market_events": True,
            "q4_is_descriptive_not_proven_forward_oos": True,
            "quarterly_realized_exit_attribution": quarter_summary(
                result, journal),
            "source_manifest_sha256": replay.canonical_hash(
                [sources[k] for k in sorted(sources)]),
            "explicit_billing_budget": args.max_api_calls
            if args.allow_external_api else 0,
            "real_orders_permitted": False,
        }
        stage = "REPORT_WRITE"
        with args.report_out.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2)
    except (InputError, OSError, ValueError, TypeError, ArithmeticError) as exc:
        print(json.dumps({
            "status": "FAIL_CLOSED", "runtime_go_no_go": "NO_GO",
            "safety_hold_latched": True, "failure_stage": stage,
            "reason": exc.reason if isinstance(exc, ai.MacroAPIError)
            else "INVALID_OR_UNSAFE_RESEARCH_INPUT",
        }))
        return 2
    print(json.dumps({
        "status": "ANNUAL_MACRO_RESEARCH_COMPLETE_NO_GO",
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
        "source_events": len(sources),
        "model_generated_or_replayed_decisions": len(journal["decisions"]),
        "trade_count": result["trade_count"],
        "net_pnl_jpy": result["net_pnl_jpy"],
        "quarterly": result["annual_macro_research"][
            "quarterly_realized_exit_attribution"],
        "real_order_execution_authorized": False,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
