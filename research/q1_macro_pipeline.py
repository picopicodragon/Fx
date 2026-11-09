"""Single command for 2025Q1 real-source AI macro replay on a local Windows PC.

Offline preflight by default. Only --allow-external-api sends evidence to
OpenAI's billed Responses API. No order or MT4 connectivity.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from research import historical_replay as hist
from research import macro_ai_backtest as replay
from research import macro_ai_generate as ai
from research.offline_backtest import InputError

DEFAULT_EVIDENCE = (Path(__file__).parent / "datasets" /
                    "official_2025q1_us_macro_evidence.json")
FILE_TAG = "2025-01-01-2025-04-01"


def prices(folder: Path):
    return {sym: (folder / f"{sym}-h1-bid-{FILE_TAG}.csv",
                  folder / f"{sym}-h1-ask-{FILE_TAG}.csv")
            for sym in hist.SYMBOLS}


def preflight(folder: Path, evidence_path: Path):
    evidence, metadata = replay.evidence_file(evidence_path)
    bars, pricing = hist.prepare(prices(folder))
    first_close = bars[0].time
    last_close = bars[-1].time
    return evidence, {
        "status": "PRECHECK_RESEARCH_ONLY_NO_GO",
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
        "priced_bars": len(bars),
        "data_start_utc": first_close.isoformat(),
        "data_end_utc": last_close.isoformat(),
        "source_events": metadata["evidence_event_count"],
        "input_price_checksums": pricing["input_checksums"],
        "price_provenance_independently_verified": False,
        "market_consensus_values_missing": sum(
            not e["market_expectation"] for e in evidence.values()),
        "ai_api_called": False,
        "ai_backtest_executed": False,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="2025Q1 real-text historical AI macro backtest (NO_GO)")
    ap.add_argument("--prices-dir", type=Path,
                    default=Path("data/raw/dukascopy_h1"))
    ap.add_argument("--evidence", type=Path, default=DEFAULT_EVIDENCE)
    ap.add_argument("--decisions-out", type=Path,
                    default=Path("out/macro_ai_decisions_2025Q1.json"))
    ap.add_argument("--report-out", type=Path,
                    default=Path("out/macro_ai_backtest_2025Q1.json"))
    ap.add_argument("--analyst-model", default="")
    ap.add_argument("--reviewer-model", default="")
    ap.add_argument("--max-decisions", type=int, default=24)
    ap.add_argument("--allow-external-api", action="store_true")
    args = ap.parse_args(argv)
    try:
        sources, info = preflight(args.prices_dir, args.evidence)
        if not args.allow_external_api:
            print(json.dumps(info, indent=2))
            return 0  # Explicitly not a backtest or AI run.
        if (not os.environ.get("OPENAI_API_KEY")
                or args.decisions_out.exists() or args.report_out.exists()
                or not args.decisions_out.parent.is_dir()
                or not args.report_out.parent.is_dir()
                or args.decisions_out == args.report_out):
            raise InputError("refuse unavailable credentials or overwrite")
        # First complete local price/evidence validation; then only when
        # explicitly enabled send text to external models.
        journal = ai.generate(
            sources, analyst_model=args.analyst_model,
            reviewer_model=args.reviewer_model,
            max_decisions=args.max_decisions,
            api_key=os.environ["OPENAI_API_KEY"])
        # Check journal against the source and price timeline before saving.
        # Repository data and user-owned CSVs are never uploaded by this tool.
        with args.decisions_out.open("x", encoding="utf-8") as handle:
            json.dump(journal, handle, ensure_ascii=False, indent=2)
        result = replay.run(prices(args.prices_dir), args.evidence,
                            args.decisions_out)
        with args.report_out.open("x", encoding="utf-8") as handle:
            json.dump(result, handle, ensure_ascii=False, indent=2)
    except (InputError, OSError, TypeError, ValueError, ArithmeticError):
        print(json.dumps({
            "status": "FAIL_CLOSED", "runtime_go_no_go": "NO_GO",
            "safety_hold_latched": True,
            "ai_or_historical_replay_complete": False,
            "error": "MACRO_PIPELINE_INPUT_OR_API_FAILURE"}))
        return 2
    print(json.dumps({
        "status": "AI_MACRO_RESEARCH_REPLAY_COMPLETE_NO_GO",
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
        "source_events": info["source_events"],
        "model_generated_decisions": len(journal["decisions"]),
        "trade_count": result["trade_count"],
        "net_pnl_jpy": result["net_pnl_jpy"],
        "actual_research_not_live": True
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
